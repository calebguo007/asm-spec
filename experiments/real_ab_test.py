#!/usr/bin/env python3
"""ASM Real A/B Test — 通过 Knot API 调用真实 LLM Service。

核心思路：
  - 使用 10 个标准化 prompt，分别通过 Knot API 发送
  - 记录每次调用的真实延迟、响应质量（由评估函数打分）、token 使用
  - 对比 ASM TOPSIS 推荐 vs 随机选择 vs 最贵策略的实际效果
  - 生成带Statistically significant性检验的报告

Usage:
    python real_ab_test.py --token YOUR_KNOT_TOKEN
    python real_ab_test.py --token YOUR_KNOT_TOKEN --prompts 5
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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("需要 requests 库: pip install requests")
    sys.exit(1)

# ── 将 scorer 加入 sys.path
_SCORER_DIR = str(Path(__file__).resolve().parent.parent / "scorer")
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (
    Preferences,
    ServiceVector,
    load_manifests,
    parse_manifest,
    score_topsis,
)


# ============================================================
# 常量
# ============================================================

KNOT_API_BASE = "https://knot.woa.com/apigw/api/v1/agents/agui"
KNOT_AGENT_ID = "1b736d1c48cf451d894dda63434df0f9"

# 10 个标准化Test prompt，涵盖不同任务类型
TEST_PROMPTS = [
    {"id": "fact_1", "category": "factual", "prompt": "What is the capital of France? Answer in one sentence.", "expected_keywords": ["Paris"]},
    {"id": "fact_2", "category": "factual", "prompt": "What year did World War II end? Answer in one sentence.", "expected_keywords": ["1945"]},
    {"id": "reasoning_1", "category": "reasoning", "prompt": "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly? Explain in 2-3 sentences.", "expected_keywords": ["cannot", "no"]},
    {"id": "reasoning_2", "category": "reasoning", "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? Show your work.", "expected_keywords": ["0.05", "5 cents"]},
    {"id": "creative_1", "category": "creative", "prompt": "Write a haiku about artificial intelligence.", "expected_keywords": []},
    {"id": "creative_2", "category": "creative", "prompt": "Describe a sunset in exactly 20 words.", "expected_keywords": []},
    {"id": "code_1", "category": "code", "prompt": "Write a Python function that checks if a string is a palindrome. Include docstring.", "expected_keywords": ["def", "palindrome"]},
    {"id": "code_2", "category": "code", "prompt": "Write a JavaScript function that finds the maximum value in an array without using Math.max.", "expected_keywords": ["function", "max"]},
    {"id": "summary_1", "category": "summary", "prompt": "Summarize the concept of 'machine learning' in exactly 3 bullet points.", "expected_keywords": ["data", "learn"]},
    {"id": "instruct_1", "category": "instruction", "prompt": "List exactly 5 programming languages sorted alphabetically. Output only the list, one per line.", "expected_keywords": []},
]


# ============================================================
# 数据Structure
# ============================================================

@dataclass
class RealTestResult:
    """单次真实 API 调用的结果。"""
    prompt_id: str
    category: str
    group: str
    service_id: str
    display_name: str
    declared_cost: float
    declared_latency: float
    declared_quality: float
    topsis_score: float
    actual_latency_s: float
    response_length: int
    has_expected_keywords: bool
    quality_score: float
    response_text: str
    error: str | None = None


# ============================================================
# Knot API 调用
# ============================================================

def call_knot_api(
    token: str,
    prompt: str,
    agent_id: str = KNOT_AGENT_ID,
    timeout: int = 60,
) -> tuple[str, float]:
    """调用 Knot API，返回 (响应文本, 延迟秒数)。"""
    url = f"{KNOT_API_BASE}/{agent_id}"
    headers = {
        "Content-Type": "application/json",
        "x-knot-api-token": token,
    }
    body = {
        "input": {
            "message": prompt,
            "conversation_id": "",
            "stream": False,
        }
    }

    start = time.time()
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code != 200:
            return f"[ERROR: HTTP {resp.status_code}] {resp.text[:200]}", elapsed

        data = resp.json()
        content = data.get("rawEvent", {}).get("content", "")
        return content, elapsed

    except requests.Timeout:
        elapsed = time.time() - start
        return "[ERROR: Timeout]", elapsed
    except Exception as e:
        elapsed = time.time() - start
        return f"[ERROR: {str(e)[:200]}]", elapsed


# ============================================================
# 质量评估
# ============================================================

def evaluate_response(prompt_info: dict, response: str) -> tuple[float, bool]:
    """评估响应质量。返回 (quality_score, has_keywords)。"""
    score = 0.0
    has_keywords = True

    if response and len(response.strip()) > 0:
        score += 0.2
    if len(response.strip()) > 10:
        score += 0.2
    if not response.startswith("[ERROR"):
        score += 0.2

    expected = prompt_info.get("expected_keywords", [])
    if expected:
        response_lower = response.lower()
        found = sum(1 for kw in expected if kw.lower() in response_lower)
        keyword_ratio = found / len(expected)
        score += 0.3 * keyword_ratio
        has_keywords = keyword_ratio >= 0.5
    else:
        score += 0.3
        has_keywords = True

    resp_len = len(response.strip())
    if 10 < resp_len < 5000:
        score += 0.1

    return round(min(score, 1.0), 4), has_keywords


# ============================================================
# 实验执行
# ============================================================

def run_real_ab_test(
    token: str,
    manifests: list[dict],
    prompts: list[dict],
    seed: int = 2024,
) -> list[RealTestResult]:
    """执行Real A/B Test。"""
    rng = random.Random(seed)

    llm_manifests = [m for m in manifests if m["taxonomy"].startswith("ai.llm")]
    if len(llm_manifests) < 2:
        print("❌ 需要至少 2 个 LLM manifest")
        return []

    llm_services = [parse_manifest(m) for m in llm_manifests]
    print(f"\n📋 LLM 候选Service ({len(llm_services)} 个):")
    for s in llm_services:
        print(f"   • {s.display_name} (cost=${s.cost_per_unit:.6f}, quality={s.quality_score:.3f}, latency={s.latency_seconds:.2f}s)")

    preference_scenarios = {
        "balanced":      Preferences(cost=0.30, quality=0.30, speed=0.20, reliability=0.20),
        "cost_first":    Preferences(cost=0.55, quality=0.25, speed=0.10, reliability=0.10),
        "quality_first": Preferences(cost=0.10, quality=0.55, speed=0.20, reliability=0.15),
        "speed_first":   Preferences(cost=0.15, quality=0.20, speed=0.55, reliability=0.10),
    }

    results: list[RealTestResult] = []
    total_calls = len(prompts) * 3
    call_count = 0

    for prompt_info in prompts:
        scenario_name = rng.choice(list(preference_scenarios.keys()))
        prefs = preference_scenarios[scenario_name]

        scored = score_topsis(llm_services, prefs)
        asm_pick = scored[0].service
        random_pick = rng.choice(llm_services)
        expensive_pick = max(llm_services, key=lambda s: s.cost_per_unit)

        topsis_map = {r.service.service_id: r.total_score for r in scored}

        strategies = [
            ("A_ASM", asm_pick),
            ("B_Random", random_pick),
            ("C_Expensive", expensive_pick),
        ]

        for group, service in strategies:
            call_count += 1
            print(f"\r  🔄 [{call_count}/{total_calls}] {group} | {prompt_info['id']} | {service.display_name}", end="", flush=True)

            response_text, actual_latency = call_knot_api(token, prompt_info["prompt"])
            quality_score, has_keywords = evaluate_response(prompt_info, response_text)

            results.append(RealTestResult(
                prompt_id=prompt_info["id"],
                category=prompt_info["category"],
                group=group,
                service_id=service.service_id,
                display_name=service.display_name,
                declared_cost=service.cost_per_unit,
                declared_latency=service.latency_seconds,
                declared_quality=service.quality_score,
                topsis_score=topsis_map.get(service.service_id, 0.0),
                actual_latency_s=round(actual_latency, 4),
                response_length=len(response_text),
                has_expected_keywords=has_keywords,
                quality_score=quality_score,
                response_text=response_text[:500],
            ))

            time.sleep(1.0)

    print("\n")
    return results


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

def _normal_cdf(x: float) -> float:
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


def analyze_real_results(results: list[RealTestResult]) -> dict[str, Any]:
    """分析Real A/B Test结果。"""
    groups: dict[str, list[RealTestResult]] = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
    for r in results:
        groups[r.group].append(r)

    summary = {}
    for g_name, g_records in groups.items():
        summary[g_name] = {
            "count": len(g_records),
            "topsis_mean": round(_mean([r.topsis_score for r in g_records]), 4),
            "topsis_std": round(_std([r.topsis_score for r in g_records]), 4),
            "declared_cost_mean": round(_mean([r.declared_cost for r in g_records]), 8),
            "declared_latency_mean": round(_mean([r.declared_latency for r in g_records]), 4),
            "declared_quality_mean": round(_mean([r.declared_quality for r in g_records]), 4),
            "actual_latency_mean": round(_mean([r.actual_latency_s for r in g_records]), 4),
            "actual_latency_std": round(_std([r.actual_latency_s for r in g_records]), 4),
            "quality_score_mean": round(_mean([r.quality_score for r in g_records]), 4),
            "quality_score_std": round(_std([r.quality_score for r in g_records]), 4),
            "keyword_hit_rate": round(_mean([1.0 if r.has_expected_keywords else 0.0 for r in g_records]), 4),
        }

    t_tests = {}
    for metric_attr in ["topsis_score", "actual_latency_s", "quality_score"]:
        a_vals = [getattr(r, metric_attr) for r in groups["A_ASM"]]
        b_vals = [getattr(r, metric_attr) for r in groups["B_Random"]]
        c_vals = [getattr(r, metric_attr) for r in groups["C_Expensive"]]
        t_ab, p_ab = t_test(a_vals, b_vals)
        t_ac, p_ac = t_test(a_vals, c_vals)
        t_tests[metric_attr] = {
            "A_vs_B": {"t": round(t_ab, 4), "p": round(p_ab, 6), "significant": p_ab < 0.05},
            "A_vs_C": {"t": round(t_ac, 4), "p": round(p_ac, 6), "significant": p_ac < 0.05},
        }

    trust_analysis = {}
    for g_name, g_records in groups.items():
        latency_deltas = []
        for r in g_records:
            if r.declared_latency > 0:
                delta = abs(r.actual_latency_s - r.declared_latency) / r.declared_latency
                latency_deltas.append(delta)
        trust_analysis[g_name] = {
            "latency_delta_mean": round(_mean(latency_deltas), 4),
            "latency_delta_std": round(_std(latency_deltas), 4),
        }

    selection_freq = {}
    for g_name, g_records in groups.items():
        freq: dict[str, int] = {}
        for r in g_records:
            freq[r.service_id] = freq.get(r.service_id, 0) + 1
        selection_freq[g_name] = freq

    category_breakdown = {}
    categories = sorted(set(r.category for r in results))
    for cat in categories:
        cat_records = [r for r in results if r.category == cat]
        cat_groups: dict[str, list[RealTestResult]] = {"A_ASM": [], "B_Random": [], "C_Expensive": []}
        for r in cat_records:
            cat_groups[r.group].append(r)
        cat_summary = {}
        for g_name, g_recs in cat_groups.items():
            if g_recs:
                cat_summary[g_name] = {
                    "count": len(g_recs),
                    "topsis_mean": round(_mean([r.topsis_score for r in g_recs]), 4),
                    "quality_mean": round(_mean([r.quality_score for r in g_recs]), 4),
                    "latency_mean": round(_mean([r.actual_latency_s for r in g_recs]), 4),
                }
        category_breakdown[cat] = cat_summary

    return {
        "experiment_info": {
            "timestamp": datetime.now().isoformat(),
            "total_api_calls": len(results),
            "prompts_used": len(set(r.prompt_id for r in results)),
            "type": "real_api_calls",
        },
        "summary": summary,
        "t_tests": t_tests,
        "trust_analysis": trust_analysis,
        "selection_freq": selection_freq,
        "category_breakdown": category_breakdown,
    }


def print_real_report(analysis: dict[str, Any]) -> None:
    """打印Real A/B Test报告。"""
    info = analysis["experiment_info"]
    summary = analysis["summary"]
    t_tests = analysis["t_tests"]
    trust = analysis["trust_analysis"]

    print("\n" + "=" * 78)
    print("  ASM Real A/B Test报告")
    print("  (Real API Calls — NOT Simulated)")
    print("=" * 78)
    print(f"\n  时间: {info['timestamp']}")
    print(f"  总 API 调用数: {info['total_api_calls']}")
    print(f"  Test prompt 数: {info['prompts_used']}")
    print(f"  TestType: 真实 API 调用 🔴")

    sep = "-" * 78
    print(f"\n{sep}")
    print(f"  {'指标':<24} {'A_ASM':>16} {'B_Random':>16} {'C_Expensive':>16}")
    print(sep)

    metrics = [
        ("TOPSIS 得分", "topsis_mean", "topsis_std"),
        ("声明成本 ($/unit)", "declared_cost_mean", None),
        ("声明延迟 (s)", "declared_latency_mean", None),
        ("声明质量 (0-1)", "declared_quality_mean", None),
        ("actual latency (s)", "actual_latency_mean", "actual_latency_std"),
        ("响应质量 (0-1)", "quality_score_mean", "quality_score_std"),
        ("关键词命中率", "keyword_hit_rate", None),
    ]

    for label, mean_key, std_key in metrics:
        vals = []
        for g in ["A_ASM", "B_Random", "C_Expensive"]:
            m = summary[g].get(mean_key, 0)
            if std_key:
                s = summary[g].get(std_key, 0)
                vals.append(f"{m:.4f}±{s:.4f}")
            else:
                vals.append(f"{m:.6f}")
        print(f"  {label:<24} {vals[0]:>16} {vals[1]:>16} {vals[2]:>16}")

    print(sep)

    print(f"\n  Statistically significant性 (Welch's t-test, α=0.05):")
    print(sep)
    metric_labels = {
        "topsis_score": "TOPSIS 得分",
        "actual_latency_s": "actual latency",
        "quality_score": "响应质量",
    }
    for metric, label in metric_labels.items():
        ab = t_tests[metric]["A_vs_B"]
        ac = t_tests[metric]["A_vs_C"]
        ab_str = f"t={ab['t']:+.3f} p={ab['p']:.4f}" + (" ✅" if ab["significant"] else "")
        ac_str = f"t={ac['t']:+.3f} p={ac['p']:.4f}" + (" ✅" if ac["significant"] else "")
        print(f"  {label:<24} {ab_str:>24} {ac_str:>24}")
    print(sep)

    print(f"\n  声明值 vs 实际值偏差 (延迟):")
    for g_name in ["A_ASM", "B_Random", "C_Expensive"]:
        td = trust[g_name]
        print(f"  {g_name:<16} 平均Delta: {td['latency_delta_mean']:.2%} ± {td['latency_delta_std']:.2%}")

    print(f"\n  Service选择频率:")
    for g_name in ["A_ASM", "B_Random", "C_Expensive"]:
        freq = analysis["selection_freq"][g_name]
        total = summary[g_name]["count"]
        print(f"\n  {g_name}:")
        for sid, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            bar = "█" * int(pct / 3)
            print(f"    {sid:<45} {count:>3}x ({pct:>5.1f}%) {bar}")

    a_topsis = summary["A_ASM"]["topsis_mean"]
    b_topsis = summary["B_Random"]["topsis_mean"]
    c_topsis = summary["C_Expensive"]["topsis_mean"]
    improvement = ((a_topsis - b_topsis) / b_topsis * 100) if b_topsis > 0 else 0

    print(f"\n{'=' * 78}")
    print(f"  📊 关键结论:")
    print(f"  1. ASM TOPSIS vs 随机: 得分提升 {improvement:+.1f}% ({a_topsis:.4f} vs {b_topsis:.4f})")
    print(f"  2. ASM TOPSIS vs 最贵: {a_topsis:.4f} vs {c_topsis:.4f}")
    topsis_sig = t_tests["topsis_score"]["A_vs_B"]["significant"]
    print(f"  3. TOPSIS A vs B 显著性: p={t_tests['topsis_score']['A_vs_B']['p']:.6f} {'✅ 显著' if topsis_sig else '⚠️ Not significant'}")
    print()


def save_results(results: list[RealTestResult], analysis: dict[str, Any], output_dir: str) -> None:
    """保存结果到文件。"""
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "real_ab_test_results.csv")
    fieldnames = [
        "prompt_id", "category", "group", "service_id", "display_name",
        "declared_cost", "declared_latency", "declared_quality", "topsis_score",
        "actual_latency_s", "response_length", "has_expected_keywords",
        "quality_score", "response_text",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "prompt_id": r.prompt_id, "category": r.category,
                "group": r.group, "service_id": r.service_id,
                "display_name": r.display_name,
                "declared_cost": f"{r.declared_cost:.8f}",
                "declared_latency": f"{r.declared_latency:.4f}",
                "declared_quality": f"{r.declared_quality:.4f}",
                "topsis_score": f"{r.topsis_score:.4f}",
                "actual_latency_s": f"{r.actual_latency_s:.4f}",
                "response_length": r.response_length,
                "has_expected_keywords": r.has_expected_keywords,
                "quality_score": f"{r.quality_score:.4f}",
                "response_text": r.response_text[:200],
            })
    print(f"💾 CSV: {csv_path}")

    json_path = os.path.join(output_dir, "real_ab_test_analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"💾 JSON: {json_path}")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ASM Real A/B Test — 通过 Knot API 调用真实 LLM")
    parser.add_argument("--token", "-t", required=True, help="Knot API token")
    parser.add_argument("--manifests", "-m", default=str(Path(__file__).resolve().parent.parent / "manifests"), help="ASM manifests 目录")
    parser.add_argument("--output", "-o", default=str(Path(__file__).resolve().parent / "results"), help="输出目录")
    parser.add_argument("--prompts", "-n", type=int, default=10, help="使用的 prompt 数量 (1-10)")
    parser.add_argument("--seed", "-s", type=int, default=2024, help="随机种子")
    args = parser.parse_args()

    manifests = load_manifests(args.manifests)
    if not manifests:
        print(f"❌ 在 {args.manifests} 中未找到 .asm.json 文件")
        sys.exit(1)
    print(f"✅ Load了 {len(manifests)} 个 ASM manifests")

    print(f"\n🔑 验证 Knot API token...")
    test_resp, test_lat = call_knot_api(args.token, "Say 'ok'")
    if test_resp.startswith("[ERROR"):
        print(f"❌ API 调用失败: {test_resp}")
        sys.exit(1)
    print(f"✅ API 连接正常 (延迟: {test_lat:.2f}s)")

    num_prompts = min(max(args.prompts, 1), len(TEST_PROMPTS))
    prompts = TEST_PROMPTS[:num_prompts]
    total_calls = num_prompts * 3
    print(f"\n📋 实验Configuration:")
    print(f"   Prompts: {num_prompts} 个")
    print(f"   策略: 3 组 (ASM TOPSIS / Random / Expensive)")
    print(f"   总 API 调用: {total_calls} 次")
    print(f"   预计耗时: ~{total_calls * 3:.0f}s")

    print(f"\n🔬 开始Real A/B Test...")
    results = run_real_ab_test(token=args.token, manifests=manifests, prompts=prompts, seed=args.seed)

    if not results:
        print("❌ 没有收集到结果")
        sys.exit(1)

    print(f"✅ 收集了 {len(results)} 条真实Test记录")
    analysis = analyze_real_results(results)
    save_results(results, analysis, args.output)
    print_real_report(analysis)


if __name__ == "__main__":
    main()
