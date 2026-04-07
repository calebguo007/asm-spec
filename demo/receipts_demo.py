#!/usr/bin/env python3
"""
ASM Signed Receipts Integration Demo
=====================================

Demonstrates the trust delta pipeline:
  1. Service declares quality in ASM manifest (pre-selection)
  2. Agent selects service using ASM scorer
  3. Service executes and produces a signed receipt (simulated)
  4. Agent computes trust delta: |declared - actual| / declared
  5. Trust scores update with exponential decay
  6. Future selections incorporate trust data

This demo simulates the complete ASM ↔ Signed Receipts trust chain
without requiring an actual receipt server.

No external dependencies required (pure Python + ASM scorer).
"""

import sys
import os
import time
import json
import math
import random

# Add scorer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scorer"))

from scorer import (
    load_manifests,
    select_service,
    parse_manifest,
    Constraints,
    Preferences,
    ScoredService,
    ReceiptRecord,
    TrustScore,
    compute_trust_delta,
    exponential_decay_weight,
    compute_trust_score,
    adjust_scores_with_trust,
)

# ── ANSI colors ─────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")


def step(num: int, text: str):
    print(f"\n{BOLD}{YELLOW}  Step {num}: {text}{RESET}")


def result_line(text: str, indent: int = 4):
    print(f"{' ' * indent}{GREEN}→{RESET} {text}")


def warn_line(text: str, indent: int = 4):
    print(f"{' ' * indent}{RED}⚠{RESET} {text}")


def dim_line(text: str, indent: int = 4):
    print(f"{' ' * indent}{DIM}{text}{RESET}")


# ── Simulated Receipt Generation ────────────────────────

def simulate_execution(
    service_id: str,
    declared_latency: float,
    declared_quality: float,
    declared_uptime: float,
    declared_cost: float,
    honesty_factor: float = 1.0,
    noise: float = 0.1,
) -> ReceiptRecord:
    """Simulate a service execution and generate a receipt.

    Args:
        honesty_factor: 1.0 = perfectly honest, >1.0 = overstates quality,
                        <1.0 = understates (conservative)
        noise: Random noise factor (0-1)
    """
    # Honest services deliver close to declared values
    # Dishonest services have systematic deviation
    actual_latency = declared_latency * honesty_factor * (1 + random.gauss(0, noise))
    actual_quality = declared_quality / honesty_factor * (1 + random.gauss(0, noise * 0.5))
    actual_uptime = min(1.0, declared_uptime / honesty_factor * (1 + random.gauss(0, noise * 0.2)))
    actual_cost = declared_cost * (1 + random.gauss(0, noise * 0.3))

    # Clamp values
    actual_latency = max(0.01, actual_latency)
    actual_quality = max(0.0, min(1.0, actual_quality))
    actual_uptime = max(0.0, min(1.0, actual_uptime))
    actual_cost = max(0.0, actual_cost)

    return ReceiptRecord(
        service_id=service_id,
        timestamp=time.time() - random.uniform(0, 14 * 24 * 3600),  # Random time in last 2 weeks
        actual_latency_seconds=actual_latency,
        actual_quality_score=actual_quality,
        actual_uptime=actual_uptime,
        actual_cost_per_unit=actual_cost,
    )


def format_receipt_json(receipt: ReceiptRecord, declared: dict) -> str:
    """Format a receipt as a JSON-like display (simulating IETF ACTA format)."""
    return json.dumps({
        "@context": "https://www.w3.org/2018/credentials/v1",
        "type": ["VerifiableCredential", "ServiceExecutionReceipt"],
        "issuer": receipt.service_id,
        "issuanceDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(receipt.timestamp)),
        "credentialSubject": {
            "asm:service_id": receipt.service_id,
            "asm:declared": declared,
            "asm:actual": {
                "latency_seconds": round(receipt.actual_latency_seconds, 4),
                "quality_score": round(receipt.actual_quality_score, 4),
                "uptime": round(receipt.actual_uptime, 4),
                "cost_per_unit": round(receipt.actual_cost_per_unit, 6),
            },
            "asm:trust_delta": {
                "latency": round(compute_trust_delta(
                    declared["latency_seconds"], receipt.actual_latency_seconds), 4),
                "quality": round(compute_trust_delta(
                    declared["quality_score"], receipt.actual_quality_score), 4),
            }
        },
        "proof": {
            "type": "Ed25519Signature2020",
            "verificationMethod": "did:web:provider.example#key-1",
            "proofValue": "z..." + "".join(random.choices("abcdef0123456789", k=32))
        }
    }, indent=2)


# ── Demo Scenarios ──────────────────────────────────────

def demo_trust_delta_basics():
    """Demonstrate basic trust delta computation."""
    header("Part 1: Trust Delta Basics")

    step(1, "Trust Delta Formula")
    result_line("trust_delta(declared, actual) = |declared - actual| / declared")
    result_line("0.0 = perfect match, 1.0 = 100% deviation")
    print()

    examples = [
        ("Latency: declared 200ms, actual 200ms", 0.200, 0.200),
        ("Latency: declared 200ms, actual 300ms", 0.200, 0.300),
        ("Latency: declared 200ms, actual 450ms", 0.200, 0.450),
        ("Quality: declared 0.90, actual 0.90", 0.90, 0.90),
        ("Quality: declared 0.90, actual 0.72", 0.90, 0.72),
        ("Cost: declared $0.003, actual $0.003", 0.003, 0.003),
        ("Cost: declared $0.003, actual $0.005", 0.003, 0.005),
    ]

    for desc, declared, actual in examples:
        delta = compute_trust_delta(declared, actual)
        color = GREEN if delta < 0.1 else (YELLOW if delta < 0.5 else RED)
        result_line(f"{desc} → delta = {color}{delta:.3f}{RESET}")


def demo_exponential_decay():
    """Demonstrate exponential decay weighting."""
    header("Part 2: Exponential Decay Weighting")

    step(2, "Recent receipts matter more")
    result_line("w(t) = exp(-ln(2) × age / half_life)")
    result_line("Half-life = 1 week (default)")
    print()

    now = time.time()
    ages = [
        ("Just now", 0),
        ("1 day ago", 1 * 24 * 3600),
        ("3 days ago", 3 * 24 * 3600),
        ("1 week ago", 7 * 24 * 3600),
        ("2 weeks ago", 14 * 24 * 3600),
        ("1 month ago", 30 * 24 * 3600),
    ]

    for desc, age_seconds in ages:
        ts = now - age_seconds
        weight = exponential_decay_weight(ts, now)
        bar_len = int(weight * 30)
        bar = f"{'█' * bar_len}{'░' * (30 - bar_len)}"
        result_line(f"{desc:15s} [{bar}] weight = {weight:.4f}")


def demo_trust_pipeline(manifests: list[dict]):
    """Full trust pipeline: select → execute → receipt → trust update → re-rank."""
    header("Part 3: Full Trust Pipeline — Honest vs Dishonest Services")

    # Use LLM services for this demo
    llm_manifests = [m for m in manifests if m["taxonomy"] == "ai.llm.chat"]
    if len(llm_manifests) < 2:
        warn_line("Need at least 2 LLM services for this demo")
        return

    step(3, "Initial Selection (no trust data)")
    prefs = Preferences(cost=0.40, quality=0.35, speed=0.15, reliability=0.10)
    initial_results = select_service(llm_manifests, preferences=prefs, method="topsis")

    for r in initial_results:
        marker = f" ⭐ {GREEN}SELECTED{RESET}" if r.rank == 1 else ""
        result_line(f"#{r.rank} {BOLD}{r.service.display_name:25s}{RESET} "
                   f"score={r.total_score:.4f}{marker}")

    step(4, "Simulate 20 Executions with Signed Receipts")

    # Parse services for trust computation
    services = {m["service_id"]: parse_manifest(m) for m in llm_manifests}

    # Define honesty profiles
    # Service 1 (first in list): honest — delivers what it promises
    # Service 2 (second): dishonest — overstates quality, understates latency
    service_ids = list(services.keys())
    honesty_profiles = {}
    for i, sid in enumerate(service_ids):
        if i == 0:
            honesty_profiles[sid] = {"honesty_factor": 1.0, "label": "honest"}
        elif i == 1:
            honesty_profiles[sid] = {"honesty_factor": 1.8, "label": "dishonest (overstates)"}
        else:
            honesty_profiles[sid] = {"honesty_factor": 1.2, "label": "slightly inflated"}

    # Generate receipts
    all_receipts: dict[str, list[ReceiptRecord]] = {sid: [] for sid in service_ids}
    now = time.time()

    for sid, svc in services.items():
        profile = honesty_profiles[sid]
        for _ in range(20):
            receipt = simulate_execution(
                service_id=sid,
                declared_latency=svc.latency_seconds,
                declared_quality=svc.quality_score,
                declared_uptime=svc.uptime,
                declared_cost=svc.cost_per_unit,
                honesty_factor=profile["honesty_factor"],
                noise=0.08,
            )
            all_receipts[sid].append(receipt)

        label = profile["label"]
        result_line(f"{svc.display_name}: 20 receipts generated ({label})")

    step(5, "Show Sample Receipt (IETF ACTA format)")
    sample_sid = service_ids[0]
    sample_svc = services[sample_sid]
    sample_receipt = all_receipts[sample_sid][0]
    declared_dict = {
        "latency_seconds": round(sample_svc.latency_seconds, 4),
        "quality_score": round(sample_svc.quality_score, 4),
        "uptime": round(sample_svc.uptime, 4),
        "cost_per_unit": round(sample_svc.cost_per_unit, 6),
    }
    print(f"\n{DIM}{format_receipt_json(sample_receipt, declared_dict)}{RESET}")

    step(6, "Compute Trust Scores")
    trust_scores: dict[str, TrustScore] = {}
    for sid, svc in services.items():
        ts = compute_trust_score(svc, all_receipts[sid], now=now)
        trust_scores[sid] = ts

        color = GREEN if ts.trust_score >= 0.8 else (YELLOW if ts.trust_score >= 0.5 else RED)
        result_line(f"{svc.display_name:25s} trust={color}{ts.trust_score:.3f}{RESET} "
                   f"confidence={ts.confidence:.2f}")
        for dim, delta in ts.delta_breakdown.items():
            delta_color = GREEN if delta < 0.1 else (YELLOW if delta < 0.3 else RED)
            dim_line(f"  {dim:12s} delta={delta_color}{delta:.4f}{RESET}", indent=8)

    step(7, "Re-rank with Trust Adjustment")
    result_line("Final score = 0.8 × TOPSIS score + 0.2 × trust × confidence")
    print()

    adjusted = adjust_scores_with_trust(initial_results, trust_scores, trust_weight=0.2)

    for r in adjusted:
        marker = f" ⭐ {GREEN}SELECTED{RESET}" if r.rank == 1 else ""
        trust_info = ""
        if "trust" in r.breakdown:
            trust_info = f" trust_adj={MAGENTA}{r.breakdown['trust']:.3f}{RESET}"
        result_line(f"#{r.rank} {BOLD}{r.service.display_name:25s}{RESET} "
                   f"score={r.total_score:.4f}{trust_info}{marker}")

    # Compare initial vs adjusted
    step(8, "Impact Analysis")
    initial_best = initial_results[0].service.display_name
    adjusted_best = adjusted[0].service.display_name
    if initial_best != adjusted_best:
        warn_line(f"Ranking changed! Initial best: {initial_best} → Trust-adjusted best: {adjusted_best}")
        result_line("Trust data revealed that the initially top-ranked service overstates its quality.")
        result_line("The honest service is now correctly ranked higher.")
    else:
        result_line(f"Best service unchanged: {adjusted_best}")
        result_line("The top-ranked service is also the most trustworthy.")


def demo_v03_manifest():
    """Show what a v0.3 manifest looks like with receipt fields."""
    header("Part 4: ASM v0.3 Manifest — New Fields")

    step(9, "New v0.3 fields for Signed Receipts integration")

    v03_example = {
        "asm_version": "0.3",
        "service_id": "anthropic/claude-sonnet-4@4.0",
        "taxonomy": "ai.llm.chat",
        "display_name": "Claude Sonnet 4",
        "updated_at": "2026-04-07T10:00:00Z",
        "ttl": 3600,
        "receipt_endpoint": "https://api.anthropic.com/v1/receipts",
        "verification": {
            "protocol": "signed-receipts-acta",
            "public_key_url": "https://api.anthropic.com/.well-known/jwks.json",
            "receipt_schema_version": "1.0"
        },
        "pricing": {"billing_dimensions": [{"dimension": "input_token", "unit": "per_1M", "cost_per_unit": 3.00, "currency": "USD"}]},
        "quality": {"metrics": [{"name": "LMSYS_Elo", "score": 1290, "scale": "Elo", "self_reported": False}]},
        "sla": {"latency_p50": "800ms", "uptime": 0.999}
    }

    result_line(f"{BOLD}updated_at{RESET}: ISO 8601 timestamp — agents know when data was last refreshed")
    result_line(f"{BOLD}ttl{RESET}: Cache duration in seconds — agents know when to re-fetch")
    result_line(f"{BOLD}receipt_endpoint{RESET}: URL to obtain signed receipts after execution")
    result_line(f"{BOLD}verification.protocol{RESET}: Which verification standard is used")
    result_line(f"{BOLD}verification.public_key_url{RESET}: Where to fetch the signing key")
    print(f"\n{DIM}{json.dumps(v03_example, indent=2)}{RESET}")


# ── Main ────────────────────────────────────────────────

def main():
    # Set random seed for reproducibility
    random.seed(42)

    manifest_dir = os.path.join(os.path.dirname(__file__), "..", "manifests")
    manifests = load_manifests(manifest_dir)

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  ASM Signed Receipts Integration Demo{RESET}")
    print(f"{BOLD}  Trust = |declared - actual| / declared{RESET}")
    print(f"{BOLD}  \"ASM declares. Receipts verify. Trust updates.\"{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"\n  Loaded {BOLD}{len(manifests)}{RESET} service manifests")

    # Run all parts
    demo_trust_delta_basics()
    demo_exponential_decay()
    demo_trust_pipeline(manifests)
    demo_v03_manifest()

    # Final summary
    header("Demo Complete")
    print(f"""
  {BOLD}What you just saw:{RESET}
  1. Trust delta formula: |declared - actual| / declared
  2. Exponential decay: recent receipts weighted more heavily
  3. Full pipeline: select → execute → receipt → trust score → re-rank
  4. Dishonest services get penalized, honest services get rewarded
  5. ASM v0.3 manifest fields for Signed Receipts integration

  {BOLD}The ASM + Signed Receipts trust chain:{RESET}
  {CYAN}ASM manifest{RESET} (pre-selection) → {CYAN}Service execution{RESET} → {CYAN}Signed Receipt{RESET} (post-execution)
  → {CYAN}Trust delta{RESET} (|declared - actual|) → {CYAN}Trust score update{RESET} (exponential decay)
  → {CYAN}Better future selections{RESET}

  {DIM}Learn more: https://github.com/asm-protocol/asm-spec{RESET}
""")


if __name__ == "__main__":
    main()
