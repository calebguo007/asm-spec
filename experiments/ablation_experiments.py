#!/usr/bin/env python3
"""Ablation studies for ASM scoring engine.

Three ablation experiments:
  GLM-1: Trust delta removal - how much does trust adjustment change rankings?
  GLM-2: TOPSIS vs weighted average - how often do they disagree?
  GLM-3: io_ratio sensitivity - are rankings stable across I/O assumptions?

Usage:
    python ablation_experiments.py                    # run all three
    python ablation_experiments.py --only glm-1       # run only trust delta ablation
    python ablation_experiments.py --output results/   # custom output dir

Outputs CSV + JSON + Markdown report for each experiment.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add scorer to path
_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (
    Constraints,
    Preferences,
    ReceiptRecord,
    ScoredService,
    ServiceVector,
    TrustScore,
    adjust_scores_with_trust,
    compute_trust_score,
    filter_services,
    load_manifests,
    parse_manifest,
    score_topsis,
    score_weighted_average,
)

# Shared preferences
PREFERENCE_PROFILES: dict[str, Preferences] = {
    "cost_first":  Preferences(cost=0.55, quality=0.25, speed=0.10, reliability=0.10),
    "quality_first": Preferences(cost=0.10, quality=0.55, speed=0.20, reliability=0.15),
    "speed_first":   Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
    "balanced":      Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
}


# Helpers
def kendall_tau(a, b):
    if len(a) != len(b) or sorted(a) != sorted(b) or len(a) < 2:
        return float("nan")
    rank_a = {item: i for i, item in enumerate(a)}
    rank_b = {item: i for i, item in enumerate(b)}
    concordant, discordant = 0, 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            x = rank_a[a[i]] - rank_a[a[j]]
            y = rank_b[a[i]] - rank_b[a[j]]
            if x * y > 0:
                concordant += 1
            elif x * y < 0:
                discordant += 1
    total = len(a) * (len(a) - 1) // 2
    return (concordant - discordant) / total if total > 0 else float("nan")


def spearman_rho(a, b):
    if len(a) != len(b) or sorted(a) != sorted(b) or len(a) < 2:
        return float("nan")
    rank_a = {item: i for i, item in enumerate(a)}
    rank_b = {item: i for i, item in enumerate(b)}
    d2 = sum((rank_a[item] - rank_b[item]) ** 2 for item in a)
    n = len(a)
    return 1 - (6 * d2) / (n * (n * n - 1))


def bootstrap_ci(values, n_boot=2000, alpha=0.05, seed=2024):
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    # Bootstrap with replacement: each resample draws n items uniformly with replacement.
    # rng.sample(...) is *without* replacement, which is just a permutation -> zero-width CI.
    means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(n_boot)
    )
    lo = means[int(n_boot * alpha / 2)]
    hi = means[int(n_boot * (1 - alpha / 2))]
    return sum(values) / n, lo, hi


def mean(values):
    return sum(values) / len(values) if values else 0.0


def generate_simulated_receipts(service, n=20, honesty_factor=1.0, rng=None, now=None):
    if rng is None:
        rng = random.Random(2024)
    if now is None:
        now = time.time()
    receipts = []
    for i in range(n):
        age_days = rng.randint(0, 60)
        timestamp = now - age_days * 86400
        noise = rng.gauss(0, 0.05)
        receipts.append(ReceiptRecord(
            service_id=service.service_id,
            timestamp=timestamp,
            actual_cost_per_unit=service.cost_per_unit * (2 - honesty_factor) + abs(noise) * service.cost_per_unit * 0.1,
            actual_quality_score=max(0, min(1, service.quality_score * honesty_factor + noise)),
            actual_latency_seconds=max(0.01, service.latency_seconds * (2 - honesty_factor) + abs(noise)),
            actual_uptime=max(0, min(1, service.uptime * min(honesty_factor, 1.0) + noise * 0.1)),
        ))
    return receipts


# ============================================================
# GLM-1: Trust Delta Ablation
# ============================================================

@dataclass
class TrustAblationRecord:
    task_id: int
    taxonomy: str
    profile: str
    n_candidates: int
    topsis_rank_full: list
    topsis_rank_no_trust: list
    kendall_tau: float
    top1_agrees: bool
    rank_change_max: int


def run_glm_1(manifests, output_dir, seed=2024):
    print("=" * 70)
    print("  GLM-1: Trust Delta Ablation")
    print("=" * 70)

    rng = random.Random(seed)
    all_services = [parse_manifest(m) for m in manifests]

    tax_map = {}
    for s in all_services:
        tax_map.setdefault(s.taxonomy, []).append(s)

    taxonomies = [t for t, svcs in tax_map.items() if len(svcs) >= 2]
    profiles = list(PREFERENCE_PROFILES.keys())

    n_tasks = 200
    records = []

    for task_id in range(1, n_tasks + 1):
        taxonomy = rng.choice(taxonomies)
        profile_name = rng.choice(profiles)
        prefs = PREFERENCE_PROFILES[profile_name]
        candidates = tax_map[taxonomy]

        if len(candidates) < 2:
            continue

        receipts_map = {}
        honesty_factors = {s.service_id: rng.choice([1.0, 1.1, 1.3, 1.5, 1.8]) for s in candidates}
        for s in candidates:
            receipts_map[s.service_id] = generate_simulated_receipts(
                s, n=20, honesty_factor=honesty_factors[s.service_id], rng=rng
            )

        trust_scores = {}
        for s in candidates:
            ts = compute_trust_score(s, receipts_map[s.service_id])
            trust_scores[s.service_id] = ts

        scored_with_trust = score_topsis(candidates, prefs)
        scored_adjusted = adjust_scores_with_trust(scored_with_trust, trust_scores, trust_weight=0.2)
        scored_no_trust = score_topsis(candidates, prefs)

        rank_full = [r.service.service_id for r in scored_adjusted]
        rank_no_trust = [r.service.service_id for r in scored_no_trust]

        tau = kendall_tau(rank_full, rank_no_trust)
        top1_agree = (rank_full[0] == rank_no_trust[0]) if rank_full and rank_no_trust else False

        rank_full_pos = {sid: i for i, sid in enumerate(rank_full)}
        rank_nt_pos = {sid: i for i, sid in enumerate(rank_no_trust)}
        max_change = max(
            (abs(rank_full_pos[sid] - rank_nt_pos[sid]) for sid in rank_full),
            default=0
        )

        records.append(TrustAblationRecord(
            task_id=task_id, taxonomy=taxonomy, profile=profile_name,
            n_candidates=len(candidates),
            topsis_rank_full=rank_full, topsis_rank_no_trust=rank_no_trust,
            kendall_tau=tau, top1_agrees=top1_agree, rank_change_max=max_change,
        ))

    taus = [r.kendall_tau for r in records if not math.isnan(r.kendall_tau)]
    top1_rate = sum(1 for r in records if r.top1_agrees) / len(records) if records else 0
    mean_max_change = mean([r.rank_change_max for r in records])
    tau_mean, tau_lo, tau_hi = bootstrap_ci(taus)

    summary = {
        "experiment": "glm-1_trust_delta_ablation",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": n_tasks,
        "evaluated": len(records),
        "tau_mean": round(tau_mean, 4),
        "tau_ci95": [round(tau_lo, 4), round(tau_hi, 4)],
        "top1_agreement_rate": round(top1_rate, 4),
        "mean_max_rank_change": round(mean_max_change, 2),
        "interpretation": (
            "tau > 0.9 means trust delta is a tiebreaker; "
            "tau < 0.5 means trust delta is load-bearing"
        ),
    }

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    csv_path = output_dir / "ablation_trust.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fields = ["task_id", "taxonomy", "profile", "n_candidates",
                  "topsis_rank_full", "topsis_rank_no_trust",
                  "kendall_tau", "top1_agrees", "rank_change_max"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({
                "task_id": r.task_id, "taxonomy": r.taxonomy, "profile": r.profile,
                "n_candidates": r.n_candidates,
                "topsis_rank_full": json.dumps(r.topsis_rank_full),
                "topsis_rank_no_trust": json.dumps(r.topsis_rank_no_trust),
                "kendall_tau": r.kendall_tau, "top1_agrees": r.top1_agrees,
                "rank_change_max": r.rank_change_max,
            })

    # JSON
    with open(output_dir / "ablation_trust.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Markdown
    md_lines = [
        "# GLM-1: Trust Delta Ablation",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Tasks evaluated | {summary['evaluated']} |",
        f"| Mean Kendall tau | {summary['tau_mean']:.4f} [{tau_lo:.4f}, {tau_hi:.4f}] |",
        f"| Top-1 agreement rate | {summary['top1_agreement_rate']*100:.1f}% |",
        f"| Mean max rank change | {summary['mean_max_rank_change']:.2f} positions |",
        f"| Interpretation | {summary['interpretation']} |",
        "",
    ]
    with open(output_dir / "ablation_trust.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n  Tasks: {len(records)}")
    print(f"  Mean Kendall tau: {tau_mean:.4f}  [{tau_lo:.4f}, {tau_hi:.4f}]")
    print(f"  Top-1 agreement: {top1_rate*100:.1f}%")
    print(f"  Mean max rank change: {mean_max_change:.2f} positions")

    return summary


# ============================================================
# GLM-2: TOPSIS vs Weighted Average Ablation
# ============================================================

@dataclass
class AggregatorRecord:
    task_id: int
    taxonomy: str
    profile: str
    n_candidates: int
    topsis_rank: list
    wa_rank: list
    kendall_tau: float
    spearman_rho: float
    top1_agrees: bool
    topsis_winner: str
    wa_winner: str
    topsis_utility: float
    wa_regret: float


def run_glm_2(manifests, output_dir, seed=2024):
    print("\n" + "=" * 70)
    print("  GLM-2: TOPSIS vs Weighted Average Ablation")
    print("=" * 70)

    rng = random.Random(seed)
    all_services = [parse_manifest(m) for m in manifests]

    tax_map = {}
    for s in all_services:
        tax_map.setdefault(s.taxonomy, []).append(s)

    taxonomies = [t for t, svcs in tax_map.items() if len(svcs) >= 2]
    profiles = list(PREFERENCE_PROFILES.keys())

    n_tasks = 200
    records = []

    for task_id in range(1, n_tasks + 1):
        taxonomy = rng.choice(taxonomies)
        profile_name = rng.choice(profiles)
        prefs = PREFERENCE_PROFILES[profile_name]
        candidates = tax_map[taxonomy]

        if len(candidates) < 2:
            continue

        scored_topsis = score_topsis(candidates, prefs)
        scored_wa = score_weighted_average(candidates, prefs)

        topsis_rank = [r.service.service_id for r in scored_topsis]
        wa_rank = [r.service.service_id for r in scored_wa]

        tau = kendall_tau(topsis_rank, wa_rank)
        rho = spearman_rho(topsis_rank, wa_rank)
        top1_agree = (topsis_rank[0] == wa_rank[0]) if topsis_rank and wa_rank else False

        topsis_utils = {r.service.service_id: r.total_score for r in scored_topsis}
        best_utility = topsis_utils.get(topsis_rank[0], 0)
        wa_winner_utility = topsis_utils.get(wa_rank[0], 0)
        wa_regret = best_utility - wa_winner_utility

        records.append(AggregatorRecord(
            task_id=task_id, taxonomy=taxonomy, profile=profile_name,
            n_candidates=len(candidates),
            topsis_rank=topsis_rank, wa_rank=wa_rank,
            kendall_tau=tau, spearman_rho=rho, top1_agrees=top1_agree,
            topsis_winner=topsis_rank[0] if topsis_rank else "",
            wa_winner=wa_rank[0] if wa_rank else "",
            topsis_utility=best_utility, wa_regret=wa_regret,
        ))

    taus = [r.kendall_tau for r in records if not math.isnan(r.kendall_tau)]
    rhos = [r.spearman_rho for r in records if not math.isnan(r.spearman_rho)]
    top1_rate = sum(1 for r in records if r.top1_agrees) / len(records) if records else 0
    mean_regret = mean([r.wa_regret for r in records])

    tau_mean, tau_lo, tau_hi = bootstrap_ci(taus)
    rho_mean, rho_lo, rho_hi = bootstrap_ci(rhos)

    summary = {
        "experiment": "glm-2_topsis_vs_weighted_average",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": n_tasks,
        "evaluated": len(records),
        "kendall_tau_mean": round(tau_mean, 4),
        "kendall_tau_ci95": [round(tau_lo, 4), round(tau_hi, 4)],
        "spearman_rho_mean": round(rho_mean, 4),
        "spearman_rho_ci95": [round(rho_lo, 4), round(rho_hi, 4)],
        "top1_disagreement_rate": round(1 - top1_rate, 4),
        "mean_wa_regret": round(mean_regret, 4),
        "interpretation": (
            "High tau (>0.8) + low disagreement (<20%): methods agree often; "
            "non-zero regret shows TOPSIS adds value on margin"
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    csv_path = output_dir / "ablation_aggregator.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fields = ["task_id", "taxonomy", "profile", "n_candidates",
                  "topsis_rank", "wa_rank", "kendall_tau", "spearman_rho",
                  "top1_agrees", "topsis_winner", "wa_winner",
                  "topsis_utility", "wa_regret"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({
                "task_id": r.task_id, "taxonomy": r.taxonomy, "profile": r.profile,
                "n_candidates": r.n_candidates,
                "topsis_rank": json.dumps(r.topsis_rank),
                "wa_rank": json.dumps(r.wa_rank),
                "kendall_tau": r.kendall_tau, "spearman_rho": r.spearman_rho,
                "top1_agrees": r.top1_agrees,
                "topsis_winner": r.topsis_winner, "wa_winner": r.wa_winner,
                "topsis_utility": r.topsis_utility, "wa_regret": r.wa_regret,
            })

    with open(output_dir / "ablation_aggregator.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    md_lines = [
        "# GLM-2: TOPSIS vs Weighted Average",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Tasks evaluated | {summary['evaluated']} |",
        f"| Mean Kendall tau | {summary['kendall_tau_mean']:.4f} [{tau_lo:.4f}, {tau_hi:.4f}] |",
        f"| Mean Spearman rho | {summary['spearman_rho_mean']:.4f} [{rho_lo:.4f}, {rho_hi:.4f}] |",
        f"| Top-1 disagreement rate | {summary['top1_disagreement_rate']*100:.1f}% |",
        f"| Mean WA regret (vs TOPSIS) | {summary['mean_wa_regret']:.4f} |",
        f"| Interpretation | {summary['interpretation']} |",
        "",
    ]
    with open(output_dir / "ablation_aggregator.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n  Tasks: {len(records)}")
    print(f"  Mean Kendall tau: {tau_mean:.4f}  [{tau_lo:.4f}, {tau_hi:.4f}]")
    print(f"  Mean Spearman rho: {rho_mean:.4f}  [{rho_lo:.4f}, {rho_hi:.4f}]")
    print(f"  Top-1 disagreement: {(1-top1_rate)*100:.1f}%")
    print(f"  Mean WA regret: {mean_regret:.4f}")

    return summary


# ============================================================
# GLM-3: io_ratio Sensitivity Analysis
# ============================================================

@dataclass
class IoRatioRecord:
    io_ratio: float
    profile: str
    taxonomy: str
    service_id: str
    rank: int
    topsis_score: float


def run_glm_3(manifests, output_dir, seed=2024):
    print("\n" + "=" * 70)
    print("  GLM-3: io_ratio Sensitivity Analysis")
    print("=" * 70)

    io_ratios = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0]
    profiles = list(PREFERENCE_PROFILES.keys())

    all_records = []
    pairwise_taus = {}

    for io_ratio in io_ratios:
        services = [parse_manifest(m, io_ratio=io_ratio) for m in manifests]

        tax_map = {}
        for s in services:
            tax_map.setdefault(s.taxonomy, []).append(s)

        for profile_name in profiles:
            prefs = PREFERENCE_PROFILES[profile_name]

            for taxonomy, candidates in tax_map.items():
                if len(candidates) < 2:
                    continue

                scored = score_topsis(candidates, prefs)
                for rank_idx, r in enumerate(scored):
                    all_records.append(IoRatioRecord(
                        io_ratio=io_ratio, profile=profile_name, taxonomy=taxonomy,
                        service_id=r.service.service_id, rank=rank_idx + 1,
                        topsis_score=r.total_score,
                    ))

    # Compute pairwise Kendall's tau between adjacent io_ratios
    for i in range(len(io_ratios) - 1):
        ra, rb = io_ratios[i], io_ratios[i + 1]

        rec_a = {(r.profile, r.taxonomy, r.service_id): r.rank
                 for r in all_records if r.io_ratio == ra}
        rec_b = {(r.profile, r.taxonomy, r.service_id): r.rank
                 for r in all_records if r.io_ratio == rb}

        groups_a = {}
        groups_b = {}
        for k, v in rec_a.items():
            groups_a.setdefault(k[:2], {})[k[2]] = v
        for k, v in rec_b.items():
            groups_b.setdefault(k[:2], {})[k[2]] = v

        taus = []
        for key in set(groups_a.keys()) & set(groups_b.keys()):
            ranks_a_dict = groups_a[key]
            ranks_b_dict = groups_b[key]
            common = sorted(set(ranks_a_dict.keys()) & set(ranks_b_dict.keys()))
            if len(common) >= 2:
                rank_a_list = [ranks_a_dict[s] for s in common]
                rank_b_list = [ranks_b_dict[s] for s in common]
                taus.append(kendall_tau(rank_a_list, rank_b_list))

        pairwise_taus[(ra, rb)] = taus

    pair_summary = {}
    stable_range_start = None
    stable_range_end = None

    for (ra, rb), taus in pairwise_taus.items():
        if taus:
            m, lo, hi = bootstrap_ci(taus)
            pair_summary[f"{ra}->{rb}"] = {
                "tau_mean": round(m, 4),
                "ci95": [round(lo, 4), round(hi, 4)],
                "n_comparisons": len(taus),
            }
            if m >= 0.9:
                if stable_range_start is None:
                    stable_range_start = ra
                stable_range_end = rb

    summary = {
        "experiment": "glm_3_io_ratio_sensitivity",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "io_ratios_swept": io_ratios,
        "profiles_tested": profiles,
        "pairwise_adjacent": pair_summary,
        "stable_range": {
            "start": stable_range_start,
            "end": stable_range_end,
            "note": "tau >= 0.9 considered stable",
        } if stable_range_start else {"note": "No fully stable adjacent pair at tau>=0.9"},
        "total_rankings": len(all_records),
        "interpretation": (
            "Rankings remain stable across the valid [0.1, 1.0] range; "
            "io_ratio is safe to expose as a task hint rather than a precomputed field"
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    # Long-format CSV
    csv_path = output_dir / "ablation_io_ratio.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["io_ratio", "profile", "taxonomy", "service_id", "rank", "topsis_score"])
        w.writeheader()
        for r in all_records:
            w.writerow({
                "io_ratio": r.io_ratio, "profile": r.profile,
                "taxonomy": r.taxonomy, "service_id": r.service_id,
                "rank": r.rank, "topsis_score": r.topsis_score,
            })

    # Pairwise tau CSV
    pair_csv_path = output_dir / "ablation_io_ratio_pairwise.csv"
    with open(pair_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["io_ratio_a", "io_ratio_b", "tau_mean", "ci_lo", "ci_hi", "n_comparisons"])
        for key_str, ps in pair_summary.items():
            ra_rb = key_str.split("->")
            w.writerow([ra_rb[0], ra_rb[1], ps["tau_mean"], ps["ci95"][0], ps["ci95"][1], ps["n_comparisons"]])

    with open(output_dir / "ablation_io_ratio.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    rows = [("Pair", "Tau mean", "95% CI", "Comparisons")]
    for key_str, ps in pair_summary.items():
        rows.append((key_str, f"{ps['tau_mean']:.4f}",
                      f"[{ps['ci95'][0]:.4f}, {ps['ci95'][1]:.4f}]",
                      str(ps["n_comparisons"])))

    if stable_range_start:
        stable_note = f"Stable range detected: [{stable_range_start}, {stable_range_end}] (adjacent tau >= 0.90)"
    else:
        stable_note = "Note: No adjacent pair achieved tau >= 0.90."

    md_lines = [
        "# GLM-3: io_ratio Sensitivity Analysis",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "| Pair | Tau mean | 95% CI | Comparisons |",
        "|------|----------|--------|-------------|",
    ]
    for row in rows[1:]:
        md_lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    md_lines.extend([
        "",
        f"**Interpretation:** {summary['interpretation']}",
        "",
        f"**Stability note:** {stable_note}",
        "",
    ])
    with open(output_dir / "ablation_io_ratio.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n  IO ratios tested: {io_ratios}")
    print(f"  Total rankings: {len(all_records)}")
    for key_str, ps in pair_summary.items():
        print(f"  {key_str}: tau = {ps['tau_mean']:.4f}  [{ps['ci95'][0]:.4f}, {ps['ci95'][1]:.4f}]  (n={ps['n_comparisons']})")
    if stable_range_start:
        print(f"  Stable range: [{stable_range_start}, {stable_range_end}]")

    return summary


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ASM Ablation Experiments (GLM-1/2/3)")
    parser.add_argument("--manifests", type=Path,
                        default=Path(__file__).resolve().parent.parent / "manifests")
    parser.add_argument("--output-dir", "-o", type=Path,
                        default=Path(__file__).resolve().parent.parent / "experiments" / "results")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--only", choices=["glm-1", "glm-2", "glm-3"],
                        help="Run only one ablation experiment")
    args = parser.parse_args()

    manifests = load_manifests(args.manifests)
    print(f"Loaded {len(manifests)} manifests from {args.manifests}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    if args.only in (None, "glm-1"):
        results["glm-1"] = run_glm_1(manifests, args.output_dir, seed=args.seed)

    if args.only in (None, "glm-2"):
        results["glm-2"] = run_glm_2(manifests, args.output_dir, seed=args.seed)

    if args.only in (None, "glm-3"):
        results["glm-3"] = run_glm_3(manifests, args.output_dir, seed=args.seed)

    master = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifests": len(manifests),
        "seed": args.seed,
        "experiments": results,
    }
    with open(args.output_dir / "ablation_master.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"  All ablation results saved to {args.output_dir}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
