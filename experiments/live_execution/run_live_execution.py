#!/usr/bin/env python3
"""Live execution: ASM-selected vs heuristic vs LLM-selected, real Chinese-LLM gateway.

Calls the TokenDance OpenAI-compatible gateway with the actually-selected model
and records realised cost (from token usage), realised latency (wall clock),
realised quality (independent judge model on a 1-10 scale), and constraint
violations (against per-task max_cost / max_latency / min_quality).

This is the §6.5b live-execution evidence: ASM's manifest-declared values, when
TOPSIS-driven selection is followed by actual API calls, predict realised
outcomes. If ASM-TOPSIS outperforms heuristics on regret across realised
outcomes, the protocol's value claim transfers from synthetic to live.

Run:
    DEEPSEEK_API_KEY=sk-... python experiments/live_execution/run_live_execution.py \
        --base-url https://tokendance.space/gateway/v1 \
        --judge-model glm-4.7
"""

from __future__ import annotations

import argparse
import csv
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
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent.parent
SCORER_DIR = str(ROOT / "scorer")
if SCORER_DIR not in sys.path:
    sys.path.insert(0, SCORER_DIR)

from scorer import (  # noqa: E402
    Preferences,
    ServiceVector,
    load_manifests,
    parse_manifest,
    score_topsis,
    score_weighted_average,
)


# ---------------------------------------------------------------------------
# Constants

HERE = Path(__file__).resolve().parent
TASKS_PATH = HERE / "tasks.json"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Map our manifest service_id -> TokenDance gateway model name.
SERVICE_TO_MODEL: dict[str, str] = {
    "deepseek/deepseek-v4-flash@4.0": "deepseek-v4-flash",
    "qwen/qwen3-max@3.0": "qwen3-max",
    "moonshot/kimi-k2.5@2.5": "kimi-k2.5",
    "zhipu/glm-5@5.0": "glm-5",
    "minimax/m2.7@2.7": "minimax-m2.7",
}

MODEL_TO_SERVICE: dict[str, str] = {model: service_id for service_id, model in SERVICE_TO_MODEL.items()}

AXIS_TO_PREFS: dict[str, Preferences] = {
    "cost":     Preferences(cost=0.55, quality=0.20, speed=0.15, reliability=0.10),
    "latency":  Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
    "quality":  Preferences(cost=0.15, quality=0.55, speed=0.15, reliability=0.15),
    "balanced": Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
}

JUDGE_PROMPT = (
    "You are an independent quality judge. Below is a task and a model response. "
    "Score the response from 1 to 10 on a single scale combining:\n"
    "- Faithfulness to the task instructions (e.g., output-only constraints).\n"
    "- Technical correctness for code, accuracy for translation, factual fidelity for summary.\n"
    "- Style appropriate to the task category.\n"
    "Output STRICT JSON only with shape {\"score\": <int 1..10>, \"rationale\": \"<one sentence>\"}. "
    "No prose, no markdown fence."
)


@dataclass
class Selection:
    selector: str
    service_id: str
    selection_reason: str = ""
    picker_prompt_tokens: int = 0
    picker_completion_tokens: int = 0
    picker_cost_usd: float = 0.0
    picker_latency_s: float = 0.0
    picker_error: str = ""


@dataclass
class CallResult:
    success: bool
    response_text: str
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    error: str = ""


@dataclass
class TaskResult:
    task_id: int
    category: str
    preference_axis: str
    selector: str
    service_id: str
    selection_reason: str
    response_text: str
    judge_score: float
    judge_rationale: str
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    execution_cost_usd: float
    picker_prompt_tokens: int
    picker_completion_tokens: int
    picker_cost_usd: float
    picker_latency_s: float
    judge_prompt_tokens: int
    judge_completion_tokens: int
    judge_cost_usd: float
    total_known_cost_usd: float
    cost_accounting_note: str
    cost_violation: bool
    latency_violation: bool
    quality_violation: bool
    success: bool
    error: str = ""


# ---------------------------------------------------------------------------
# Gateway client

def call_gateway(model: str, prompt: str, api_key: str, base_url: str,
                 temperature: float = 0.0, timeout: int = 120) -> dict:
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Pricing → realised cost

def cost_for_call(manifest: dict, prompt_tokens: int, completion_tokens: int) -> float:
    """Compute realised USD cost from manifest pricing and observed token counts."""
    pricing = manifest.get("pricing") or {}
    input_per_1m = output_per_1m = 0.0
    for dim in pricing.get("billing_dimensions", []):
        d = dim.get("dimension")
        unit = dim.get("unit")
        cost = float(dim.get("cost_per_unit", 0))
        if d == "input_token" and unit in ("per_1M", "per_1m"):
            input_per_1m = cost
        elif d == "output_token" and unit in ("per_1M", "per_1m"):
            output_per_1m = cost
    return prompt_tokens * input_per_1m / 1_000_000 + completion_tokens * output_per_1m / 1_000_000


def usage_tokens(response: dict) -> tuple[int, int]:
    usage = response.get("usage") or {}
    return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def manifest_for_gateway_model(model: str, manifest_map: dict[str, dict]) -> dict | None:
    service_id = MODEL_TO_SERVICE.get(model)
    if service_id is None:
        return None
    return manifest_map.get(service_id)


def cost_for_gateway_model(
    model: str,
    manifest_map: dict[str, dict],
    prompt_tokens: int,
    completion_tokens: int,
) -> tuple[float, str]:
    manifest = manifest_for_gateway_model(model, manifest_map)
    if manifest is None:
        return 0.0, f"no manifest pricing for gateway model {model}"
    return cost_for_call(manifest, prompt_tokens, completion_tokens), ""


# ---------------------------------------------------------------------------
# Selectors

def feasible_under_constraints(task: dict, candidates: list[dict]) -> list[dict]:
    """Filter candidates by hard constraints inferred from manifest declared values.
    For latency, use sla.latency_p50 parsed to seconds. For cost, use a heuristic
    derived from manifest pricing under a typical 800-input / 800-output token mix.
    Quality uses the normalised quality score from the parsed ServiceVector.
    """
    out = []
    for c in candidates:
        v = c["vector"]
        if task.get("max_latency_s") is not None:
            if v.latency_seconds > float(task["max_latency_s"]):
                continue
        if task.get("max_cost_usd") is not None:
            estimated_cost = cost_for_call(c["manifest"], 800, 800)
            if estimated_cost > float(task["max_cost_usd"]):
                continue
        if task.get("min_quality_score") is not None:
            min_q = float(task["min_quality_score"]) / 10.0
            if v.quality_score < min_q:
                continue
        out.append(c)
    return out or candidates  # fall back to all if filter is too strict


def selector_topsis(task: dict, candidates: list[dict]) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    prefs = AXIS_TO_PREFS[task["preference_axis"]]
    ranked = score_topsis([c["vector"] for c in pool], prefs)
    return Selection("asm_topsis", ranked[0].service.service_id, "deterministic TOPSIS")


def selector_random(task: dict, candidates: list[dict], rng: random.Random) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    pick = rng.choice(pool)
    return Selection("random", pick["vector"].service_id, "uniform random")


def selector_cheapest(task: dict, candidates: list[dict]) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    pick = min(pool, key=lambda c: cost_for_call(c["manifest"], 800, 800))
    return Selection("cheapest_first", pick["vector"].service_id, "minimum estimated cost")


def selector_weighted_average(task: dict, candidates: list[dict]) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    prefs = AXIS_TO_PREFS[task["preference_axis"]]
    ranked = score_weighted_average([c["vector"] for c in pool], prefs)
    return Selection("weighted_average", ranked[0].service.service_id, "additive weighted score")


def selector_llm_with_manifest(task: dict, candidates: list[dict],
                                api_key: str, base_url: str, picker_model: str,
                                manifest_map: dict[str, dict]) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    # Compact manifests for the picker prompt.
    compact = []
    for c in pool:
        m = c["manifest"]
        compact.append({
            "service_id": m["service_id"],
            "display_name": m.get("display_name"),
            "pricing": m.get("pricing"),
            "quality": m.get("quality"),
            "sla": m.get("sla"),
        })
    prompt = (
        "You are an LLM selector. Pick exactly one service_id from the candidates that best "
        f"satisfies preference axis '{task['preference_axis']}' for the task below.\n\n"
        f"Constraints: max_cost_usd={task.get('max_cost_usd')}, max_latency_s={task.get('max_latency_s')}, "
        f"min_quality_score={task.get('min_quality_score')}.\n\n"
        f"Candidates (ASM manifests):\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n\n"
        f"Task:\n{task['prompt'][:600]}\n\n"
        "Reply STRICT JSON only: {\"service_id\": \"<picked id>\", \"reason\": \"<one sentence>\"}."
    )
    try:
        t0 = time.monotonic()
        result = call_gateway(picker_model, prompt, api_key, base_url, temperature=0.0)
        picker_latency_s = time.monotonic() - t0
        picker_prompt_tokens, picker_completion_tokens = usage_tokens(result)
        picker_cost_usd, picker_note = cost_for_gateway_model(
            picker_model, manifest_map, picker_prompt_tokens, picker_completion_tokens
        )
        text = result["choices"][0]["message"]["content"]
        cleaned = re.sub(r"^```(?:json)?", "", text.strip()).rstrip("```").strip()
        obj = json.loads(cleaned)
        sid = str(obj.get("service_id", "")).strip()
        if sid not in {c["vector"].service_id for c in pool}:
            sid = pool[0]["vector"].service_id
        return Selection(
            "llm_picker_manifest",
            sid,
            str(obj.get("reason", ""))[:200],
            picker_prompt_tokens=picker_prompt_tokens,
            picker_completion_tokens=picker_completion_tokens,
            picker_cost_usd=round(picker_cost_usd, 8),
            picker_latency_s=round(picker_latency_s, 3),
            picker_error=picker_note,
        )
    except Exception as exc:
        return Selection("llm_picker_manifest", pool[0]["vector"].service_id, f"fallback: {exc}", picker_error=str(exc)[:300])


def selector_llm_with_description(task: dict, candidates: list[dict],
                                  api_key: str, base_url: str, picker_model: str,
                                  manifest_map: dict[str, dict]) -> Selection:
    pool = feasible_under_constraints(task, candidates)
    snippets = []
    for c in pool:
        m = c["manifest"]
        snippets.append(
            f"service_id: {m['service_id']}\n"
            f"display_name: {m.get('display_name')}\n"
            f"description: {m.get('capabilities', {}).get('description', '')}\n"
            f"provider_url: {m.get('provider', {}).get('url', '')}"
        )
    prompt = (
        "You are an LLM selector. Pick exactly one service_id from the candidates that best "
        f"satisfies preference axis '{task['preference_axis']}' for the task below. "
        "You only have informal descriptions; quantitative metadata is not available.\n\n"
        f"Candidates:\n" + "\n---\n".join(snippets) + "\n\n"
        f"Task:\n{task['prompt'][:600]}\n\n"
        "Reply STRICT JSON only: {\"service_id\": \"<picked id>\", \"reason\": \"<one sentence>\"}."
    )
    try:
        t0 = time.monotonic()
        result = call_gateway(picker_model, prompt, api_key, base_url, temperature=0.0)
        picker_latency_s = time.monotonic() - t0
        picker_prompt_tokens, picker_completion_tokens = usage_tokens(result)
        picker_cost_usd, picker_note = cost_for_gateway_model(
            picker_model, manifest_map, picker_prompt_tokens, picker_completion_tokens
        )
        text = result["choices"][0]["message"]["content"]
        cleaned = re.sub(r"^```(?:json)?", "", text.strip()).rstrip("```").strip()
        obj = json.loads(cleaned)
        sid = str(obj.get("service_id", "")).strip()
        if sid not in {c["vector"].service_id for c in pool}:
            sid = pool[0]["vector"].service_id
        return Selection(
            "llm_picker_description",
            sid,
            str(obj.get("reason", ""))[:200],
            picker_prompt_tokens=picker_prompt_tokens,
            picker_completion_tokens=picker_completion_tokens,
            picker_cost_usd=round(picker_cost_usd, 8),
            picker_latency_s=round(picker_latency_s, 3),
            picker_error=picker_note,
        )
    except Exception as exc:
        return Selection("llm_picker_description", pool[0]["vector"].service_id, f"fallback: {exc}", picker_error=str(exc)[:300])


# ---------------------------------------------------------------------------
# Judge

def judge_call(task_prompt: str, response_text: str, api_key: str, base_url: str,
               judge_model: str, manifest_map: dict[str, dict]) -> tuple[float, str, int, int, float, str]:
    prompt = (
        f"{JUDGE_PROMPT}\n\n"
        f"---TASK---\n{task_prompt[:1200]}\n\n"
        f"---RESPONSE---\n{response_text[:2000]}\n\n"
        f"Score:"
    )
    try:
        result = call_gateway(judge_model, prompt, api_key, base_url, temperature=0.0)
        judge_prompt_tokens, judge_completion_tokens = usage_tokens(result)
        judge_cost_usd, judge_note = cost_for_gateway_model(
            judge_model, manifest_map, judge_prompt_tokens, judge_completion_tokens
        )
        text = result["choices"][0]["message"]["content"]
        cleaned = re.sub(r"^```(?:json)?", "", text.strip()).rstrip("```").strip()
        m = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)
        obj = json.loads(cleaned)
        score = float(obj.get("score", 0))
        rationale = str(obj.get("rationale", ""))[:200]
        return score, rationale, judge_prompt_tokens, judge_completion_tokens, round(judge_cost_usd, 8), judge_note
    except Exception as exc:
        return 0.0, f"judge_error: {exc}", 0, 0, 0.0, str(exc)[:300]


# ---------------------------------------------------------------------------
# Main loop

def run_task(task: dict, selection: Selection, manifest_map: dict[str, dict],
             api_key: str, base_url: str, judge_model: str) -> TaskResult:
    service_id = selection.service_id
    manifest = manifest_map[service_id]
    model_name = SERVICE_TO_MODEL.get(service_id)
    if model_name is None:
        return TaskResult(
            task_id=task["id"], category=task["category"],
            preference_axis=task["preference_axis"], selector=selection.selector,
            service_id=service_id, selection_reason=selection.selection_reason,
            response_text="", judge_score=0.0, judge_rationale="",
            latency_s=0.0, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
            execution_cost_usd=0.0,
            picker_prompt_tokens=selection.picker_prompt_tokens,
            picker_completion_tokens=selection.picker_completion_tokens,
            picker_cost_usd=selection.picker_cost_usd,
            picker_latency_s=selection.picker_latency_s,
            judge_prompt_tokens=0,
            judge_completion_tokens=0,
            judge_cost_usd=0.0,
            total_known_cost_usd=selection.picker_cost_usd,
            cost_accounting_note=selection.picker_error,
            cost_violation=False, latency_violation=False, quality_violation=False,
            success=False, error=f"no gateway model mapping for {service_id}",
        )

    t0 = time.monotonic()
    try:
        gateway_response = call_gateway(model_name, task["prompt"], api_key, base_url, temperature=0.0)
        latency_s = time.monotonic() - t0
        msg = gateway_response["choices"][0]["message"]
        response_text = msg.get("content") or msg.get("reasoning_content") or ""
        usage = gateway_response.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        success = True
        error = ""
    except Exception as exc:
        latency_s = time.monotonic() - t0
        return TaskResult(
            task_id=task["id"], category=task["category"],
            preference_axis=task["preference_axis"], selector=selection.selector,
            service_id=service_id, selection_reason=selection.selection_reason,
            response_text="", judge_score=0.0, judge_rationale="",
            latency_s=latency_s, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
            execution_cost_usd=0.0,
            picker_prompt_tokens=selection.picker_prompt_tokens,
            picker_completion_tokens=selection.picker_completion_tokens,
            picker_cost_usd=selection.picker_cost_usd,
            picker_latency_s=selection.picker_latency_s,
            judge_prompt_tokens=0,
            judge_completion_tokens=0,
            judge_cost_usd=0.0,
            total_known_cost_usd=selection.picker_cost_usd,
            cost_accounting_note=selection.picker_error,
            cost_violation=False, latency_violation=False, quality_violation=False,
            success=False, error=str(exc)[:400],
        )

    execution_cost_usd = cost_for_call(manifest, prompt_tokens, completion_tokens)
    judge_score, judge_rationale, judge_prompt_tokens, judge_completion_tokens, judge_cost_usd, judge_note = judge_call(
        task["prompt"], response_text, api_key, base_url, judge_model, manifest_map
    )
    total_known_cost_usd = execution_cost_usd + selection.picker_cost_usd + judge_cost_usd
    cost_accounting_note = "; ".join(note for note in [selection.picker_error, judge_note] if note)

    cost_violation = task.get("max_cost_usd") is not None and execution_cost_usd > float(task["max_cost_usd"])
    latency_violation = task.get("max_latency_s") is not None and latency_s > float(task["max_latency_s"])
    quality_violation = task.get("min_quality_score") is not None and judge_score < float(task["min_quality_score"])

    return TaskResult(
        task_id=task["id"], category=task["category"],
        preference_axis=task["preference_axis"], selector=selection.selector,
        service_id=service_id, selection_reason=selection.selection_reason,
        response_text=response_text[:2000], judge_score=judge_score, judge_rationale=judge_rationale,
        latency_s=round(latency_s, 3),
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        cost_usd=round(execution_cost_usd, 8),
        execution_cost_usd=round(execution_cost_usd, 8),
        picker_prompt_tokens=selection.picker_prompt_tokens,
        picker_completion_tokens=selection.picker_completion_tokens,
        picker_cost_usd=selection.picker_cost_usd,
        picker_latency_s=selection.picker_latency_s,
        judge_prompt_tokens=judge_prompt_tokens,
        judge_completion_tokens=judge_completion_tokens,
        judge_cost_usd=judge_cost_usd,
        total_known_cost_usd=round(total_known_cost_usd, 8),
        cost_accounting_note=cost_accounting_note,
        cost_violation=cost_violation, latency_violation=latency_violation,
        quality_violation=quality_violation,
        success=success, error=error,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Live execution of selectors against TokenDance gateway")
    parser.add_argument("--tasks-file", type=Path, default=TASKS_PATH)
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--base-url", default="https://tokendance.space/gateway/v1")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--judge-model", default="glm-4.7")
    parser.add_argument("--picker-model", default="qwen3-max",
                        help="Model used by the LLM-picker selectors (manifest + description surfaces).")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--selectors", nargs="+",
                        default=["asm_topsis", "random", "cheapest_first", "weighted_average",
                                 "llm_picker_manifest", "llm_picker_description"])
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N tasks (for smoke tests).")
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        sys.exit(f"Set ${args.api_key_env} before running.")

    rng = random.Random(args.seed)

    tasks_data = json.loads(args.tasks_file.read_text(encoding="utf-8"))
    tasks = tasks_data["tasks"]
    if args.limit:
        tasks = tasks[: args.limit]
    candidate_ids = tasks_data["candidates"]

    manifests = load_manifests(args.manifests)
    manifest_map: dict[str, dict] = {m["service_id"]: m for m in manifests}
    candidates: list[dict] = []
    for cid in candidate_ids:
        m = manifest_map[cid]
        candidates.append({"manifest": m, "vector": parse_manifest(m)})

    results: list[TaskResult] = []
    total = len(tasks) * len(args.selectors)
    done = 0
    for task in tasks:
        for selector_name in args.selectors:
            done += 1
            if selector_name == "asm_topsis":
                sel = selector_topsis(task, candidates)
            elif selector_name == "random":
                sel = selector_random(task, candidates, rng)
            elif selector_name == "cheapest_first":
                sel = selector_cheapest(task, candidates)
            elif selector_name == "weighted_average":
                sel = selector_weighted_average(task, candidates)
            elif selector_name == "llm_picker_manifest":
                sel = selector_llm_with_manifest(task, candidates, api_key, args.base_url, args.picker_model, manifest_map)
            elif selector_name in {"llm_picker_description", "llm_picker_raw_doc"}:
                sel = selector_llm_with_description(task, candidates, api_key, args.base_url, args.picker_model, manifest_map)
            else:
                continue
            print(f"  [{done}/{total}] task={task['id']:>2} axis={task['preference_axis']:<8} "
                  f"selector={selector_name:<20} -> {sel.service_id}", flush=True)
            r = run_task(task, sel, manifest_map, api_key, args.base_url, args.judge_model)
            results.append(r)
            time.sleep(0.4)  # gentle rate limiting

    # CSV
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "live_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    # Summary by selector
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks_run": len(tasks),
        "selectors": {},
    }
    for sel_name in sorted({r.selector for r in results}):
        rows = [r for r in results if r.selector == sel_name and r.success]
        if not rows:
            continue
        summary["selectors"][sel_name] = {
            "n": len(rows),
            "judge_score_mean": round(sum(r.judge_score for r in rows) / len(rows), 3),
            "execution_cost_total_usd": round(sum(r.execution_cost_usd for r in rows), 6),
            "execution_cost_mean_usd": round(sum(r.execution_cost_usd for r in rows) / len(rows), 8),
            "picker_cost_total_usd": round(sum(r.picker_cost_usd for r in rows), 6),
            "judge_cost_total_usd": round(sum(r.judge_cost_usd for r in rows), 6),
            "known_total_cost_usd": round(sum(r.total_known_cost_usd for r in rows), 6),
            "known_total_cost_mean_usd": round(sum(r.total_known_cost_usd for r in rows) / len(rows), 8),
            # Backward-compatible aliases for existing analysis notebooks: execution cost only.
            "cost_total_usd": round(sum(r.execution_cost_usd for r in rows), 6),
            "cost_mean_usd": round(sum(r.execution_cost_usd for r in rows) / len(rows), 8),
            "latency_mean_s": round(sum(r.latency_s for r in rows) / len(rows), 3),
            "picker_latency_mean_s": round(sum(r.picker_latency_s for r in rows) / len(rows), 3),
            "cost_violation_rate": round(sum(1 for r in rows if r.cost_violation) / len(rows), 3),
            "latency_violation_rate": round(sum(1 for r in rows if r.latency_violation) / len(rows), 3),
            "quality_violation_rate": round(sum(1 for r in rows if r.quality_violation) / len(rows), 3),
        }
    summary_path = args.output_dir / "live_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown report
    lines = [
        "# Live Execution: Chinese-LLM gateway",
        "",
        f"Generated: {summary['generated_at']}",
        f"Tasks: {summary['tasks_run']}",
        f"Gateway: {args.base_url}",
        f"Judge model: {args.judge_model}",
        f"LLM-picker model: {args.picker_model}",
        "",
        "## Aggregate by selector",
        "",
        "`Execution cost` is only the selected model's task call. `Known total cost` adds priced selector and judge calls when the gateway model has a matching ASM manifest; missing judge pricing is noted in the CSV.",
        "",
        "| Selector | n | Judge mean | Execution cost | Picker cost | Judge cost | Known total | Mean latency (s) | Cost-viol | Latency-viol | Quality-viol |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sel_name, stats in sorted(summary["selectors"].items(), key=lambda kv: -kv[1]["judge_score_mean"]):
        lines.append(
            f"| {sel_name} | {stats['n']} | {stats['judge_score_mean']:.2f} | "
            f"${stats['execution_cost_total_usd']:.4f} | ${stats['picker_cost_total_usd']:.4f} | "
            f"${stats['judge_cost_total_usd']:.4f} | ${stats['known_total_cost_usd']:.4f} | "
            f"{stats['latency_mean_s']:.2f} | "
            f"{stats['cost_violation_rate']*100:.0f}% | {stats['latency_violation_rate']*100:.0f}% | "
            f"{stats['quality_violation_rate']*100:.0f}% |"
        )
    (args.output_dir / "live_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
