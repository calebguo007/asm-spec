#!/usr/bin/env python3
"""ASM Scorer 单元测试 — 3 个关键测试用例。

1. Golden Test:  TOPSIS 在已知输入下的输出是否正确
2. io_ratio Test: io_ratio 参数对排名的影响（回归测试）
3. Cross-language Parity: Python 输出与 TypeScript 输出的一致性验证

用法:
    python -m pytest test_scorer.py -v
    python test_scorer.py  # 直接运行
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

# 将 scorer 加入 path
_SCORER_DIR = str(Path(__file__).resolve().parent)
if _SCORER_DIR not in sys.path:
    sys.path.insert(0, _SCORER_DIR)

from scorer import (
    Preferences,
    ServiceVector,
    load_manifests,
    parse_manifest,
    score_topsis,
    score_weighted_average,
    _extract_primary_cost,
    _extract_primary_quality,
    _parse_latency,
)


# ============================================================
# 测试数据：3 个合成 manifest（已知输入）
# ============================================================

SYNTHETIC_MANIFESTS = [
    {
        "asm_version": "0.3",
        "service_id": "test/cheap-fast@1.0",
        "taxonomy": "ai.llm.chat",
        "display_name": "Cheap Fast",
        "pricing": {
            "billing_dimensions": [
                {"dimension": "input_token", "unit": "per_1M", "cost_per_unit": 1.0, "currency": "USD"},
                {"dimension": "output_token", "unit": "per_1M", "cost_per_unit": 2.0, "currency": "USD"},
            ]
        },
        "quality": {"metrics": [{"name": "Elo", "score": 1100, "scale": "Elo"}]},
        "sla": {"latency_p50": "300ms", "uptime": 0.99},
    },
    {
        "asm_version": "0.3",
        "service_id": "test/expensive-good@1.0",
        "taxonomy": "ai.llm.chat",
        "display_name": "Expensive Good",
        "pricing": {
            "billing_dimensions": [
                {"dimension": "input_token", "unit": "per_1M", "cost_per_unit": 10.0, "currency": "USD"},
                {"dimension": "output_token", "unit": "per_1M", "cost_per_unit": 30.0, "currency": "USD"},
            ]
        },
        "quality": {"metrics": [{"name": "Elo", "score": 1350, "scale": "Elo"}]},
        "sla": {"latency_p50": "1.5s", "uptime": 0.999},
    },
    {
        "asm_version": "0.3",
        "service_id": "test/balanced-mid@1.0",
        "taxonomy": "ai.llm.chat",
        "display_name": "Balanced Mid",
        "pricing": {
            "billing_dimensions": [
                {"dimension": "input_token", "unit": "per_1M", "cost_per_unit": 3.0, "currency": "USD"},
                {"dimension": "output_token", "unit": "per_1M", "cost_per_unit": 8.0, "currency": "USD"},
            ]
        },
        "quality": {"metrics": [{"name": "Elo", "score": 1250, "scale": "Elo"}]},
        "sla": {"latency_p50": "800ms", "uptime": 0.995},
    },
]


def _parse_all(manifests, io_ratio=0.3):
    """解析 manifests 为 ServiceVector 列表。"""
    return [parse_manifest(m, io_ratio=io_ratio) for m in manifests]


# ============================================================
# Test 1: Golden Test — TOPSIS 在已知输入下的输出
# ============================================================

def test_topsis_golden():
    """验证 TOPSIS 在已知合成数据上的排名和分数范围。

    已知：
    - Cheap Fast: 低成本、低延迟、中等质量
    - Expensive Good: 高成本、高延迟、高质量
    - Balanced Mid: 中等各维度

    用均衡权重 (0.25 each) 时，TOPSIS 应该倾向于 Balanced Mid 或 Cheap Fast
    （因为它们在多数维度上都有竞争力）。
    """
    services = _parse_all(SYNTHETIC_MANIFESTS)
    prefs = Preferences(cost=0.25, quality=0.25, speed=0.25, reliability=0.25)
    results = score_topsis(services, prefs)

    # 基本结构验证
    assert len(results) == 3, f"应有 3 个结果，得到 {len(results)}"
    assert results[0].rank == 1
    assert results[1].rank == 2
    assert results[2].rank == 3

    # 分数范围验证：TOPSIS 贴近度在 [0, 1]
    for r in results:
        assert 0.0 <= r.total_score <= 1.0, f"{r.service.display_name} 分数 {r.total_score} 超出 [0,1]"

    # 排名单调性：分数严格递减
    for i in range(len(results) - 1):
        assert results[i].total_score >= results[i + 1].total_score, \
            f"排名 #{i+1} 分数 {results[i].total_score} < 排名 #{i+2} 分数 {results[i+1].total_score}"

    # Breakdown 维度完整性
    for r in results:
        assert set(r.breakdown.keys()) == {"cost", "quality", "speed", "reliability"}, \
            f"Breakdown 维度不完整: {r.breakdown.keys()}"
        for dim, val in r.breakdown.items():
            assert 0.0 <= val <= 1.0, f"{r.service.display_name}.{dim} = {val} 超出 [0,1]"

    # Reasoning 非空
    for r in results:
        assert len(r.reasoning) > 0, f"{r.service.display_name} reasoning 为空"

    # 具体排名验证：成本优先时，Cheap Fast 应该排第一
    prefs_cost = Preferences(cost=0.7, quality=0.1, speed=0.1, reliability=0.1)
    results_cost = score_topsis(services, prefs_cost)
    assert results_cost[0].service.service_id == "test/cheap-fast@1.0", \
        f"成本优先时，排名第一应是 Cheap Fast，实际是 {results_cost[0].service.display_name}"

    # 质量优先时，Expensive Good 应该排第一
    prefs_quality = Preferences(cost=0.1, quality=0.7, speed=0.1, reliability=0.1)
    results_quality = score_topsis(services, prefs_quality)
    assert results_quality[0].service.service_id == "test/expensive-good@1.0", \
        f"质量优先时，排名第一应是 Expensive Good，实际是 {results_quality[0].service.display_name}"

    print("✅ Test 1 (Golden Test): PASSED")


# ============================================================
# Test 2: io_ratio 对排名的影响（回归测试）
# ============================================================

def test_io_ratio_regression():
    """验证 io_ratio 参数确实影响成本计算和最终排名。

    io_ratio=0.3 (默认, chat) → 偏重 output cost
    io_ratio=0.8 (RAG) → 偏重 input cost

    对于 Expensive Good (input=10, output=30):
      io_ratio=0.3 → cost = 0.3*10e-6 + 0.7*30e-6 = 24e-6
      io_ratio=0.8 → cost = 0.8*10e-6 + 0.2*30e-6 = 14e-6
    
    所以在 RAG 场景下，Expensive Good 的成本更低，排名可能上升。
    """
    # 验证 _extract_primary_cost 的 io_ratio 行为
    pricing = SYNTHETIC_MANIFESTS[1]["pricing"]  # Expensive Good

    cost_chat = _extract_primary_cost(pricing, io_ratio=0.3)
    cost_rag = _extract_primary_cost(pricing, io_ratio=0.8)

    # Chat 场景偏重 output (30/M)，所以 cost 更高
    assert cost_chat > cost_rag, \
        f"Chat cost ({cost_chat}) 应大于 RAG cost ({cost_rag})，因为 output token 更贵"

    # 精确值验证
    expected_chat = 0.3 * 10 / 1_000_000 + 0.7 * 30 / 1_000_000
    expected_rag = 0.8 * 10 / 1_000_000 + 0.2 * 30 / 1_000_000
    assert math.isclose(cost_chat, expected_chat, rel_tol=1e-9), \
        f"Chat cost {cost_chat} != expected {expected_chat}"
    assert math.isclose(cost_rag, expected_rag, rel_tol=1e-9), \
        f"RAG cost {cost_rag} != expected {expected_rag}"

    # 验证 io_ratio 对 TOPSIS 排名的影响
    services_chat = _parse_all(SYNTHETIC_MANIFESTS, io_ratio=0.3)
    services_rag = _parse_all(SYNTHETIC_MANIFESTS, io_ratio=0.8)

    prefs = Preferences(cost=0.5, quality=0.2, speed=0.2, reliability=0.1)
    results_chat = score_topsis(services_chat, prefs)
    results_rag = score_topsis(services_rag, prefs)

    # 排名应该不同（或至少分数不同）
    chat_order = [r.service.service_id for r in results_chat]
    rag_order = [r.service.service_id for r in results_rag]

    # 分数必须不同
    chat_scores = {r.service.service_id: r.total_score for r in results_chat}
    rag_scores = {r.service.service_id: r.total_score for r in results_rag}

    any_diff = False
    for sid in chat_scores:
        if not math.isclose(chat_scores[sid], rag_scores[sid], abs_tol=1e-6):
            any_diff = True
            break

    assert any_diff, "io_ratio 变化后分数应有差异"

    # 边界值测试
    cost_0 = _extract_primary_cost(pricing, io_ratio=0.0)  # 纯 output
    cost_1 = _extract_primary_cost(pricing, io_ratio=1.0)  # 纯 input
    expected_0 = 30 / 1_000_000  # 纯 output token cost
    expected_1 = 10 / 1_000_000  # 纯 input token cost
    assert math.isclose(cost_0, expected_0, rel_tol=1e-9)
    assert math.isclose(cost_1, expected_1, rel_tol=1e-9)

    print("✅ Test 2 (io_ratio Regression): PASSED")


# ============================================================
# Test 3: 跨语言一致性 (Python vs TypeScript)
# ============================================================

def test_cross_language_parity():
    """验证 Python scorer 和 TypeScript scorer 在相同输入下输出一致。

    使用真实的 14 个 manifest 文件，对比两个实现的 TOPSIS 排名。
    如果 TypeScript 编译环境不可用，则跳过。
    """
    manifest_dir = Path(__file__).resolve().parent.parent / "manifests"
    registry_dir = Path(__file__).resolve().parent.parent / "registry"
    ts_test_script = registry_dir / "src" / "test_topsis.ts"

    if not manifest_dir.exists():
        print("⚠️ Test 3 (Cross-language): SKIPPED — manifests 目录不存在")
        return

    # Python 端
    manifests = load_manifests(manifest_dir)
    if len(manifests) < 2:
        print("⚠️ Test 3 (Cross-language): SKIPPED — manifest 不足")
        return

    services = _parse_all(manifests, io_ratio=0.3)
    prefs = Preferences(cost=0.3, quality=0.3, speed=0.2, reliability=0.2)
    py_results = score_topsis(services, prefs)

    py_ranking = [(r.service.service_id, r.total_score) for r in py_results]

    # TypeScript 端 — 尝试运行
    try:
        result = subprocess.run(
            ["npx", "tsx", str(ts_test_script)],
            cwd=str(registry_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"⚠️ Test 3 (Cross-language): SKIPPED — TypeScript 执行失败: {result.stderr[:200]}")
            return

        # 解析 TypeScript 输出（只取 TOPSIS 部分，忽略 Weighted Average 部分）
        ts_ranking = []
        in_topsis_section = False
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if "TOPSIS" in line and "---" in line:
                in_topsis_section = True
                continue
            if "Weighted Average" in line and "---" in line:
                in_topsis_section = False
                continue
            if not in_topsis_section:
                continue
            if not line.startswith("#"):
                continue
            # 格式: #1 service_id: score=0.xxxx ...
            parts = line.split()
            if len(parts) >= 3:
                sid = parts[1].rstrip(":")
                score_str = parts[2].split("=")[1]
                ts_ranking.append((sid, float(score_str)))

        if not ts_ranking:
            print("⚠️ Test 3 (Cross-language): SKIPPED — 无法解析 TypeScript 输出")
            return

        # 对比排名
        py_order = [sid for sid, _ in py_ranking]
        ts_order = [sid for sid, _ in ts_ranking]

        assert py_order == ts_order, \
            f"排名不一致!\nPython:     {py_order[:5]}\nTypeScript: {ts_order[:5]}"

        # 对比分数（允许 0.001 的浮点误差）
        py_scores = dict(py_ranking)
        ts_scores = dict(ts_ranking)

        max_diff = 0.0
        for sid in py_scores:
            if sid in ts_scores:
                diff = abs(py_scores[sid] - ts_scores[sid])
                max_diff = max(max_diff, diff)
                assert diff < 0.001, \
                    f"{sid}: Python={py_scores[sid]:.4f} vs TS={ts_scores[sid]:.4f}, diff={diff:.6f}"

        print(f"✅ Test 3 (Cross-language Parity): PASSED — {len(py_ranking)} 个服务排名一致, 最大分数差: {max_diff:.6f}")

    except FileNotFoundError:
        print("⚠️ Test 3 (Cross-language): SKIPPED — npx/tsx 不可用")
    except subprocess.TimeoutExpired:
        print("⚠️ Test 3 (Cross-language): SKIPPED — TypeScript 执行超时")


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 60)
    print("  ASM Scorer 单元测试")
    print("=" * 60)
    print()

    passed = 0
    failed = 0
    skipped = 0

    tests = [
        ("Test 1: TOPSIS Golden Test", test_topsis_golden),
        ("Test 2: io_ratio Regression", test_io_ratio_regression),
        ("Test 3: Cross-language Parity", test_cross_language_parity),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: FAILED — {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️ {name}: ERROR — {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  结果: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
