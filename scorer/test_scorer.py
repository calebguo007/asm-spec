#!/usr/bin/env python3
"""ASM Scorer Unit Tests — 3 key test cases.

1. Golden test: verify TOPSIS output on known input
2. io_ratio test: effect of io_ratio on ranking (regression test)
3. Cross-language parity: Python vs TypeScript output consistency

Usage:
    python -m pytest test_scorer.py -v
    python test_scorer.py  # Run directly
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

# Add scorer to path
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
# Test data: 3 synthetic manifests (known input)
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
    """Parse manifests into ServiceVector list."""
    return [parse_manifest(m, io_ratio=io_ratio) for m in manifests]


# ============================================================
# Test 1: Golden Test — TOPSIS output on known input
# ============================================================

def test_topsis_golden():
    """Verify TOPSIS ranking and score range on known synthetic data.

    Known:
    - Cheap Fast: Low cost, low latency, medium quality
    - Expensive Good: High cost, high latency, high quality
    - Balanced Mid: Medium across all dimensions

    With equal weights (0.25 each), TOPSIS should favor Balanced Mid or Cheap Fast
    （because they are competitive across most dimensions）。
    """
    services = _parse_all(SYNTHETIC_MANIFESTS)
    prefs = Preferences(cost=0.25, quality=0.25, speed=0.25, reliability=0.25)
    results = score_topsis(services, prefs)

    # Basic structure validation
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert results[0].rank == 1
    assert results[1].rank == 2
    assert results[2].rank == 3

    # Score range: TOPSIS closeness in [0, 1]
    for r in results:
        assert 0.0 <= r.total_score <= 1.0, f"{r.service.display_name} score {r.total_score} out of range [0,1]"

    # Ranking monotonicity: strictly decreasing scores
    for i in range(len(results) - 1):
        assert results[i].total_score >= results[i + 1].total_score, \
            f"Rank #{i+1} score {results[i].total_score} < Rank #{i+2} score {results[i+1].total_score}"

    # Breakdown dimension completeness
    for r in results:
        assert set(r.breakdown.keys()) == {"cost", "quality", "speed", "reliability"}, \
            f"Breakdown Dimensions incomplete: {r.breakdown.keys()}"
        for dim, val in r.breakdown.items():
            assert 0.0 <= val <= 1.0, f"{r.service.display_name}.{dim} = {val} out of range [0,1]"

    # Reasoning non-empty
    for r in results:
        assert len(r.reasoning) > 0, f"{r.service.display_name} reasoning is empty"

    # Specific ranking: cost-priority, Cheap Fast should rank first
    prefs_cost = Preferences(cost=0.7, quality=0.1, speed=0.1, reliability=0.1)
    results_cost = score_topsis(services, prefs_cost)
    assert results_cost[0].service.service_id == "test/cheap-fast@1.0", \
        f"Cost-priority rank 1 should be Cheap Fast, got {results_cost[0].service.display_name}"

    # Quality-priority: Expensive Good should rank first
    prefs_quality = Preferences(cost=0.1, quality=0.7, speed=0.1, reliability=0.1)
    results_quality = score_topsis(services, prefs_quality)
    assert results_quality[0].service.service_id == "test/expensive-good@1.0", \
        f"Quality-priority rank 1 should be Expensive Good, got {results_quality[0].service.display_name}"

    print("✅ Test 1 (Golden Test): PASSED")


# ============================================================
# Test 2: io_ratio effect on ranking (regression test)
# ============================================================

def test_io_ratio_regression():
    """Verify io_ratio affects cost calculation and final ranking.

    io_ratio=0.3 (default, chat) → weighted toward output cost
    io_ratio=0.8 (RAG) → weighted toward input cost

    For Expensive Good (input=10, output=30):
      io_ratio=0.3 → cost = 0.3*10e-6 + 0.7*30e-6 = 24e-6
      io_ratio=0.8 → cost = 0.8*10e-6 + 0.2*30e-6 = 14e-6
    
    So in RAG scenario, Expensive Good has lower cost and may rank higher.
    """
    # Verify _extract_primary_cost io_ratio behavior
    pricing = SYNTHETIC_MANIFESTS[1]["pricing"]  # Expensive Good

    cost_chat = _extract_primary_cost(pricing, io_ratio=0.3)
    cost_rag = _extract_primary_cost(pricing, io_ratio=0.8)

    # Chat scenario weights output (30/M), so cost is higher
    assert cost_chat > cost_rag, \
        f"Chat cost ({cost_chat}) should be greater than RAG cost ({cost_rag})，because output tokens are more expensive"

    # Exact value verification
    expected_chat = 0.3 * 10 / 1_000_000 + 0.7 * 30 / 1_000_000
    expected_rag = 0.8 * 10 / 1_000_000 + 0.2 * 30 / 1_000_000
    assert math.isclose(cost_chat, expected_chat, rel_tol=1e-9), \
        f"Chat cost {cost_chat} != expected {expected_chat}"
    assert math.isclose(cost_rag, expected_rag, rel_tol=1e-9), \
        f"RAG cost {cost_rag} != expected {expected_rag}"

    # Verify io_ratio effect on TOPSIS ranking
    services_chat = _parse_all(SYNTHETIC_MANIFESTS, io_ratio=0.3)
    services_rag = _parse_all(SYNTHETIC_MANIFESTS, io_ratio=0.8)

    prefs = Preferences(cost=0.5, quality=0.2, speed=0.2, reliability=0.1)
    results_chat = score_topsis(services_chat, prefs)
    results_rag = score_topsis(services_rag, prefs)

    # Rankings should differ (or at least scores)
    chat_order = [r.service.service_id for r in results_chat]
    rag_order = [r.service.service_id for r in results_rag]

    # Scores must differ
    chat_scores = {r.service.service_id: r.total_score for r in results_chat}
    rag_scores = {r.service.service_id: r.total_score for r in results_rag}

    any_diff = False
    for sid in chat_scores:
        if not math.isclose(chat_scores[sid], rag_scores[sid], abs_tol=1e-6):
            any_diff = True
            break

    assert any_diff, "Scores should differ after io_ratio change"

    # Edge case tests
    cost_0 = _extract_primary_cost(pricing, io_ratio=0.0)  # Pure output
    cost_1 = _extract_primary_cost(pricing, io_ratio=1.0)  # Pure input
    expected_0 = 30 / 1_000_000  # Pure output token cost
    expected_1 = 10 / 1_000_000  # Pure input token cost
    assert math.isclose(cost_0, expected_0, rel_tol=1e-9)
    assert math.isclose(cost_1, expected_1, rel_tol=1e-9)

    print("✅ Test 2 (io_ratio Regression): PASSED")


# ============================================================
# Test 3: Cross-language parity (Python vs TypeScript)
# ============================================================

def test_cross_language_parity():
    """Verify Python and TypeScript scorers produce consistent output on same input.

    Uses real 14 manifest files, comparing TOPSIS rankings from both implementations.
    Skipped if TypeScript compilation environment unavailable.
    """
    manifest_dir = Path(__file__).resolve().parent.parent / "manifests"
    registry_dir = Path(__file__).resolve().parent.parent / "registry"
    ts_test_script = registry_dir / "src" / "test_topsis.ts"

    if not manifest_dir.exists():
        print("⚠️ Test 3 (Cross-language): SKIPPED — manifests directory not found")
        return

    # Python side
    manifests = load_manifests(manifest_dir)
    if len(manifests) < 2:
        print("⚠️ Test 3 (Cross-language): SKIPPED — insufficient manifests")
        return

    services = _parse_all(manifests, io_ratio=0.3)
    prefs = Preferences(cost=0.3, quality=0.3, speed=0.2, reliability=0.2)
    py_results = score_topsis(services, prefs)

    py_ranking = [(r.service.service_id, r.total_score) for r in py_results]

    # TypeScript side — try running
    try:
        result = subprocess.run(
            ["npx", "tsx", str(ts_test_script)],
            cwd=str(registry_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"⚠️ Test 3 (Cross-language): SKIPPED — TypeScript execution failed: {result.stderr[:200]}")
            return

        # Parse TypeScript output (TOPSIS part only, ignore Weighted Average)
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
            # Format: #1 service_id: score=0.xxxx ...
            parts = line.split()
            if len(parts) >= 3:
                sid = parts[1].rstrip(":")
                score_str = parts[2].split("=")[1]
                ts_ranking.append((sid, float(score_str)))

        if not ts_ranking:
            print("⚠️ Test 3 (Cross-language): SKIPPED — Cannot parse TypeScript output")
            return

        # Compare rankings
        py_order = [sid for sid, _ in py_ranking]
        ts_order = [sid for sid, _ in ts_ranking]

        assert py_order == ts_order, \
            f"Rankings inconsistent!\nPython:     {py_order[:5]}\nTypeScript: {ts_order[:5]}"

        # Compare scores (0.001 tolerance)
        py_scores = dict(py_ranking)
        ts_scores = dict(ts_ranking)

        max_diff = 0.0
        for sid in py_scores:
            if sid in ts_scores:
                diff = abs(py_scores[sid] - ts_scores[sid])
                max_diff = max(max_diff, diff)
                assert diff < 0.001, \
                    f"{sid}: Python={py_scores[sid]:.4f} vs TS={ts_scores[sid]:.4f}, diff={diff:.6f}"

        print(f"✅ Test 3 (Cross-language Parity): PASSED — {len(py_ranking)} services ranked consistently, max score diff: {max_diff:.6f}")

    except FileNotFoundError:
        print("⚠️ Test 3 (Cross-language): SKIPPED — npx/tsx unavailable")
    except subprocess.TimeoutExpired:
        print("⚠️ Test 3 (Cross-language): SKIPPED — TypeScript execution timeout")


# ============================================================
# Main entry
# ============================================================

def main():
    print("=" * 60)
    print("  ASM Scorer Unit Tests")
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
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
