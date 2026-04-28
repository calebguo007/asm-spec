#!/usr/bin/env python3
"""LLM selector baseline for raw documents vs ASM manifests.

This experiment targets the core critique: why not let a large model read
provider docs and choose? It compares three surfaces over the same tasks:

  1. llm_raw_doc: LLM sees candidate IDs plus raw public source snippets.
  2. llm_manifest: LLM sees candidate IDs plus compact ASM manifests.
  3. asm_topsis: deterministic settlement over structured manifest vectors.

Without an API key/model, the script prepares raw-doc caches and prompt JSONL
files but does not fabricate LLM results.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import Preferences, ServiceVector, load_manifests, parse_manifest, score_topsis  # noqa: E402
from scorer import score_weighted_average  # noqa: E402


PREFERENCE_PROFILES: dict[str, Preferences] = {
    "cost_first": Preferences(cost=0.55, quality=0.25, speed=0.10, reliability=0.10),
    "quality_first": Preferences(cost=0.10, quality=0.55, speed=0.20, reliability=0.15),
    "speed_first": Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
    "balanced": Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
}


@dataclass
class Task:
    task_id: int
    taxonomy: str
    profile: str
    max_cost: float | None
    max_latency_s: float | None
    min_quality: float | None


@dataclass
class Candidate:
    manifest: dict[str, Any]
    vector: ServiceVector


@dataclass
class SelectionRecord:
    task_id: int
    taxonomy: str
    profile: str
    selector: str
    selected_service_id: str
    selected_display_name: str
    valid_service_id: bool
    constraint_violation: bool
    parse_failure: bool
    utility: float
    best_utility: float
    regret: float
    cost_per_unit: float
    latency_seconds: float
    quality_score: float
    prompt_chars: int
    completion_chars: int
    reason: str


@dataclass
class SourceFetchEvent:
    service_id: str
    source_url: str
    cache_path: str
    cache_hit: bool
    fetched_chars: int
    returned_chars: int
    status: str
    error: str


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(max(int(round((len(values) - 1) * p)), 0), len(values) - 1)
    return values[index]


def finite_latency(value: float) -> float:
    return value if math.isfinite(value) else 1e9


def slug_for_url(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/") or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:140]


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_source_text(url: str, service_id: str, cache_dir: Path, max_chars: int) -> tuple[str, SourceFetchEvent]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{slug_for_url(url or service_id)}.txt"
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars], SourceFetchEvent(
            service_id=service_id,
            source_url=url,
            cache_path=str(cache_path),
            cache_hit=True,
            fetched_chars=len(text),
            returned_chars=min(len(text), max_chars),
            status="cache_hit",
            error="",
        )

    text = ""
    status = "fetched"
    error = ""
    if url:
        try:
            req = Request(url, headers={"User-Agent": "asm-llm-selector-baseline"})
            with urlopen(req, timeout=10) as response:
                raw = response.read(300_000).decode("utf-8", errors="replace")
                text = strip_html(raw)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            status = "unavailable"
            error = type(exc).__name__
            text = f"[source unavailable: {type(exc).__name__}] {url}"

    if not text:
        status = "unavailable"
        text = f"[source unavailable] {url}"
    cache_path.write_text(text, encoding="utf-8")
    return text[:max_chars], SourceFetchEvent(
        service_id=service_id,
        source_url=url,
        cache_path=str(cache_path),
        cache_hit=False,
        fetched_chars=len(text),
        returned_chars=min(len(text), max_chars),
        status=status,
        error=error,
    )


def compact_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "service_id",
        "taxonomy",
        "display_name",
        "provider",
        "capabilities",
        "pricing",
        "quality",
        "sla",
        "payment",
        "provenance",
    ]
    return {key: manifest[key] for key in keys if key in manifest}


def candidate_source_url(manifest: dict[str, Any]) -> str:
    return (
        ((manifest.get("provenance") or {}).get("source_url"))
        or ((manifest.get("provider") or {}).get("url"))
        or ((manifest.get("payment") or {}).get("signup_url"))
        or ""
    )


def constraints_for(profile: str, vectors: list[ServiceVector]) -> tuple[float | None, float | None, float | None]:
    costs = [v.cost_per_unit for v in vectors]
    latencies = [finite_latency(v.latency_seconds) for v in vectors]
    qualities = [v.quality_score for v in vectors]
    max_cost = None
    max_latency = None
    min_quality = None
    if profile in {"cost_first", "balanced"}:
        max_cost = percentile(costs, 0.75)
    if profile in {"speed_first", "balanced"}:
        max_latency = percentile(latencies, 0.75)
    if profile in {"quality_first", "balanced"}:
        min_quality = percentile(qualities, 0.25)
    return max_cost, max_latency, min_quality


def satisfies(task: Task, vector: ServiceVector) -> bool:
    if task.max_cost is not None and vector.cost_per_unit > task.max_cost:
        return False
    if task.max_latency_s is not None and finite_latency(vector.latency_seconds) > task.max_latency_s:
        return False
    if task.min_quality is not None and vector.quality_score < task.min_quality:
        return False
    return True


def generate_tasks(candidate_map: dict[str, list[Candidate]], count: int, seed: int) -> list[Task]:
    rng = random.Random(seed)
    taxonomies = sorted(tax for tax, candidates in candidate_map.items() if len(candidates) >= 2)
    if not taxonomies:
        raise ValueError("Need at least one taxonomy with two or more candidate services")
    profiles = sorted(PREFERENCE_PROFILES)
    tasks = []
    for task_id in range(1, count + 1):
        taxonomy = rng.choice(taxonomies)
        profile = rng.choice(profiles)
        vectors = [c.vector for c in candidate_map[taxonomy]]
        max_cost, max_latency, min_quality = constraints_for(profile, vectors)
        tasks.append(Task(task_id, taxonomy, profile, max_cost, max_latency, min_quality))
    return tasks


def task_instruction(task: Task, candidates: list[Candidate]) -> str:
    prefs = PREFERENCE_PROFILES[task.profile]
    lines = [
        "You are selecting one service for an autonomous agent.",
        "Return only JSON with keys: service_id, reason.",
        f"Required taxonomy: {task.taxonomy}",
        f"Preference profile: {task.profile}",
        f"Weights: cost={prefs.cost:.2f}, quality={prefs.quality:.2f}, speed={prefs.speed:.2f}, reliability={prefs.reliability:.2f}",
        "Hard constraints:",
    ]
    if task.max_cost is not None:
        lines.append(f"- cost_per_unit <= {task.max_cost:.10f}")
    if task.max_latency_s is not None:
        lines.append(f"- latency_seconds <= {task.max_latency_s:.4f}")
    if task.min_quality is not None:
        lines.append(f"- quality_score >= {task.min_quality:.4f}")
    if task.max_cost is None and task.max_latency_s is None and task.min_quality is None:
        lines.append("- none")
    lines.append("Candidate service IDs: " + ", ".join(c.vector.service_id for c in candidates))
    return "\n".join(lines)


def build_raw_doc_prompt(
    task: Task,
    candidates: list[Candidate],
    cache_dir: Path,
    max_source_chars: int,
) -> tuple[str, list[SourceFetchEvent]]:
    parts = [task_instruction(task, candidates), "\nRaw public source snippets:"]
    per_candidate_chars = max(500, max_source_chars // max(len(candidates), 1))
    events: list[SourceFetchEvent] = []
    for candidate in candidates:
        manifest = candidate.manifest
        source_url = candidate_source_url(manifest)
        source_text, event = fetch_source_text(source_url, candidate.vector.service_id, cache_dir, per_candidate_chars)
        events.append(event)
        parts.append(
            "\n---\n"
            f"service_id: {candidate.vector.service_id}\n"
            f"display_name: {candidate.vector.display_name}\n"
            f"source_url: {source_url}\n"
            f"source_excerpt:\n{source_text}"
        )
    return "\n".join(parts), events


def build_manifest_prompt(task: Task, candidates: list[Candidate]) -> str:
    payload = [compact_manifest(c.manifest) for c in candidates]
    return task_instruction(task, candidates) + "\n\nASM manifests:\n" + json.dumps(payload, indent=2)


def call_openai_chat(prompt: str, model: str, api_key: str, temperature: float, base_url: str) -> str:
    import urllib.request

    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": "You are a strict JSON service selector. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"]


def parse_llm_choice(text: str) -> tuple[str, str, bool]:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        data = json.loads(cleaned)
        return str(data.get("service_id", "")).strip(), str(data.get("reason", "")).strip(), False
    except json.JSONDecodeError:
        match = re.search(r"[\w.-]+/[\w.@-]+", text)
        return (match.group(0) if match else "", text[:300], True)


def utility_lookup(candidates: list[Candidate], prefs: Preferences) -> dict[str, float]:
    return {r.service.service_id: r.total_score for r in score_topsis([c.vector for c in candidates], prefs)}


def feasible_candidates(task: Task, candidates: list[Candidate]) -> list[Candidate]:
    return [c for c in candidates if satisfies(task, c.vector)]


def choose_topsis(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    prefs = PREFERENCE_PROFILES[task.profile]
    winner = score_topsis([c.vector for c in pool], prefs)[0].service.service_id
    return next(c for c in candidates if c.vector.service_id == winner)


def choose_weighted_average(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    prefs = PREFERENCE_PROFILES[task.profile]
    winner = score_weighted_average([c.vector for c in pool], prefs)[0].service.service_id
    return next(c for c in candidates if c.vector.service_id == winner)


def choose_cheapest(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    return min(pool, key=lambda c: c.vector.cost_per_unit)


def choose_fastest(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    return min(pool, key=lambda c: finite_latency(c.vector.latency_seconds))


def choose_highest_quality(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    return max(pool, key=lambda c: c.vector.quality_score)


def choose_most_expensive(task: Task, candidates: list[Candidate]) -> Candidate:
    pool = feasible_candidates(task, candidates) or candidates
    return max(pool, key=lambda c: c.vector.cost_per_unit)


HEURISTIC_SELECTORS = {
    "cheapest_first": choose_cheapest,
    "fastest_first": choose_fastest,
    "highest_quality_first": choose_highest_quality,
    "weighted_average": choose_weighted_average,
    "most_expensive_first": choose_most_expensive,
}


def record_selection(
    task: Task,
    selector: str,
    candidates: list[Candidate],
    selected_service_id: str,
    reason: str,
    prompt_chars: int,
    completion_chars: int,
    parse_failure: bool,
) -> SelectionRecord:
    prefs = PREFERENCE_PROFILES[task.profile]
    utilities = utility_lookup(candidates, prefs)
    feasible_utilities = {
        c.vector.service_id: utilities[c.vector.service_id]
        for c in candidates
        if satisfies(task, c.vector)
    }
    if not feasible_utilities:
        feasible_utilities = utilities
    best_utility = max(feasible_utilities.values())
    selected = next((c for c in candidates if c.vector.service_id == selected_service_id), None)
    if selected is None:
        return SelectionRecord(
            task.task_id, task.taxonomy, task.profile, selector, selected_service_id, "",
            False, True, parse_failure, 0.0, best_utility, best_utility,
            0.0, 0.0, 0.0, prompt_chars, completion_chars, reason,
        )
    utility = utilities[selected.vector.service_id]
    violation = not satisfies(task, selected.vector)
    regret = max(best_utility - utility, 0.0)
    if violation:
        regret = best_utility
    return SelectionRecord(
        task.task_id,
        task.taxonomy,
        task.profile,
        selector,
        selected.vector.service_id,
        selected.vector.display_name,
        True,
        violation,
        parse_failure,
        round(utility, 4),
        round(best_utility, 4),
        round(regret, 4),
        selected.vector.cost_per_unit,
        selected.vector.latency_seconds,
        selected.vector.quality_score,
        prompt_chars,
        completion_chars,
        reason[:500],
    )


def summarize(records: list[SelectionRecord], generated_at: str, args: argparse.Namespace) -> dict[str, Any]:
    summary = {}
    for selector in sorted(set(r.selector for r in records)):
        rows = [r for r in records if r.selector == selector]
        summary[selector] = {
            "count": len(rows),
            "utility_mean": round(mean([r.utility for r in rows]), 4),
            "regret_mean": round(mean([r.regret for r in rows]), 4),
            "constraint_violation_rate": round(mean([1.0 if r.constraint_violation else 0.0 for r in rows]), 4),
            "parse_failure_rate": round(mean([1.0 if r.parse_failure else 0.0 for r in rows]), 4),
            "prompt_chars_mean": round(mean([r.prompt_chars for r in rows]), 1),
            "completion_chars_mean": round(mean([r.completion_chars for r in rows]), 1),
            "cost_mean": round(mean([r.cost_per_unit for r in rows]), 10),
            "latency_mean": round(mean([r.latency_seconds for r in rows]), 4),
            "quality_mean": round(mean([r.quality_score for r in rows]), 4),
        }
    return {
        "generated_at": generated_at,
        "tasks": args.tasks,
        "seed": args.seed,
        "provider": args.provider,
        "model": args.model,
        "ran_llm": bool(args.provider and args.model and os.environ.get(args.api_key_env)),
        "selectors": args.selectors,
        "runs_per_task": args.runs_per_task,
        "max_candidates": args.max_candidates,
        "summary": summary,
    }


def summarize_prompt_rows(prompt_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for selector in sorted(set(row["selector"] for row in prompt_rows)):
        rows = [row for row in prompt_rows if row["selector"] == selector]
        prompt_lengths = [len(row["prompt"]) for row in rows]
        summary[selector] = {
            "count": len(rows),
            "prompt_chars_mean": round(mean(prompt_lengths), 1),
            "prompt_chars_max": max(prompt_lengths) if prompt_lengths else 0,
            "estimated_prompt_tokens_mean": round(mean([n / 4 for n in prompt_lengths]), 1),
        }
    return summary


def summarize_fetch_events(fetch_events: list[SourceFetchEvent]) -> dict[str, Any]:
    if not fetch_events:
        return {"count": 0}
    return {
        "count": len(fetch_events),
        "unique_sources": len(set(e.source_url for e in fetch_events)),
        "cache_hit_rate": round(mean([1.0 if e.cache_hit else 0.0 for e in fetch_events]), 4),
        "unavailable_rate": round(mean([1.0 if e.status == "unavailable" else 0.0 for e in fetch_events]), 4),
        "returned_chars_mean": round(mean([e.returned_chars for e in fetch_events]), 1),
    }


def write_outputs(
    records: list[SelectionRecord],
    prompt_rows: list[dict[str, Any]],
    fetch_events: list[SourceFetchEvent],
    summary: dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if records:
        with (output_dir / "llm_selector_results.csv").open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(asdict(records[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(r) for r in records)
    with (output_dir / "llm_selector_prompts.jsonl").open("w", encoding="utf-8") as fp:
        for row in prompt_rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
    if fetch_events:
        with (output_dir / "llm_selector_source_fetches.csv").open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(asdict(fetch_events[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(e) for e in fetch_events)
    (output_dir / "llm_selector_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# LLM Raw-Doc vs ASM Manifest Selector",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Tasks: {summary['tasks']}",
        f"Provider/model: {summary['provider'] or 'none'} / {summary['model'] or 'none'}",
        f"Ran LLM: {summary['ran_llm']}",
        f"Prompt selectors: {', '.join(summary['selectors'])}",
        f"Runs per task: {summary['runs_per_task']}",
        f"Max candidates per task: {summary['max_candidates']}",
        f"Prompts generated: {len(prompt_rows)}",
        f"Raw-source fetch events: {len(fetch_events)}",
        "",
        "## Prompt Surface",
        "",
        "| Selector | Prompts | Mean prompt chars | Max prompt chars | Est. mean prompt tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for selector, stats in sorted(summary.get("prompt_summary", {}).items()):
        lines.append(
            f"| {selector} | {stats['count']} | {stats['prompt_chars_mean']:.1f} | "
            f"{stats['prompt_chars_max']} | {stats['estimated_prompt_tokens_mean']:.1f} |"
        )
    fetch_summary = summary.get("fetch_summary", {})
    if fetch_summary.get("count", 0):
        lines.extend(
            [
                "",
                "## Raw-Source Fetches",
                "",
                f"Unique sources: {fetch_summary['unique_sources']}",
                f"Cache hit rate: {fetch_summary['cache_hit_rate'] * 100:.1f}%",
                f"Unavailable rate: {fetch_summary['unavailable_rate'] * 100:.1f}%",
                f"Mean returned chars: {fetch_summary['returned_chars_mean']:.1f}",
            ]
        )
    lines.extend(
        [
            "",
            "## Selection Outcomes",
            "",
        "| Selector | Utility mean | Regret mean | Constraint violations | Parse failures | Prompt chars | Cost mean | Latency mean | Quality mean |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for selector, stats in sorted(summary["summary"].items(), key=lambda item: item[1]["regret_mean"]):
        lines.append(
            f"| {selector} | {stats['utility_mean']:.4f} | {stats['regret_mean']:.4f} | "
            f"{stats['constraint_violation_rate'] * 100:.1f}% | {stats['parse_failure_rate'] * 100:.1f}% | "
            f"{stats['prompt_chars_mean']:.1f} | {stats['cost_mean']:.10f} | "
            f"{stats['latency_mean']:.4f} | {stats['quality_mean']:.4f} |"
        )
    (output_dir / "llm_selector_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare LLM raw-doc selection against LLM ASM-manifest selection.")
    parser.add_argument("--manifests", type=Path, default=Path(__file__).resolve().parent.parent / "manifests")
    parser.add_argument("--tasks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-source-chars", type=int, default=12000)
    parser.add_argument(
        "--selectors",
        nargs="+",
        choices=["raw_doc", "manifest"],
        default=["raw_doc", "manifest"],
        help="LLM selector surfaces to generate/run.",
    )
    parser.add_argument("--runs-per-task", type=int, default=1)
    parser.add_argument("--no-heuristics", action="store_true", help="Do not include deterministic heuristic baselines.")
    parser.add_argument("--provider", choices=["openai"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).resolve().parent / "cache" / "raw_docs")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()

    manifests = load_manifests(args.manifests)
    candidate_map: dict[str, list[Candidate]] = {}
    for manifest in manifests:
        vector = parse_manifest(manifest)
        candidate_map.setdefault(vector.taxonomy, []).append(Candidate(manifest, vector))
    for taxonomy in list(candidate_map):
        candidate_map[taxonomy] = sorted(candidate_map[taxonomy], key=lambda c: c.vector.service_id)

    tasks = generate_tasks(candidate_map, args.tasks, args.seed)
    rng = random.Random(args.seed)
    api_key = os.environ.get(args.api_key_env)
    run_llm = bool(args.provider and args.model and api_key)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records: list[SelectionRecord] = []
    prompt_rows: list[dict[str, Any]] = []
    fetch_events: list[SourceFetchEvent] = []
    for task in tasks:
        candidates = candidate_map[task.taxonomy]
        if len(candidates) > args.max_candidates:
            candidates = rng.sample(candidates, args.max_candidates)
        topsis_choice = choose_topsis(task, candidates)
        records.append(record_selection(task, "asm_topsis", candidates, topsis_choice.vector.service_id, "deterministic TOPSIS", 0, 0, False))

        if not args.no_heuristics:
            for selector, chooser in HEURISTIC_SELECTORS.items():
                choice = chooser(task, candidates)
                records.append(record_selection(task, selector, candidates, choice.vector.service_id, selector, 0, 0, False))

        for selector in args.selectors:
            if selector == "raw_doc":
                prompt, events = build_raw_doc_prompt(task, candidates, args.cache_dir, args.max_source_chars)
                fetch_events.extend(events)
                record_selector = "llm_raw_doc"
            else:
                prompt = build_manifest_prompt(task, candidates)
                events = []
                record_selector = "llm_manifest"
            prompt_rows.append({
                "task": asdict(task),
                "selector": record_selector,
                "candidate_ids": [c.vector.service_id for c in candidates],
                "source_fetches": [asdict(e) for e in events],
                "prompt": prompt,
            })
            if not run_llm:
                continue
            for run_index in range(args.runs_per_task):
                if args.provider == "openai":
                    completion = call_openai_chat(prompt, args.model or "", api_key or "", args.temperature, args.openai_base_url)
                else:
                    raise ValueError(f"Unsupported provider: {args.provider}")
                service_id, reason, parse_failure = parse_llm_choice(completion)
                records.append(
                    record_selection(
                        task,
                        record_selector,
                        candidates,
                        service_id,
                        reason,
                        len(prompt),
                        len(completion),
                        parse_failure,
                    )
                )
                time.sleep(0.2)

    summary = summarize(records, generated_at, args)
    summary["prompt_summary"] = summarize_prompt_rows(prompt_rows)
    summary["fetch_summary"] = summarize_fetch_events(fetch_events)
    write_outputs(records, prompt_rows, fetch_events, summary, args.output_dir)
    print(json.dumps(summary, indent=2))
    if not run_llm:
        print(f"\nLLM calls skipped. Set --provider openai --model <model> and {args.api_key_env} to run selectors.")


if __name__ == "__main__":
    main()
