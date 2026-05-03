#!/usr/bin/env python3
"""Auto-generate paper table snippets from experiment result JSONs.

Writes Markdown table fragments to `experiments/results/paper_tables/` so paper
authors can copy-paste exact numbers without manual transcription. Each table
maps to a section in `paper/asm-paper-draft.md`.

This script is not a full paper builder — the paper is hand-written prose
around these numbers. The point is to ensure that whenever an experiment
re-runs, the source-of-truth Markdown tables update too.

Run after experiments produce their JSON outputs:
    python experiments/generate_paper_tables.py

Idempotent and safe to re-run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results"
EA_RESULTS = ROOT / "experiments" / "expert_annotation"
OUT = RESULTS / "paper_tables"


def write(name: str, body: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# §6.0 — 50-repo GitHub audit (Table 0)

def table_section_6_0() -> None:
    data = load_json(RESULTS / "mcp_ecosystem_audit.json")
    if data is None:
        return
    summary = data.get("summary") or data
    n = summary.get("sample_size") or summary.get("total_repositories") or 50
    counts = summary.get("counts") or {}
    rows_data = data.get("rows") or []
    # Compute "all four core" by scanning rows if not pre-computed.
    all_four = 0
    for row in rows_data:
        if all(row.get(k) for k in ("pricing", "sla", "quality", "payment")):
            all_four += 1
    rows = [
        ("Pricing mentions", counts.get("pricing")),
        ("SLA or rate-limit mentions", counts.get("sla")),
        ("Quality or benchmark mentions", counts.get("quality")),
        ("Payment mentions", counts.get("payment")),
        ("Structured ASM / `x-asm` metadata", counts.get("structured_asm") or 0),
        ("All four core value classes", all_four),
    ]
    lines = [
        f"**Table 0: MCP ecosystem value metadata coverage (n={n} public repositories).**",
        "",
        "| Metadata class | Repositories | Coverage |",
        "|---|---:|---:|",
    ]
    for label, count in rows:
        if count is None:
            continue
        pct = (count / n * 100) if n else 0
        lines.append(f"| {label} | {count} / {n} | {pct:.1f}% |")
    write("section_6_0_github_audit.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# §6.0a — Registry-level audit (Table 0a)

def table_section_6_0a() -> None:
    data = load_json(RESULTS / "mcp_value_metadata_audit.json")
    if data is None:
        return
    summary = data.get("summary") or data
    n = summary.get("sample_size") or summary.get("n") or 0
    overall = summary.get("overall") or {}
    counts = overall.get("counts") or {}
    fields = ["pricing", "sla_rate_limit", "quality_benchmark", "payment", "provenance", "security_trust"]
    sources = summary.get("sources") or {}
    lines = [
        f"**Table 0a: Value-metadata coverage across {len(sources)} MCP registries / directories (n = {n:,}).**",
        "",
        "| Field | Absent | Human-readable | Structured | Machine-actionable |",
        "|---|---:|---:|---:|---:|",
    ]
    for f in fields:
        row = counts.get(f) or {}
        lines.append(
            f"| {f.replace('_', ' / ')} | "
            f"{row.get('absent', 0):,} | "
            f"{row.get('human_readable', 0):,} | "
            f"{row.get('structured_unverified', 0):,} | "
            f"{row.get('machine_actionable', 0):,} |"
        )
    full = (overall.get("all_core_value_classes") or {}).get("count")
    if full is not None and n:
        lines.append("")
        lines.append(
            f"Entries exposing all four core economic value classes simultaneously: "
            f"**{full:,} / {n:,} ({full / n * 100:.1f}%)**."
        )
    lines.append("")
    lines.append("**Per-source breakdown (n by source):**")
    lines.append("")
    lines.append("| Source | n |")
    lines.append("|---|---:|")
    for src, info in sorted(sources.items()):
        lines.append(f"| {src} | {info.get('n', 0):,} |")
    write("section_6_0a_registry_audit.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# §6.3a — Component ablations

def table_section_6_3a() -> None:
    """§6.3a synthesises trust-delta + aggregator + io_ratio results.

    Master JSON nests the three experiments under .experiments. The io_ratio
    pairwise comparisons live under `pairwise_adjacent` (NOT `pairwise_tau`).
    """
    master = load_json(RESULTS / "ablation_master.json")
    if master is None:
        return
    glm1 = master.get("experiments", {}).get("glm-1") or {}
    glm2 = master.get("experiments", {}).get("glm-2") or {}
    glm3 = master.get("experiments", {}).get("glm-3") or {}

    # io_ratio pairwise lives as a dict keyed "0.1->0.2": {"tau_mean": ..., "ci95": [..]}
    # in the experiment JSON, but the legacy schema flattened it into a list. Handle both.
    pairwise_raw = glm3.get("pairwise_adjacent") or glm3.get("pairwise_tau") or []
    if isinstance(pairwise_raw, dict):
        pairwise_iter = list(pairwise_raw.values())
    elif isinstance(pairwise_raw, list):
        pairwise_iter = pairwise_raw
    else:
        pairwise_iter = []
    min_adj_tau: Any = "n/a"
    taus = [p.get("tau_mean") for p in pairwise_iter
            if isinstance(p, dict) and isinstance(p.get("tau_mean"), (int, float))]
    if taus:
        min_adj_tau = round(min(taus), 4)

    top1_disagree = glm2.get("top1_disagreement_rate")
    top1_str = (
        f"{top1_disagree*100:.1f}%" if isinstance(top1_disagree, (int, float)) else "n/a"
    )

    tau_glm1 = glm1.get("tau_mean", "n/a")
    tau_glm2 = glm2.get("kendall_tau_mean", "n/a")

    lines = [
        "**Table 5: Component ablations on the same 200-task suite as §6.5.**",
        "",
        "| Ablation | Metric | Result | Interpretation |",
        "|---|---|---:|---|",
        f"| Drop trust delta | Kendall's tau vs full TOPSIS | {tau_glm1} | trust delta is a tiebreaker |",
        f"| TOPSIS vs weighted average | Kendall's tau | {tau_glm2} | top-1 disagreement {top1_str} |",
        f"| io_ratio sweep | Min adjacent tau in swept range | {min_adj_tau} | rankings stable across realistic I/O ratios |",
    ]
    write("section_6_3a_ablations.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# §6.5 — A/B comparison

def table_section_6_5() -> None:
    """§6.5 reads ab_test_analysis.json. The actual JSON keys are
    A_ASM / B_Random / C_Expensive (with the order prefix), nested under
    .summary. The TOPSIS utility field is `topsis_mean`.
    """
    data = load_json(RESULTS / "ab_test_analysis.json")
    if data is None:
        return
    summary = data.get("summary") or {}
    lines = [
        "**Table 4: Mean outcomes across 200 tasks, 3 selectors.**",
        "",
        "| Selector | n | TOPSIS utility | Cost | Quality | Latency |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    label_map = {
        "A_ASM": "ASM-TOPSIS",
        "B_Random": "Random",
        "C_Expensive": "Most-expensive-first",
    }
    for raw_key, pretty in label_map.items():
        s = summary.get(raw_key)
        if not s:
            continue
        utility = s.get("topsis_mean", s.get("topsis_score_mean", "n/a"))
        cost = s.get("cost_mean", "n/a")
        quality = s.get("quality_mean", "n/a")
        latency = s.get("latency_mean", "n/a")
        n = s.get("count", "n/a")
        lines.append(
            f"| {pretty} | {n} | "
            f"{utility:.4f} | "
            f"{cost:.6f} | "
            f"{quality:.4f} | "
            f"{latency:.4f} |"
            if isinstance(utility, (int, float)) else
            f"| {pretty} | {n} | {utility} | {cost} | {quality} | {latency} |"
        )

    # Stat-sig footer (Welch's t-tests on TOPSIS score across selector pairs).
    # JSON shape: t_tests[<field>][<pair>]={t, p, significant}.
    # We only surface topsis_score and cost_per_unit.
    t_tests = data.get("t_tests") or {}
    if t_tests:
        lines.append("")
        lines.append("**Welch's t-tests, ASM vs baselines:**")
        lines.append("")
        lines.append("| Metric | Comparison | t | p |")
        lines.append("|---|---|---:|---:|")
        for field in ("topsis_score", "cost_per_unit"):
            pairs = t_tests.get(field) or {}
            for pair_label, stats in pairs.items():
                t = stats.get("t", "n/a")
                p = stats.get("p", "n/a")
                t_str = f"{t:.3f}" if isinstance(t, (int, float)) else str(t)
                p_str = f"{p:.2e}" if isinstance(p, (int, float)) else str(p)
                lines.append(f"| {field} | {pair_label} | {t_str} | {p_str} |")

    write("section_6_5_ab_test.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# §6.6a — Preference alignment

def table_section_6_6a() -> None:
    data = load_json(RESULTS / "preference_alignment.json")
    if data is None:
        return
    aggregate = (data.get("summary") or {}).get("summary") or {}
    if not aggregate:
        return
    n = (data.get("summary") or {}).get("task_count", 20)
    lines = [
        f"**Table 6a: Preference alignment over {n} natural-language requests.**",
        "",
        "| Selector | Utility mean | Regret mean | Alignment mean | Zero-regret rate |",
        "|---|---:|---:|---:|---:|",
    ]
    order = ["asm_topsis", "weighted_average", "cheapest_first", "fastest_first",
             "highest_quality_first", "highest_reliability_first", "random"]
    for k in order:
        v = aggregate.get(k)
        if not v:
            continue
        lines.append(
            f"| {k.replace('_', ' ')} | "
            f"{v.get('utility_mean', 'n/a'):.3f} | "
            f"{v.get('regret_mean', 'n/a'):.3f} | "
            f"{v.get('alignment_score_mean', 'n/a'):.3f} | "
            f"{v.get('zero_regret_rate', 0)*100:.1f}% |"
        )
    write("section_6_6a_preference_alignment.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# §6.7 — LLM-as-selector

def table_section_6_7() -> None:
    rows = []
    for label, dir_name in [
        ("DeepSeek-V4-flash", "results_objective"),
        ("Qwen3-Max", "results_objective_qwen"),
        ("Kimi K2.5", "results_objective_kimi"),
    ]:
        summary = load_json(EA_RESULTS / dir_name / "ranking_summary.json")
        if not summary:
            continue
        sel = summary.get("selectors", {})
        raw = sel.get("llm_raw_doc", {}).get("top1_accuracy")
        manifest = sel.get("llm_manifest", {}).get("top1_accuracy")
        if raw is None or manifest is None:
            continue
        delta = manifest - raw
        rows.append((label, raw, manifest, delta))
    if not rows:
        return
    lines = [
        "**Table 7b: Three-LLM replication of the §6.7 ranking experiment (n=36 tasks).**",
        "",
        "| Model | `llm_raw_doc` top-1 | `llm_manifest` top-1 | Δ (pp) |",
        "|---|---:|---:|---:|",
    ]
    for label, raw, manifest, delta in rows:
        lines.append(
            f"| {label} | {raw * 100:.1f}% | {manifest * 100:.1f}% | +{delta * 100:.1f} |"
        )
    write("section_6_7_llm_replication.md", "\n".join(lines))


# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Generating paper-table snippets at {OUT.relative_to(ROOT)}")
    table_section_6_0()
    table_section_6_0a()
    table_section_6_3a()
    table_section_6_5()
    table_section_6_6a()
    table_section_6_7()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (OUT / "_generated_at.txt").write_text(stamp, encoding="utf-8")
    print(f"Done. ({stamp})")


if __name__ == "__main__":
    main()
