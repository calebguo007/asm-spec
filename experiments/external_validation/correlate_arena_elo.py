#!/usr/bin/env python3
"""External-validation correlation: ASM-declared quality vs LM Arena Elo.

For each LLM in the ASM registry, we look up the closest LM Arena entry
(snapshot date driven by --elo-pkl) and compute the Spearman rank correlation
between the manifest-declared quality score and the Arena Elo. Arena Elo is
derived from millions of pairwise human preference votes — it is the single
most-cited population-scale preference signal for LLMs. Strong rank
correlation supports the claim that ASM's quality dimension reflects real
user preference, not author opinion.

The exact-version LLM in our registry is rarely the exact-version LLM on
Arena (e.g., we ship "deepseek-v4-flash" but Arena has "deepseek-v3.1");
the mapping below pairs each manifest with the closest dated Arena variant
and documents the choice in the output JSON.

Required deps: jsonschema (for manifest reading), plotly<6 (so the official
Arena pickle deserialises). Falls back to a CSV if --arena-csv is supplied.

Usage:
    python experiments/external_validation/correlate_arena_elo.py \
        --elo-pkl ~/Desktop/arena_elo.pkl

    # Or with a hand-curated CSV (model,elo,battles,rank):
    python experiments/external_validation/correlate_arena_elo.py \
        --arena-csv path/to/arena.csv

Outputs:
    experiments/results/external_validation/arena_elo_correlation.json
    experiments/results/external_validation/arena_elo_correlation.csv
    experiments/results/external_validation/arena_elo_correlation.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCORER_DIR = str(ROOT / "scorer")
if SCORER_DIR not in sys.path:
    sys.path.insert(0, SCORER_DIR)

from scorer import load_manifests, parse_manifest  # noqa: E402

OUTPUT_DIR = ROOT / "experiments" / "results" / "external_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Curated ASM service_id -> closest Arena model name (lowercase).
# Each entry documents the *generation gap* between our manifest and the closest
# dated Arena variant; we surface this gap explicitly in the output.
ASM_TO_ARENA: dict[str, dict[str, object]] = {
    "openai/gpt-4o@2024-11-20": {
        "arena_model": "gpt-4o-2024-08-06",
        "gap_note": "Closest dated GPT-4o variant; manifest is 2024-11-20, Arena snapshot has Aug 2024 release.",
    },
    "anthropic/claude-sonnet-4@4.0": {
        "arena_model": "claude-sonnet-4-20250514",
        "gap_note": "Same family generation (Sonnet 4); Arena entry is May 2025 release.",
    },
    "google/gemini-2.5-pro@2.5": {
        "arena_model": "gemini-2.5-pro",
        "gap_note": "Direct match.",
    },
    "deepseek/deepseek-v4-flash@4.0": {
        "arena_model": "deepseek-v3.1",
        "gap_note": "V4-flash not yet on Arena (Aug 2025 snapshot); using V3.1 as nearest predecessor.",
    },
    "qwen/qwen3-max@3.0": {
        "arena_model": "qwen-max-2025-08-15",
        "gap_note": "Closest Qwen-Max release in Arena snapshot; manifest is Qwen3 line.",
    },
    "moonshot/kimi-k2.5@2.5": {
        "arena_model": "kimi-k2-0711-preview",
        "gap_note": "Only Kimi entry in Arena Aug 2025 snapshot; manifest is K2.5, Arena has K2 preview.",
    },
    "zhipu/glm-5@5.0": {
        "arena_model": "glm-4.5",
        "gap_note": "GLM-5 not yet on Arena snapshot; GLM-4.5 is the most recent dated entry.",
    },
    "minimax/m2.7@2.7": {
        "arena_model": "minimax-m1",
        "gap_note": "Only MiniMax entry in Arena snapshot; manifest is M2.7, Arena has M1.",
    },
}


def declared_quality(manifest: dict) -> float | None:
    quality = manifest.get("quality") or {}
    metrics = quality.get("metrics") or []
    if not metrics:
        return None
    return float(metrics[0].get("score", 0))


def declared_quality_metric(manifest: dict) -> str:
    quality = manifest.get("quality") or {}
    metrics = quality.get("metrics") or []
    if not metrics:
        return "unknown"
    return str(metrics[0].get("name", "unknown"))


# ---------------------------------------------------------------------------
# Arena Elo source

def load_elo_from_pkl(path: Path) -> dict[str, dict]:
    """Read Arena Elo from the official chatbot-arena-leaderboard pickle.
    Schema: pickle is dict; data['text']['full']['leaderboard_table_df'] is a
    pandas DataFrame indexed by model name with columns including 'rating',
    'num_battles', 'final_ranking'.
    """
    with path.open("rb") as fp:
        data = pickle.load(fp)
    df = data["text"]["full"]["leaderboard_table_df"]
    out: dict[str, dict] = {}
    for name, row in df.iterrows():
        out[str(name).lower()] = {
            "model": str(name),
            "elo": float(row["rating"]),
            "battles": int(row["num_battles"]),
            "rank": int(row["final_ranking"]),
        }
    return out


def load_elo_from_csv(path: Path) -> dict[str, dict]:
    """Read Arena Elo from a user-supplied CSV: model,elo,battles,rank."""
    out: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            name = row["model"].strip().lower()
            out[name] = {
                "model": row["model"],
                "elo": float(row.get("elo", 0)),
                "battles": int(row.get("battles", 0)),
                "rank": int(row.get("rank", 0)),
            }
    return out


# ---------------------------------------------------------------------------
# Spearman rho with bootstrap CI

def spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2 or len(x) != len(y):
        return float("nan")
    n = len(x)
    rank_x = _rank(x)
    rank_y = _rank(y)
    d2 = sum((rank_x[i] - rank_y[i]) ** 2 for i in range(n))
    return 1 - (6 * d2) / (n * (n * n - 1))


def kendall_tau(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2 or n != len(y):
        return float("nan")
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx * dy > 0:
                concordant += 1
            elif dx * dy < 0:
                discordant += 1
    total = n * (n - 1) // 2
    return (concordant - discordant) / total if total else float("nan")


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and values[indexed[j + 1]] == values[indexed[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def bootstrap_ci(
    pairs: list[tuple[float, float]],
    fn,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 2026,
) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(pairs)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    point = fn([p[0] for p in pairs], [p[1] for p in pairs])
    samples = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        x = [p[0] for p in sample]
        y = [p[1] for p in sample]
        v = fn(x, y)
        if not math.isnan(v):
            samples.append(v)
    samples.sort()
    lo = samples[int(len(samples) * (alpha / 2))] if samples else float("nan")
    hi = samples[int(len(samples) * (1 - alpha / 2))] if samples else float("nan")
    return point, lo, hi


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate ASM-declared LLM quality with LM Arena Elo")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--elo-pkl", type=Path, default=None,
                        help="Path to LM Arena elo_results_*.pkl from huggingface.co/spaces/lmarena-ai/chatbot-arena-leaderboard")
    parser.add_argument("--arena-csv", type=Path, default=None,
                        help="Alternative: hand-prepared CSV with columns model,elo,battles,rank.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    if args.elo_pkl:
        elo = load_elo_from_pkl(args.elo_pkl)
        source = f"pickle:{args.elo_pkl.name}"
    elif args.arena_csv:
        elo = load_elo_from_csv(args.arena_csv)
        source = f"csv:{args.arena_csv.name}"
    else:
        sys.exit("Specify --elo-pkl or --arena-csv. See module docstring.")

    print(f"Loaded {len(elo)} Arena entries from {source}", file=sys.stderr)

    manifests = {m["service_id"]: m for m in load_manifests(args.manifests)
                 if m.get("taxonomy") == "ai.llm.chat"}

    rows = []
    pairs = []
    for asm_id, mapping in ASM_TO_ARENA.items():
        manifest = manifests.get(asm_id)
        if manifest is None:
            print(f"  SKIP {asm_id}: manifest not loaded", file=sys.stderr)
            continue
        q = declared_quality(manifest)
        metric = declared_quality_metric(manifest)
        arena_name = str(mapping["arena_model"]).lower()
        arena_row = elo.get(arena_name)
        if arena_row is None:
            print(f"  SKIP {asm_id}: arena name '{arena_name}' not found", file=sys.stderr)
            continue
        rows.append({
            "asm_service_id": asm_id,
            "asm_quality_metric": metric,
            "asm_quality_score": q,
            "arena_model": arena_row["model"],
            "arena_elo": arena_row["elo"],
            "arena_rank": arena_row["rank"],
            "arena_battles": arena_row["battles"],
            "gap_note": mapping["gap_note"],
        })
        if q is not None:
            pairs.append((float(q), float(arena_row["elo"])))

    rho, rho_lo, rho_hi = bootstrap_ci(pairs, spearman, n_boot=2000, seed=args.seed)
    tau, tau_lo, tau_hi = bootstrap_ci(pairs, kendall_tau, n_boot=2000, seed=args.seed)

    # Per-metric breakdown — heterogeneous declared metrics make the global ρ noisy.
    by_metric_pairs: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        metric = r["asm_quality_metric"]
        if r["asm_quality_score"] is None:
            continue
        by_metric_pairs.setdefault(metric, []).append(
            (float(r["asm_quality_score"]), float(r["arena_elo"]))
        )
    by_metric: dict[str, dict] = {}
    for metric, mpairs in by_metric_pairs.items():
        if len(mpairs) >= 2:
            mrho, mrho_lo, mrho_hi = bootstrap_ci(mpairs, spearman, n_boot=2000, seed=args.seed)
            mtau, _, _ = bootstrap_ci(mpairs, kendall_tau, n_boot=2000, seed=args.seed)
        else:
            mrho = mrho_lo = mrho_hi = mtau = float("nan")
        by_metric[metric] = {
            "n": len(mpairs),
            "spearman_rho": None if math.isnan(mrho) else round(mrho, 4),
            "spearman_ci95": (None if math.isnan(mrho_lo) else [round(mrho_lo, 4), round(mrho_hi, 4)]),
            "kendall_tau": None if math.isnan(mtau) else round(mtau, 4),
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "n_manifests_attempted": len(ASM_TO_ARENA),
        "n_paired": len(pairs),
        "spearman_rho": round(rho, 4) if not math.isnan(rho) else None,
        "spearman_ci95": [round(rho_lo, 4), round(rho_hi, 4)] if not math.isnan(rho_lo) else None,
        "kendall_tau":   round(tau, 4) if not math.isnan(tau) else None,
        "kendall_ci95":  [round(tau_lo, 4), round(tau_hi, 4)] if not math.isnan(tau_lo) else None,
        "by_metric": by_metric,
        "rows": rows,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "arena_elo_correlation.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if rows:
        with (args.output_dir / "arena_elo_correlation.csv").open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    lines = [
        "# ASM declared quality vs LM Arena Elo",
        "",
        f"Generated: {summary['generated_at']}",
        f"Source:    {source}",
        f"Paired:    {len(pairs)} / {len(ASM_TO_ARENA)} manifests matched",
        "",
        "## Headline correlation (all metrics pooled)",
        "",
        f"- Spearman rho = **{summary['spearman_rho']}**  (95% bootstrap CI {summary['spearman_ci95']})",
        f"- Kendall tau  = **{summary['kendall_tau']}**   (95% bootstrap CI {summary['kendall_ci95']})",
        "",
        "Pooled across heterogeneous declared metrics (LMSYS_Elo, Artificial_Analysis_Intelligence,",
        "MMLU). The pooled correlation is uninformative because the three scales are not commensurable",
        "— see per-metric breakdown below.",
        "",
        "## Per-metric breakdown",
        "",
        "| Declared metric | n | Spearman rho (95% CI) | Kendall tau |",
        "|---|---:|---|---:|",
    ]
    for metric, stats in sorted(by_metric.items(), key=lambda kv: -kv[1]["n"]):
        ci = stats["spearman_ci95"]
        ci_str = f"[{ci[0]}, {ci[1]}]" if ci else "n/a"
        rho_str = f"{stats['spearman_rho']}" if stats["spearman_rho"] is not None else "n/a"
        tau_str = f"{stats['kendall_tau']}" if stats["kendall_tau"] is not None else "n/a"
        lines.append(f"| `{metric}` | {stats['n']} | {rho_str} {ci_str} | {tau_str} |")
    lines.append("")
    lines.extend([
        "## Per-pair detail",
        "",
        "| ASM service_id | ASM metric | ASM score | Arena model | Arena Elo | Arena rank | Battles | Gap note |",
        "|---|---|---:|---|---:|---:|---:|---|",
    ])
    for r in rows:
        lines.append(
            f"| `{r['asm_service_id']}` | {r['asm_quality_metric']} | {r['asm_quality_score']} | "
            f"`{r['arena_model']}` | {r['arena_elo']:.0f} | {r['arena_rank']} | {r['arena_battles']:,} | "
            f"{r['gap_note']} |"
        )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append("- N = 8 paired observations; the bootstrap CI is wide and the point estimate is sensitive "
                 "to any single mismatch.")
    lines.append("- Arena entries are best-effort matches to ASM service_ids; the exact-dated variant in our "
                 "manifest is rarely on Arena yet, so we use the closest dated predecessor and document the "
                 "gap in the per-pair table above.")
    lines.append("- Arena Elo measures pairwise chat preference; ASM-declared quality (mostly Artificial "
                 "Analysis Intelligence index) measures benchmark suite performance. These are correlated "
                 "but not identical; a positive rho means ASM's quality axis tracks user preference at the "
                 "rank level, not that the two scales are interchangeable.")
    (args.output_dir / "arena_elo_correlation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
