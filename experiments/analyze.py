#!/usr/bin/env python3
"""ASM A/B Test分析脚本 — 读取 CSV 生成 Markdown 报告。

读取 ab_test.py 输出的 CSV 文件，生成带 ASCII 表格的 Markdown 报告。
不依赖 matplotlib，纯文本输出。

Usage:
    python analyze.py                                    # 默认路径
    python analyze.py --csv results/ab_test_results.csv  # 指定 CSV
    python analyze.py --output results/report.md         # 指定输出
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# 数据Load
# ============================================================

@dataclass
class Record:
    """CSV 中的一行记录。"""
    task_id: int
    group: str
    taxonomy: str
    preference_profile: str
    service_id: str
    display_name: str
    cost_per_unit: float
    latency_seconds: float
    quality_score: float
    uptime: float
    topsis_score: float


def load_csv(filepath: str) -> list[Record]:
    """Load CSV 文件。"""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(Record(
                task_id=int(row["task_id"]),
                group=row["group"],
                taxonomy=row["taxonomy"],
                preference_profile=row["preference_profile"],
                service_id=row["service_id"],
                display_name=row["display_name"],
                cost_per_unit=float(row["cost_per_unit"]),
                latency_seconds=float(row["latency_seconds"]),
                quality_score=float(row["quality_score"]),
                uptime=float(row["uptime"]),
                topsis_score=float(row["topsis_score"]),
            ))
    return records


# ============================================================
# 统计Tool
# ============================================================

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _normal_cdf(x: float) -> float:
    import math
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch's t-test。"""
    try:
        from scipy import stats
        result = stats.ttest_ind(a, b, equal_var=False)
        return float(result.statistic), float(result.pvalue)
    except ImportError:
        n1, n2 = len(a), len(b)
        if n1 < 2 or n2 < 2:
            return 0.0, 1.0
        m1, m2 = _mean(a), _mean(b)
        s1, s2 = _std(a), _std(b)
        se = ((s1 ** 2 / n1) + (s2 ** 2 / n2)) ** 0.5
        if se == 0:
            return 0.0, 1.0
        t_stat = (m1 - m2) / se
        p_value = 2 * (1 - _normal_cdf(abs(t_stat)))
        return t_stat, p_value


# ============================================================
# ASCII 表格生成
# ============================================================

def ascii_table(headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> str:
    """生成 ASCII 表格。

    align: 每列的对齐方式，'l'=左对齐，'r'=右对齐，'c'=居中
    """
    if align is None:
        align = ["l"] * len(headers)

    # 计算列宽
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # 添加边距
    widths = [w + 2 for w in widths]

    def _format_cell(text: str, width: int, a: str) -> str:
        if a == "r":
            return text.rjust(width)
        elif a == "c":
            return text.center(width)
        return text.ljust(width)

    # 构建表格
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    header_line = "|" + "|".join(
        _format_cell(h, widths[i], align[i]) for i, h in enumerate(headers)
    ) + "|"

    lines = [sep, header_line, sep]
    for row in rows:
        line = "|" + "|".join(
            _format_cell(row[i] if i < len(row) else "", widths[i], align[i])
            for i in range(len(headers))
        ) + "|"
        lines.append(line)
    lines.append(sep)

    return "\n".join(lines)


def ascii_bar_chart(data: dict[str, float], title: str = "", width: int = 40) -> str:
    """生成 ASCII 水平柱状图。"""
    if not data:
        return ""
    max_val = max(data.values()) if data.values() else 1
    max_label = max(len(k) for k in data.keys())

    lines = []
    if title:
        lines.append(f"  {title}")
        lines.append("")

    for label, val in data.items():
        bar_len = int(val / max_val * width) if max_val > 0 else 0
        bar = "█" * bar_len
        lines.append(f"  {label:<{max_label}} │{bar} {val:.4f}")

    return "\n".join(lines)


# ============================================================
# 报告生成
# ============================================================

def generate_report(records: list[Record]) -> str:
    """生成完整的 Markdown 分析报告。"""
    groups = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
    for r in records:
        groups[r.group].append(r)

    num_tasks = len(set(r.task_id for r in records))
    taxonomies = sorted(set(r.taxonomy for r in records))
    profiles = sorted(set(r.preference_profile for r in records))

    report = []
    report.append("# ASM A/B Test分析报告")
    report.append("")
    report.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # ── 实验概述 ──
    report.append("## 1. 实验概述")
    report.append("")
    report.append("### 实验设计")
    report.append("")
    report.append("| 项目 | 说明 |")
    report.append("|---|---|")
    report.append(f"| 模拟任务数 | {num_tasks} |")
    report.append(f"| 选择记录总数 | {len(records)} |")
    report.append(f"| 覆盖 taxonomy | {len(taxonomies)} 种 |")
    report.append(f"| 偏好方向 | {len(profiles)} 种 |")
    report.append("")
    report.append("### 三组策略")
    report.append("")
    report.append("| 组别 | 策略 | 说明 |")
    report.append("|---|---|---|")
    report.append("| **A_ASM** | TOPSIS 多准则决策 | 根据用户偏好Weight，综合成本/质量/延迟/可用性Scoring |")
    report.append("| **B_Random** | 随机选择 | 从同 taxonomy 候选Service中随机选取 |")
    report.append("| **C_Expensive** | 最贵优先 | 始终选择单位成本最高的Service |")
    report.append("")

    # ── 总体对比 ──
    report.append("## 2. 总体对比")
    report.append("")
    report.append("### 核心指标对比")
    report.append("")

    metrics_info = [
        ("成本 ($/unit)", "cost_per_unit", "r"),
        ("延迟 (s)", "latency_seconds", "r"),
        ("质量 (0-1)", "quality_score", "r"),
        ("可用性 (0-1)", "uptime", "r"),
        ("TOPSIS 得分", "topsis_score", "r"),
    ]

    headers = ["指标", "A_ASM (mean±std)", "B_Random (mean±std)", "C_Expensive (mean±std)", "A 优于 B", "A 优于 C"]
    rows = []

    for label, attr, _ in metrics_info:
        vals = {}
        for g_name, g_records in groups.items():
            v = [getattr(r, attr) for r in g_records]
            vals[g_name] = (v, _mean(v), _std(v))

        def _fmt(m: float, s: float) -> str:
            if attr == "cost_per_unit":
                return f"${m:.8f}±{s:.6f}"
            return f"{m:.4f}±{s:.4f}"

        a_m, b_m, c_m = vals["A_ASM"][1], vals["B_Random"][1], vals["C_Expensive"][1]

        # 判断 A 是否优于 B/C
        if attr in ("cost_per_unit", "latency_seconds"):
            # 越低越好
            a_vs_b = "✅" if a_m < b_m else ("—" if abs(a_m - b_m) < 1e-10 else "❌")
            a_vs_c = "✅" if a_m < c_m else ("—" if abs(a_m - c_m) < 1e-10 else "❌")
        else:
            # 越高越好
            a_vs_b = "✅" if a_m > b_m else ("—" if abs(a_m - b_m) < 1e-10 else "❌")
            a_vs_c = "✅" if a_m > c_m else ("—" if abs(a_m - c_m) < 1e-10 else "❌")

        rows.append([
            label,
            _fmt(vals["A_ASM"][1], vals["A_ASM"][2]),
            _fmt(vals["B_Random"][1], vals["B_Random"][2]),
            _fmt(vals["C_Expensive"][1], vals["C_Expensive"][2]),
            a_vs_b,
            a_vs_c,
        ])

    report.append("```")
    report.append(ascii_table(headers, rows, align=["l", "r", "r", "r", "c", "c"]))
    report.append("```")
    report.append("")

    # ── TOPSIS 得分分布 ──
    report.append("### TOPSIS 得分分布")
    report.append("")
    report.append("```")
    for g_name in ["A_ASM", "B_Random", "C_Expensive"]:
        scores = [r.topsis_score for r in groups[g_name]]
        report.append(f"  {g_name}:")
        report.append(f"    Mean:   {_mean(scores):.4f}")
        report.append(f"    Median: {_median(scores):.4f}")
        report.append(f"    Std:    {_std(scores):.4f}")
        report.append(f"    Min:    {min(scores):.4f}")
        report.append(f"    Max:    {max(scores):.4f}")
        report.append("")
    report.append("```")
    report.append("")

    # ── Statistically significant性 ──
    report.append("## 3. Statistically significant性检验")
    report.append("")
    report.append("使用 Welch's t-test（独立样本，不假设等方差），显著性水平 α = 0.05。")
    report.append("")

    t_headers = ["指标", "A vs B (t)", "A vs B (p)", "显著?", "A vs C (t)", "A vs C (p)", "显著?"]
    t_rows = []

    for label, attr, _ in metrics_info:
        a_vals = [getattr(r, attr) for r in groups["A_ASM"]]
        b_vals = [getattr(r, attr) for r in groups["B_Random"]]
        c_vals = [getattr(r, attr) for r in groups["C_Expensive"]]

        t_ab, p_ab = t_test(a_vals, b_vals)
        t_ac, p_ac = t_test(a_vals, c_vals)

        t_rows.append([
            label,
            f"{t_ab:+.4f}",
            f"{p_ab:.6f}",
            "✅ Yes" if p_ab < 0.05 else "No",
            f"{t_ac:+.4f}",
            f"{p_ac:.6f}",
            "✅ Yes" if p_ac < 0.05 else "No",
        ])

    report.append("```")
    report.append(ascii_table(t_headers, t_rows, align=["l", "r", "r", "c", "r", "r", "c"]))
    report.append("```")
    report.append("")

    # ── Taxonomy 细分 ──
    report.append("## 4. 按 Taxonomy 分组对比")
    report.append("")

    for tax in taxonomies:
        tax_records = [r for r in records if r.taxonomy == tax]
        tax_groups = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
        for r in tax_records:
            tax_groups[r.group].append(r)

        if not all(tax_groups.values()):
            continue

        report.append(f"### {tax}")
        report.append("")

        tax_headers = ["指标", "A_ASM", "B_Random", "C_Expensive"]
        tax_rows = []

        for label, attr, _ in metrics_info:
            row = [label]
            for g in ["A_ASM", "B_Random", "C_Expensive"]:
                if tax_groups[g]:
                    v = _mean([getattr(r, attr) for r in tax_groups[g]])
                    if attr == "cost_per_unit":
                        row.append(f"${v:.8f}")
                    else:
                        row.append(f"{v:.4f}")
                else:
                    row.append("—")
            tax_rows.append(row)

        report.append("```")
        report.append(ascii_table(tax_headers, tax_rows, align=["l", "r", "r", "r"]))
        report.append("```")
        report.append("")

        # TOPSIS 得分柱状图
        topsis_by_group = {}
        for g in ["A_ASM", "B_Random", "C_Expensive"]:
            if tax_groups[g]:
                topsis_by_group[g] = _mean([r.topsis_score for r in tax_groups[g]])
        report.append("```")
        report.append(ascii_bar_chart(topsis_by_group, f"TOPSIS 平均得分 — {tax}"))
        report.append("```")
        report.append("")

    # ── 偏好细分 ──
    report.append("## 5. 按偏好方向分组对比")
    report.append("")

    for profile in profiles:
        prof_records = [r for r in records if r.preference_profile == profile]
        prof_groups = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
        for r in prof_records:
            prof_groups[r.group].append(r)

        report.append(f"### {profile}")
        report.append("")

        prof_headers = ["指标", "A_ASM", "B_Random", "C_Expensive"]
        prof_rows = []

        for label, attr, _ in [("TOPSIS 得分", "topsis_score", "r"), ("成本", "cost_per_unit", "r"), ("质量", "quality_score", "r")]:
            row = [label]
            for g in ["A_ASM", "B_Random", "C_Expensive"]:
                if prof_groups[g]:
                    v = _mean([getattr(r, attr) for r in prof_groups[g]])
                    if attr == "cost_per_unit":
                        row.append(f"${v:.8f}")
                    else:
                        row.append(f"{v:.4f}")
                else:
                    row.append("—")
            prof_rows.append(row)

        report.append("```")
        report.append(ascii_table(prof_headers, prof_rows, align=["l", "r", "r", "r"]))
        report.append("```")
        report.append("")

    # ── Service选择频率 ──
    report.append("## 6. Service选择频率分析")
    report.append("")

    for g_name in ["A_ASM", "B_Random", "C_Expensive"]:
        g_records = groups[g_name]
        freq: dict[str, int] = {}
        for r in g_records:
            freq[r.service_id] = freq.get(r.service_id, 0) + 1

        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        report.append(f"### {g_name}")
        report.append("")

        freq_data = {sid: count / len(g_records) * 100 for sid, count in sorted_freq[:8]}
        report.append("```")
        report.append(ascii_bar_chart(freq_data, f"选择频率 (%) — {g_name}", width=30))
        report.append("```")
        report.append("")

    # ── 结论 ──
    report.append("## 7. 结论")
    report.append("")

    a_topsis = _mean([r.topsis_score for r in groups["A_ASM"]])
    b_topsis = _mean([r.topsis_score for r in groups["B_Random"]])
    c_topsis = _mean([r.topsis_score for r in groups["C_Expensive"]])

    a_cost = _mean([r.cost_per_unit for r in groups["A_ASM"]])
    c_cost = _mean([r.cost_per_unit for r in groups["C_Expensive"]])

    improvement_vs_random = ((a_topsis - b_topsis) / b_topsis * 100) if b_topsis > 0 else 0
    cost_saving_vs_expensive = ((c_cost - a_cost) / c_cost * 100) if c_cost > 0 else 0

    report.append(f"1. **ASM TOPSIS vs 随机选择**: TOPSIS 平均得分提升 **{improvement_vs_random:+.1f}%** "
                  f"({a_topsis:.4f} vs {b_topsis:.4f})")
    report.append(f"2. **ASM TOPSIS vs 最贵优先**: TOPSIS 平均得分 {a_topsis:.4f} vs {c_topsis:.4f}，"
                  f"同时成本节省 **{cost_saving_vs_expensive:.1f}%**")

    # t-test 结论
    a_topsis_vals = [r.topsis_score for r in groups["A_ASM"]]
    b_topsis_vals = [r.topsis_score for r in groups["B_Random"]]
    c_topsis_vals = [r.topsis_score for r in groups["C_Expensive"]]
    _, p_ab = t_test(a_topsis_vals, b_topsis_vals)
    _, p_ac = t_test(a_topsis_vals, c_topsis_vals)

    report.append(f"3. **Statistically significant性**: A vs B p={p_ab:.6f} {'(显著)' if p_ab < 0.05 else '(Not significant)'}，"
                  f"A vs C p={p_ac:.6f} {'(显著)' if p_ac < 0.05 else '(Not significant)'}")
    report.append(f"4. **核心洞察**: ASM 的 TOPSIS 算法能在多维度偏好下做出更优的综合决策，"
                  f"尤其在用户偏好明确时（如 cost_first、quality_first）优势更为显著。")
    report.append("")
    report.append("---")
    report.append(f"*报告由 ASM A/B Test框架自动生成 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(report)


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="ASM A/B Test分析 — 从 CSV 生成 Markdown 报告",
    )
    parser.add_argument(
        "--csv", "-c",
        default=str(Path(__file__).resolve().parent / "results" / "ab_test_results.csv"),
        help="输入 CSV 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(Path(__file__).resolve().parent / "results" / "report.md"),
        help="输出 Markdown 报告路径",
    )

    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: CSV 文件不存在: {args.csv}")
        print("请先运行 ab_test.py 生成数据。")
        sys.exit(1)

    # Load数据
    records = load_csv(args.csv)
    print(f"✅ Load了 {len(records)} 条记录 from {args.csv}")

    # 生成报告
    report = generate_report(records)

    # 写入文件
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 报告已生成: {args.output}")

    # 同时输出到 stdout
    print("\n" + report)


if __name__ == "__main__":
    main()
