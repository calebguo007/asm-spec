#!/usr/bin/env python3
"""Preference-alignment evaluation for natural-language service requests.

This experiment tests the claim that ASM helps agents select the most suitable
service for a user, where "most suitable" is explicitly defined as:

  best feasible service under the user's stated constraints and preference
  vector.

The tasks are natural-language requests manually mapped to candidate services,
hard constraints, and soft preference weights. The evaluator compares
ASM-TOPSIS against common non-ASM baselines and reports regret:

  regret = utility(best feasible service) - utility(selected service)

Utility is the TOPSIS score under the task's preference vector. Lower regret is
better; zero regret means the selector chose the same service as ASM-TOPSIS for
that candidate set and preference vector.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (  # noqa: E402
    Constraints,
    Preferences,
    ServiceVector,
    load_manifests,
    parse_manifest,
    score_topsis,
    score_weighted_average,
)


@dataclass
class Task:
    task_id: int
    request: str
    taxonomy: str
    candidates: list[str]
    constraints: Constraints
    preferences: Preferences


@dataclass
class Record:
    task_id: int
    request: str
    taxonomy: str
    selector: str
    selected_service_id: str
    selected_display_name: str
    best_service_id: str
    best_display_name: str
    utility: float
    best_utility: float
    regret: float
    alignment_score: float
    constraint_violation: bool
    feasible_candidates: int
    cost_per_unit: float
    quality_score: float
    latency_seconds: float
    uptime: float
    reasoning: str


def finite_latency(value: float) -> float:
    return value if math.isfinite(value) else 1e9


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def parse_constraints(data: dict[str, Any], taxonomy: str) -> Constraints:
    return Constraints(
        min_quality=data.get("min_quality"),
        max_cost=data.get("max_cost"),
        max_latency_s=data.get("max_latency_s"),
        min_uptime=data.get("min_uptime"),
        required_taxonomy=taxonomy,
    )


def parse_preferences(data: dict[str, Any]) -> Preferences:
    return Preferences(
        cost=float(data.get("cost", 0.3)),
        quality=float(data.get("quality", 0.3)),
        speed=float(data.get("speed", 0.2)),
        reliability=float(data.get("reliability", 0.2)),
        io_ratio=float(data.get("io_ratio", 0.3)),
    )


def load_tasks(path: Path) -> list[Task]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = []
    for raw in payload["tasks"]:
        taxonomy = str(raw["taxonomy"])
        tasks.append(
            Task(
                task_id=int(raw["task_id"]),
                request=str(raw["request"]),
                taxonomy=taxonomy,
                candidates=list(raw["candidates"]),
                constraints=parse_constraints(raw.get("constraints") or {}, taxonomy),
                preferences=parse_preferences(raw["preferences"]),
            )
        )
    return tasks


def satisfies(service: ServiceVector, constraints: Constraints) -> bool:
    if constraints.required_taxonomy and service.taxonomy != constraints.required_taxonomy:
        return False
    if constraints.min_quality is not None and service.quality_score < constraints.min_quality:
        return False
    if constraints.max_cost is not None and service.cost_per_unit > constraints.max_cost:
        return False
    if constraints.max_latency_s is not None and finite_latency(service.latency_seconds) > constraints.max_latency_s:
        return False
    if constraints.min_uptime is not None and service.uptime < constraints.min_uptime:
        return False
    return True


def utility_map(services: list[ServiceVector], preferences: Preferences) -> dict[str, float]:
    return {row.service.service_id: row.total_score for row in score_topsis(services, preferences)}


def choose_topsis(services: list[ServiceVector], prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return score_topsis(services, prefs)[0].service


def choose_weighted_average(services: list[ServiceVector], prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return score_weighted_average(services, prefs)[0].service


def choose_cheapest(services: list[ServiceVector], _prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return min(services, key=lambda s: s.cost_per_unit)


def choose_fastest(services: list[ServiceVector], _prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return min(services, key=lambda s: finite_latency(s.latency_seconds))


def choose_highest_quality(services: list[ServiceVector], _prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return max(services, key=lambda s: s.quality_score)


def choose_highest_reliability(services: list[ServiceVector], _prefs: Preferences, _rng: random.Random) -> ServiceVector:
    return max(services, key=lambda s: s.uptime)


def choose_random(services: list[ServiceVector], _prefs: Preferences, rng: random.Random) -> ServiceVector:
    return rng.choice(services)


SELECTORS: dict[str, Callable[[list[ServiceVector], Preferences, random.Random], ServiceVector]] = {
    "asm_topsis": choose_topsis,
    "weighted_average": choose_weighted_average,
    "cheapest_first": choose_cheapest,
    "fastest_first": choose_fastest,
    "highest_quality_first": choose_highest_quality,
    "highest_reliability_first": choose_highest_reliability,
    "random": choose_random,
}


def selector_reason(selector: str, selected: ServiceVector, best: ServiceVector) -> str:
    if selector == "asm_topsis":
        return "Selected by constraint filtering plus preference-weighted TOPSIS."
    if selected.service_id == best.service_id:
        return f"{selector} matched the zero-regret ASM-TOPSIS choice for this request."
    return f"{selector} optimized a narrower rule and missed the preference-weighted best feasible service."


def evaluate_task(
    task: Task,
    manifest_map: dict[str, dict[str, Any]],
    rng: random.Random,
) -> list[Record]:
    vectors = []
    for service_id in task.candidates:
        if service_id not in manifest_map:
            raise ValueError(f"Task {task.task_id}: unknown service_id {service_id}")
        vectors.append(parse_manifest(manifest_map[service_id], io_ratio=task.preferences.io_ratio))

    feasible = [v for v in vectors if satisfies(v, task.constraints)]
    if not feasible:
        raise ValueError(f"Task {task.task_id}: no feasible candidates after constraints")

    utilities = utility_map(feasible, task.preferences)
    best = score_topsis(feasible, task.preferences)[0].service
    best_utility = utilities[best.service_id]
    records = []

    for selector, chooser in SELECTORS.items():
        selected = chooser(feasible, task.preferences, rng)
        utility = utilities[selected.service_id]
        regret = max(best_utility - utility, 0.0)
        alignment = utility / best_utility if best_utility > 0 else 1.0
        records.append(
            Record(
                task_id=task.task_id,
                request=task.request,
                taxonomy=task.taxonomy,
                selector=selector,
                selected_service_id=selected.service_id,
                selected_display_name=selected.display_name,
                best_service_id=best.service_id,
                best_display_name=best.display_name,
                utility=round(utility, 4),
                best_utility=round(best_utility, 4),
                regret=round(regret, 4),
                alignment_score=round(alignment, 4),
                constraint_violation=not satisfies(selected, task.constraints),
                feasible_candidates=len(feasible),
                cost_per_unit=selected.cost_per_unit,
                quality_score=selected.quality_score,
                latency_seconds=selected.latency_seconds,
                uptime=selected.uptime,
                reasoning=selector_reason(selector, selected, best),
            )
        )
    return records


def summarize(records: list[Record], generated_at: str, task_count: int, seed: int) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for selector in sorted({r.selector for r in records}):
        rows = [r for r in records if r.selector == selector]
        summary[selector] = {
            "count": len(rows),
            "utility_mean": round(mean([r.utility for r in rows]), 4),
            "regret_mean": round(mean([r.regret for r in rows]), 4),
            "alignment_score_mean": round(mean([r.alignment_score for r in rows]), 4),
            "zero_regret_rate": round(mean([1.0 if r.regret == 0 else 0.0 for r in rows]), 4),
            "constraint_violation_rate": round(mean([1.0 if r.constraint_violation else 0.0 for r in rows]), 4),
            "cost_mean": round(mean([r.cost_per_unit for r in rows]), 10),
            "quality_mean": round(mean([r.quality_score for r in rows]), 4),
            "latency_mean": round(mean([r.latency_seconds for r in rows]), 4),
        }
    return {
        "generated_at": generated_at,
        "task_count": task_count,
        "seed": seed,
        "definition": "Most suitable = best feasible service under the user's stated constraints and preference vector.",
        "summary": summary,
    }


def write_outputs(records: list[Record], summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "preference_alignment.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(r) for r in records)

    (output_dir / "preference_alignment.json").write_text(
        json.dumps({"summary": summary, "records": [asdict(r) for r in records]}, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Preference Alignment Evaluation",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Tasks: {summary['task_count']}",
        f"Seed: {summary['seed']}",
        "",
        summary["definition"],
        "",
        "Regret is `utility(best feasible service) - utility(selected service)`, where utility is the TOPSIS score under the task-specific preference vector. Lower is better; zero means the selector found the most suitable service under the explicit user preference model.",
        "",
        "## Aggregate Results",
        "",
        "| Selector | Utility mean | Regret mean | Alignment mean | Zero-regret rate | Constraint violations | Cost mean | Quality mean | Latency mean |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for selector, stats in sorted(summary["summary"].items(), key=lambda item: item[1]["regret_mean"]):
        lines.append(
            f"| {selector} | {stats['utility_mean']:.4f} | {stats['regret_mean']:.4f} | "
            f"{stats['alignment_score_mean']:.4f} | {stats['zero_regret_rate'] * 100:.1f}% | "
            f"{stats['constraint_violation_rate'] * 100:.1f}% | {stats['cost_mean']:.10f} | "
            f"{stats['quality_mean']:.4f} | {stats['latency_mean']:.4f} |"
        )

    lines.extend([
        "",
        "## Per-Request ASM Choices",
        "",
        "| Task | User request | ASM selected | Feasible candidates |",
        "|---:|---|---|---:|",
    ])
    asm_rows = [r for r in records if r.selector == "asm_topsis"]
    for row in sorted(asm_rows, key=lambda r: r.task_id):
        request = row.request.replace("|", "/")
        lines.append(
            f"| {row.task_id} | {request} | {row.selected_display_name} (`{row.selected_service_id}`) | "
            f"{row.feasible_candidates} |"
        )

    (output_dir / "preference_alignment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(tasks_file: Path, manifests_dir: Path, output_dir: Path, seed: int) -> dict[str, Any]:
    tasks = load_tasks(tasks_file)
    manifests = load_manifests(manifests_dir)
    manifest_map = {m["service_id"]: m for m in manifests}
    rng = random.Random(seed)
    records: list[Record] = []
    for task in tasks:
        records.extend(evaluate_task(task, manifest_map, rng))

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = summarize(records, generated_at, len(tasks), seed)
    write_outputs(records, summary, output_dir)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate service selectors against natural-language user preferences.")
    parser.add_argument("--tasks-file", type=Path, default=Path(__file__).resolve().parent / "preference_alignment_tasks.json")
    parser.add_argument("--manifests", type=Path, default=Path(__file__).resolve().parent.parent / "manifests")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--seed", type=int, default=2024)
    args = parser.parse_args()

    summary = run(args.tasks_file, args.manifests, args.output_dir, args.seed)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
