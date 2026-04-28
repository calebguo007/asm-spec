#!/usr/bin/env python3
"""Compare ASM-TOPSIS against stronger deterministic selection baselines.

This experiment avoids the "TOPSIS beats random" strawman by adding common
single-objective heuristics and reporting regret against the best feasible
service under each task's preference vector.

Outputs:
  experiments/results/selection_baselines.csv
  experiments/results/selection_baselines.json
  experiments/results/selection_baselines.md
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (  # noqa: E402
    Preferences,
    ServiceVector,
    load_manifests,
    parse_manifest,
    score_topsis,
    score_weighted_average,
)


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


@dataclass
class Record:
    task_id: int
    taxonomy: str
    profile: str
    strategy: str
    service_id: str
    display_name: str
    utility: float
    best_utility: float
    regret: float
    cost_per_unit: float
    latency_seconds: float
    quality_score: float
    uptime: float


def utility_map(services: list[ServiceVector], preferences: Preferences) -> dict[str, float]:
    return {r.service.service_id: r.total_score for r in score_topsis(services, preferences)}


def choose_topsis(services: list[ServiceVector], preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return score_topsis(services, preferences)[0].service


def choose_weighted_average(services: list[ServiceVector], preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return score_weighted_average(services, preferences)[0].service


def choose_random(services: list[ServiceVector], _preferences: Preferences, rng: random.Random) -> ServiceVector:
    return rng.choice(services)


def choose_cheapest(services: list[ServiceVector], _preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return min(services, key=lambda s: s.cost_per_unit)


def choose_fastest(services: list[ServiceVector], _preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return min(services, key=lambda s: s.latency_seconds)


def choose_highest_quality(services: list[ServiceVector], _preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return max(services, key=lambda s: s.quality_score)


def choose_most_expensive(services: list[ServiceVector], _preferences: Preferences, _rng: random.Random) -> ServiceVector:
    return max(services, key=lambda s: s.cost_per_unit)


STRATEGIES: dict[str, Callable[[list[ServiceVector], Preferences, random.Random], ServiceVector]] = {
    "asm_topsis": choose_topsis,
    "weighted_average": choose_weighted_average,
    "cheapest_first": choose_cheapest,
    "fastest_first": choose_fastest,
    "highest_quality_first": choose_highest_quality,
    "most_expensive_first": choose_most_expensive,
    "random": choose_random,
}


def generate_tasks(taxonomy_map: dict[str, list[ServiceVector]], count: int, rng: random.Random) -> list[Task]:
    taxonomies = sorted(tax for tax, services in taxonomy_map.items() if len(services) >= 2)
    profiles = sorted(PREFERENCE_PROFILES)
    if not taxonomies:
        raise ValueError("Need at least one taxonomy with two or more services")
    return [
        Task(
            task_id=i + 1,
            taxonomy=rng.choice(taxonomies),
            profile=rng.choice(profiles),
        )
        for i in range(count)
    ]


def run(manifests: list[dict], task_count: int, seed: int) -> list[Record]:
    rng = random.Random(seed)
    services = [parse_manifest(m) for m in manifests]
    taxonomy_map: dict[str, list[ServiceVector]] = {}
    for service in services:
        taxonomy_map.setdefault(service.taxonomy, []).append(service)

    tasks = generate_tasks(taxonomy_map, task_count, rng)
    records: list[Record] = []

    for task in tasks:
        candidates = taxonomy_map[task.taxonomy]
        preferences = PREFERENCE_PROFILES[task.profile]
        utilities = utility_map(candidates, preferences)
        best_utility = max(utilities.values())

        for name, chooser in STRATEGIES.items():
            selected = chooser(candidates, preferences, rng)
            utility = utilities[selected.service_id]
            records.append(
                Record(
                    task_id=task.task_id,
                    taxonomy=task.taxonomy,
                    profile=task.profile,
                    strategy=name,
                    service_id=selected.service_id,
                    display_name=selected.display_name,
                    utility=round(utility, 4),
                    best_utility=round(best_utility, 4),
                    regret=round(max(best_utility - utility, 0.0), 4),
                    cost_per_unit=selected.cost_per_unit,
                    latency_seconds=selected.latency_seconds,
                    quality_score=selected.quality_score,
                    uptime=selected.uptime,
                )
            )
    return records


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(records: list[Record], generated_at: str, task_count: int, seed: int) -> dict:
    strategies = sorted(set(r.strategy for r in records))
    summary = {}
    for strategy in strategies:
        rows = [r for r in records if r.strategy == strategy]
        summary[strategy] = {
            "count": len(rows),
            "utility_mean": round(mean([r.utility for r in rows]), 4),
            "regret_mean": round(mean([r.regret for r in rows]), 4),
            "zero_regret_rate": round(mean([1.0 if r.regret == 0 else 0.0 for r in rows]), 4),
            "cost_mean": round(mean([r.cost_per_unit for r in rows]), 10),
            "latency_mean": round(mean([r.latency_seconds for r in rows]), 4),
            "quality_mean": round(mean([r.quality_score for r in rows]), 4),
        }
    return {
        "generated_at": generated_at,
        "task_count": task_count,
        "seed": seed,
        "strategy_count": len(strategies),
        "summary": summary,
    }


def write_outputs(records: list[Record], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "selection_baselines.csv"
    json_path = output_dir / "selection_baselines.json"
    md_path = output_dir / "selection_baselines.md"

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(r) for r in records)

    json_path.write_text(
        json.dumps({"summary": summary, "records": [asdict(r) for r in records]}, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Selection Baseline and Regret Evaluation",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Tasks: {summary['task_count']}",
        f"Seed: {summary['seed']}",
        "",
        "Regret is computed as `utility(best feasible service) - utility(selected service)` under the task's preference vector. Lower is better; zero means the strategy selected a utility-optimal service for that candidate set.",
        "",
        "| Strategy | Utility mean | Regret mean | Zero-regret rate | Cost mean | Latency mean | Quality mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy, stats in sorted(summary["summary"].items(), key=lambda item: item[1]["regret_mean"]):
        lines.append(
            f"| {strategy} | {stats['utility_mean']:.4f} | {stats['regret_mean']:.4f} | "
            f"{stats['zero_regret_rate'] * 100:.1f}% | {stats['cost_mean']:.10f} | "
            f"{stats['latency_mean']:.4f} | {stats['quality_mean']:.4f} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ASM selection against stronger heuristic baselines.")
    parser.add_argument("--manifests", type=Path, default=Path(__file__).resolve().parent.parent / "manifests")
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()

    manifests = load_manifests(args.manifests)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = run(manifests, args.tasks, args.seed)
    summary = summarize(records, generated_at, args.tasks, args.seed)
    write_outputs(records, summary, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
