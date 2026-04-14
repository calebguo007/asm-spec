#!/usr/bin/env python3
"""ASM A/B Test框架 — 对比 TOPSIS vs 随机 vs 最贵策略。

三组对照实验：
  - Group A (ASM):       使用 scorer.py 的 TOPSIS 算法选择最优Service
  - Group B (Random):    从候选Service中随机选择
  - Group C (Expensive): 始终选择价格最高的Service

生成 50 个模拟任务请求，覆盖不同 taxonomy 和用户偏好，
记录每次选择的成本、延迟、质量、TOPSIS 得分，
最终输出统计对比和 t-test 显著性检验。

Usage:
    python ab_test.py                        # 运行实验，输出到 stdout + CSV
    python ab_test.py --output results/      # 指定输出目录
    python ab_test.py --seed 42 --tasks 100  # 自定义随机种子和任务数
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── 将 scorer 加入 sys.path ──────────────────────
_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (
    Constraints,
    Preferences,
    ScoredService,
    ServiceVector,
    filter_services,
    load_manifests,
    parse_manifest,
    score_topsis,
)


# ============================================================
# 数据Structure
# ============================================================

@dataclass
class TaskRequest:
    """模拟的任务请求。"""
    task_id: int
    taxonomy: str                    # 期望的 taxonomy（如 ai.llm.chat）
    preference_profile: str          # 偏好标签（cost_first / quality_first / speed_first / balanced）
    preferences: Preferences         # 实际偏好Weight


@dataclass
class SelectionRecord:
    """单次选择的记录。"""
    task_id: int
    group: str                       # A_ASM / B_Random / C_Expensive
    taxonomy: str
    preference_profile: str
    service_id: str
    display_name: str
    cost_per_unit: float
    latency_seconds: float
    quality_score: float
    uptime: float
    topsis_score: float              # 该Service在当前偏好下的 TOPSIS 得分


# ============================================================
# 偏好生成
# ============================================================

# 四种偏好模板
PREFERENCE_PROFILES: dict[str, Preferences] = {
    "cost_first":    Preferences(cost=0.55, quality=0.25, speed=0.10, reliability=0.10),
    "quality_first": Preferences(cost=0.10, quality=0.55, speed=0.20, reliability=0.15),
    "speed_first":   Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
    "balanced":      Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
}


def generate_tasks(
    taxonomies: list[str],
    num_tasks: int = 50,
    rng: random.Random | None = None,
) -> list[TaskRequest]:
    """生成模拟任务请求。

    每个任务随机分配一个 taxonomy 和偏好方向。
    taxonomy 分布按实际 manifest 数量加权（有更多Service的类别出现更频繁）。
    """
    if rng is None:
        rng = random.Random()

    profiles = list(PREFERENCE_PROFILES.keys())
    tasks = []

    for i in range(num_tasks):
        taxonomy = rng.choice(taxonomies)
        profile_name = rng.choice(profiles)
        tasks.append(TaskRequest(
            task_id=i + 1,
            taxonomy=taxonomy,
            preference_profile=profile_name,
            preferences=PREFERENCE_PROFILES[profile_name],
        ))

    return tasks


# ============================================================
# 选择策略
# ============================================================

def strategy_asm_topsis(
    services: list[ServiceVector],
    preferences: Preferences,
) -> tuple[ServiceVector | None, float]:
    """Group A: 使用 TOPSIS 选择最优Service。返回 (选中的Service, TOPSIS 得分)。"""
    if not services:
        return None, 0.0
    results = score_topsis(services, preferences)
    if not results:
        return None, 0.0
    best = results[0]
    return best.service, best.total_score


def strategy_random(
    services: list[ServiceVector],
    preferences: Preferences,
    rng: random.Random,
) -> tuple[ServiceVector | None, float]:
    """Group B: 随机选择。同时计算该Service的 TOPSIS 得分作为参考。"""
    if not services:
        return None, 0.0
    chosen = rng.choice(services)
    # 计算该Service在 TOPSIS 框架下的得分
    results = score_topsis(services, preferences)
    topsis_score = 0.0
    for r in results:
        if r.service.service_id == chosen.service_id:
            topsis_score = r.total_score
            break
    return chosen, topsis_score


def strategy_expensive(
    services: list[ServiceVector],
    preferences: Preferences,
) -> tuple[ServiceVector | None, float]:
    """Group C: 选择价格最高的Service（模拟"贵=好"的假设）。"""
    if not services:
        return None, 0.0
    most_expensive = max(services, key=lambda s: s.cost_per_unit)
    # 计算该Service在 TOPSIS 框架下的得分
    results = score_topsis(services, preferences)
    topsis_score = 0.0
    for r in results:
        if r.service.service_id == most_expensive.service_id:
            topsis_score = r.total_score
            break
    return most_expensive, topsis_score


# ============================================================
# 实验执行
# ============================================================

def run_experiment(
    manifests: list[dict],
    tasks: list[TaskRequest],
    rng: random.Random,
) -> list[SelectionRecord]:
    """对每个任务执行三组策略，返回所有选择记录。"""
    # 预解析所有 manifest
    all_services = [parse_manifest(m) for m in manifests]

    # 按 taxonomy 分组
    taxonomy_map: dict[str, list[ServiceVector]] = {}
    for s in all_services:
        # 提取顶层 taxonomy 前缀用于匹配（如 ai.llm.chat → ai.llm）
        taxonomy_map.setdefault(s.taxonomy, []).append(s)

    records: list[SelectionRecord] = []

    for task in tasks:
        # 筛选匹配 taxonomy 的候选Service
        # 使用前缀匹配：ai.llm.chat 匹配 ai.llm.chat 和 ai.llm.*
        candidates = []
        for tax, svcs in taxonomy_map.items():
            if tax.startswith(task.taxonomy) or task.taxonomy.startswith(tax):
                candidates.extend(svcs)

        if not candidates:
            # 没有匹配的Service，跳过
            continue

        # 三组策略
        strategies = [
            ("A_ASM", strategy_asm_topsis(candidates, task.preferences)),
            ("B_Random", strategy_random(candidates, task.preferences, rng)),
            ("C_Expensive", strategy_expensive(candidates, task.preferences)),
        ]

        for group, (chosen, topsis_score) in strategies:
            if chosen is None:
                continue
            records.append(SelectionRecord(
                task_id=task.task_id,
                group=group,
                taxonomy=task.taxonomy,
                preference_profile=task.preference_profile,
                service_id=chosen.service_id,
                display_name=chosen.display_name,
                cost_per_unit=chosen.cost_per_unit,
                latency_seconds=chosen.latency_seconds,
                quality_score=chosen.quality_score,
                uptime=chosen.uptime,
                topsis_score=topsis_score,
            ))

    return records


# ============================================================
# 统计分析
# ============================================================

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def t_test_independent(a: list[float], b: list[float]) -> tuple[float, float]:
    """独立样本 t 检验（Welch's t-test）。

    返回 (t_statistic, p_value)。使用 scipy 如果可用，否则用近似。
    """
    try:
        from scipy import stats
        result = stats.ttest_ind(a, b, equal_var=False)
        return float(result.statistic), float(result.pvalue)
    except ImportError:
        # 备用：手动计算 Welch's t-test
        n1, n2 = len(a), len(b)
        if n1 < 2 or n2 < 2:
            return 0.0, 1.0
        m1, m2 = _mean(a), _mean(b)
        s1, s2 = _std(a), _std(b)
        se = ((s1 ** 2 / n1) + (s2 ** 2 / n2)) ** 0.5
        if se == 0:
            return 0.0, 1.0
        t_stat = (m1 - m2) / se
        # 近似 p-value（使用正态分布近似，对大样本足够）
        import math
        p_value = 2 * (1 - _normal_cdf(abs(t_stat)))
        return t_stat, p_value


def _normal_cdf(x: float) -> float:
    """标准正态分布 CDF 的近似（Abramowitz & Stegun）。"""
    import math
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def analyze_results(records: list[SelectionRecord]) -> dict[str, Any]:
    """分析实验结果，返回Structure化的分析数据。"""
    groups = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
    for r in records:
        groups[r.group].append(r)

    # 总体对比
    summary = {}
    for group_name, group_records in groups.items():
        costs = [r.cost_per_unit for r in group_records]
        latencies = [r.latency_seconds for r in group_records]
        qualities = [r.quality_score for r in group_records]
        uptimes = [r.uptime for r in group_records]
        topsis_scores = [r.topsis_score for r in group_records]

        summary[group_name] = {
            "count": len(group_records),
            "cost_mean": _mean(costs),
            "cost_std": _std(costs),
            "latency_mean": _mean(latencies),
            "latency_std": _std(latencies),
            "quality_mean": _mean(qualities),
            "quality_std": _std(qualities),
            "uptime_mean": _mean(uptimes),
            "uptime_std": _std(uptimes),
            "topsis_mean": _mean(topsis_scores),
            "topsis_std": _std(topsis_scores),
        }

    # t-test: A vs B, A vs C
    t_tests = {}
    for metric in ["cost_per_unit", "latency_seconds", "quality_score", "uptime", "topsis_score"]:
        a_vals = [getattr(r, metric) for r in groups["A_ASM"]]
        b_vals = [getattr(r, metric) for r in groups["B_Random"]]
        c_vals = [getattr(r, metric) for r in groups["C_Expensive"]]

        t_ab, p_ab = t_test_independent(a_vals, b_vals)
        t_ac, p_ac = t_test_independent(a_vals, c_vals)

        t_tests[metric] = {
            "A_vs_B": {"t": t_ab, "p": p_ab, "significant": p_ab < 0.05},
            "A_vs_C": {"t": t_ac, "p": p_ac, "significant": p_ac < 0.05},
        }

    # 按 taxonomy 分组的细分对比
    taxonomies = sorted(set(r.taxonomy for r in records))
    taxonomy_breakdown = {}
    for tax in taxonomies:
        tax_records = [r for r in records if r.taxonomy == tax]
        tax_groups: dict[str, list[SelectionRecord]] = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
        for r in tax_records:
            tax_groups[r.group].append(r)

        tax_summary = {}
        for group_name, group_records in tax_groups.items():
            if not group_records:
                continue
            tax_summary[group_name] = {
                "count": len(group_records),
                "cost_mean": _mean([r.cost_per_unit for r in group_records]),
                "latency_mean": _mean([r.latency_seconds for r in group_records]),
                "quality_mean": _mean([r.quality_score for r in group_records]),
                "topsis_mean": _mean([r.topsis_score for r in group_records]),
            }
        taxonomy_breakdown[tax] = tax_summary

    # 按偏好分组的细分对比
    profiles = sorted(set(r.preference_profile for r in records))
    profile_breakdown = {}
    for profile in profiles:
        prof_records = [r for r in records if r.preference_profile == profile]
        prof_groups: dict[str, list[SelectionRecord]] = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
        for r in prof_records:
            prof_groups[r.group].append(r)

        prof_summary = {}
        for group_name, group_records in prof_groups.items():
            if not group_records:
                continue
            prof_summary[group_name] = {
                "count": len(group_records),
                "cost_mean": _mean([r.cost_per_unit for r in group_records]),
                "quality_mean": _mean([r.quality_score for r in group_records]),
                "topsis_mean": _mean([r.topsis_score for r in group_records]),
            }
        profile_breakdown[profile] = prof_summary

    # Service选择频率统计
    selection_freq: dict[str, dict[str, int]] = {"A_ASM": {}, "B_Random": {}, "C_Expensive": {}}
    for r in records:
        selection_freq[r.group][r.service_id] = selection_freq[r.group].get(r.service_id, 0) + 1

    return {
        "summary": summary,
        "t_tests": t_tests,
        "taxonomy_breakdown": taxonomy_breakdown,
        "profile_breakdown": profile_breakdown,
        "selection_freq": selection_freq,
    }


# ============================================================
# 输出
# ============================================================

def save_csv(records: list[SelectionRecord], filepath: str) -> None:
    """将选择记录保存为 CSV。"""
    fieldnames = [
        "task_id", "group", "taxonomy", "preference_profile",
        "service_id", "display_name",
        "cost_per_unit", "latency_seconds", "quality_score", "uptime",
        "topsis_score",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "task_id": r.task_id,
                "group": r.group,
                "taxonomy": r.taxonomy,
                "preference_profile": r.preference_profile,
                "service_id": r.service_id,
                "display_name": r.display_name,
                "cost_per_unit": f"{r.cost_per_unit:.8f}",
                "latency_seconds": f"{r.latency_seconds:.4f}",
                "quality_score": f"{r.quality_score:.4f}",
                "uptime": f"{r.uptime:.4f}",
                "topsis_score": f"{r.topsis_score:.4f}",
            })


def print_summary(analysis: dict[str, Any], num_tasks: int) -> None:
    """打印实验结果摘要到 stdout。"""
    summary = analysis["summary"]
    t_tests = analysis["t_tests"]

    print("\n" + "=" * 78)
    print("  ASM A/B Test结果")
    print("=" * 78)
    print(f"\n  任务数: {num_tasks} | 每组选择数: {summary['A_ASM']['count']}")
    print(f"  Group A: ASM TOPSIS | Group B: Random | Group C: Expensive-first\n")

    # ── 总体对比表 ──
    header = f"{'指标':<18} {'A_ASM':>14} {'B_Random':>14} {'C_Expensive':>14}"
    sep = "-" * 62
    print(sep)
    print(header)
    print(sep)

    metrics = [
        ("成本 ($/unit)", "cost"),
        ("延迟 (s)", "latency"),
        ("质量 (0-1)", "quality"),
        ("可用性 (0-1)", "uptime"),
        ("TOPSIS 得分", "topsis"),
    ]

    for label, key in metrics:
        vals = []
        for g in ["A_ASM", "B_Random", "C_Expensive"]:
            m = summary[g][f"{key}_mean"]
            s = summary[g][f"{key}_std"]
            vals.append(f"{m:.6f}±{s:.4f}" if key == "cost" else f"{m:.4f}±{s:.4f}")
        print(f"  {label:<16} {vals[0]:>14} {vals[1]:>14} {vals[2]:>14}")

    print(sep)

    # ── Statistically significant性 ──
    print("\n  Statistically significant性检验 (Welch's t-test, α=0.05):")
    print(sep)
    print(f"  {'指标':<20} {'A vs B':>18} {'A vs C':>18}")
    print(sep)

    metric_labels = {
        "cost_per_unit": "成本",
        "latency_seconds": "延迟",
        "quality_score": "质量",
        "uptime": "可用性",
        "topsis_score": "TOPSIS 得分",
    }

    for metric, label in metric_labels.items():
        ab = t_tests[metric]["A_vs_B"]
        ac = t_tests[metric]["A_vs_C"]
        ab_sig = "✅ p<0.05" if ab["significant"] else f"p={ab['p']:.4f}"
        ac_sig = "✅ p<0.05" if ac["significant"] else f"p={ac['p']:.4f}"
        print(f"  {label:<20} {ab_sig:>18} {ac_sig:>18}")

    print(sep)

    # ── Taxonomy 细分 ──
    print("\n  按 Taxonomy 分组对比 (TOPSIS 平均得分):")
    print(sep)
    print(f"  {'Taxonomy':<30} {'A_ASM':>10} {'B_Random':>10} {'C_Expensive':>12}")
    print(sep)

    for tax, groups in analysis["taxonomy_breakdown"].items():
        vals = []
        for g in ["A_ASM", "B_Random", "C_Expensive"]:
            if g in groups:
                vals.append(f"{groups[g]['topsis_mean']:.4f}")
            else:
                vals.append("—")
        print(f"  {tax:<30} {vals[0]:>10} {vals[1]:>10} {vals[2]:>12}")

    print(sep)

    # ── 偏好细分 ──
    print("\n  按偏好方向分组对比 (TOPSIS 平均得分):")
    print(sep)
    print(f"  {'偏好':<18} {'A_ASM':>10} {'B_Random':>10} {'C_Expensive':>12}")
    print(sep)

    for profile, groups in analysis["profile_breakdown"].items():
        vals = []
        for g in ["A_ASM", "B_Random", "C_Expensive"]:
            if g in groups:
                vals.append(f"{groups[g]['topsis_mean']:.4f}")
            else:
                vals.append("—")
        print(f"  {profile:<18} {vals[0]:>10} {vals[1]:>10} {vals[2]:>12}")

    print(sep)

    # ── Service选择频率 ──
    print("\n  Service选择频率 (Top 5 per group):")
    print(sep)

    for group in ["A_ASM", "B_Random", "C_Expensive"]:
        freq = analysis["selection_freq"][group]
        top5 = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n  {group}:")
        for sid, count in top5:
            pct = count / summary[group]["count"] * 100
            bar = "█" * int(pct / 2)
            print(f"    {sid:<45} {count:>3}x ({pct:>5.1f}%) {bar}")

    print("\n" + "=" * 78)


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="ASM A/B Test框架 — 对比 TOPSIS vs Random vs Expensive 策略",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python ab_test.py                          # 默认运行
  python ab_test.py --output results/        # 输出到 results/ 目录
  python ab_test.py --seed 42 --tasks 100    # 自定义随机种子和任务数
  python ab_test.py --manifests ../manifests  # 指定 manifest 目录
        """,
    )
    parser.add_argument(
        "--manifests", "-m",
        default=str(Path(__file__).resolve().parent.parent / "manifests"),
        help="ASM manifests 目录路径（默认: ../manifests）",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(Path(__file__).resolve().parent / "results"),
        help="输出目录（默认: ./results）",
    )
    parser.add_argument(
        "--tasks", "-n",
        type=int, default=50,
        help="模拟任务数（默认: 50）",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int, default=2024,
        help="随机种子（默认: 2024）",
    )

    args = parser.parse_args()

    # ── Load manifests ──
    manifests = load_manifests(args.manifests)
    if not manifests:
        print(f"Error: 在 {args.manifests} 中未找到 .asm.json 文件。")
        sys.exit(1)

    print(f"✅ Load了 {len(manifests)} 个 ASM manifests")
    for m in manifests:
        print(f"   • {m.get('display_name', m['service_id'])} ({m['taxonomy']})")

    # ── 获取所有 taxonomy ──
    taxonomies = sorted(set(m["taxonomy"] for m in manifests))
    print(f"\n📊 覆盖 {len(taxonomies)} 种 taxonomy:")
    for t in taxonomies:
        count = sum(1 for m in manifests if m["taxonomy"] == t)
        print(f"   • {t} ({count} 个Service)")

    # ── 生成任务 ──
    rng = random.Random(args.seed)
    tasks = generate_tasks(taxonomies, num_tasks=args.tasks, rng=rng)
    print(f"\n🎲 生成了 {len(tasks)} 个模拟任务请求 (seed={args.seed})")

    # 统计任务分布
    tax_dist: dict[str, int] = {}
    pref_dist: dict[str, int] = {}
    for t in tasks:
        tax_dist[t.taxonomy] = tax_dist.get(t.taxonomy, 0) + 1
        pref_dist[t.preference_profile] = pref_dist.get(t.preference_profile, 0) + 1

    print("   Taxonomy 分布:", {k: v for k, v in sorted(tax_dist.items())})
    print("   偏好分布:", {k: v for k, v in sorted(pref_dist.items())})

    # ── 运行实验 ──
    print(f"\n🔬 运行 A/B Test...")
    start_time = time.time()
    records = run_experiment(manifests, tasks, rng)
    elapsed = time.time() - start_time
    print(f"   完成! total {len(records)} 条选择记录 ({elapsed:.2f}s)")

    # ── 分析 ──
    analysis = analyze_results(records)

    # ── 输出 ──
    os.makedirs(args.output, exist_ok=True)

    # 保存 CSV
    csv_path = os.path.join(args.output, "ab_test_results.csv")
    save_csv(records, csv_path)
    print(f"\n💾 CSV 已保存: {csv_path}")

    # 保存分析 JSON
    json_path = os.path.join(args.output, "ab_test_analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"💾 分析 JSON 已保存: {json_path}")

    # 打印摘要
    print_summary(analysis, args.tasks)


if __name__ == "__main__":
    main()
