#!/usr/bin/env python3
"""Small public CLI for trying ASM from a checkout or editable install."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scorer import Constraints, Preferences, filter_services, load_manifests, parse_manifest, score_topsis


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST_DIR = ROOT / "manifests"


TAXONOMY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("ai.audio.tts", ("tts", "text to speech", "voiceover", "voice over", "voice", "speech")),
    ("ai.audio.stt", ("stt", "speech to text", "transcription", "transcribe")),
    ("ai.llm.chat", ("llm", "chat", "model", "reasoning", "assistant")),
    ("ai.vision.image_generation", ("image", "picture", "illustration", "generate image")),
    ("ai.video.generation", ("video", "clip", "movie")),
    ("tool.data.search", ("search", "web search", "research")),
    ("tool.communication.email", ("email", "mail")),
]


def infer_taxonomy(query: str) -> str | None:
    q = query.lower()
    for taxonomy, hints in TAXONOMY_HINTS:
        if any(h in q for h in hints):
            return taxonomy
    return None


def infer_constraints(query: str, taxonomy: str | None) -> Constraints:
    q = query.lower()
    max_latency_s = None

    match = re.search(r"(?:under|below|less than|<=|<)\s*(\d+(?:\.\d+)?)\s*(ms|s|sec|second|seconds)", q)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        max_latency_s = value / 1000 if unit == "ms" else value

    min_uptime = 0.99 if any(word in q for word in ("reliable", "reliability", "uptime")) else None
    return Constraints(required_taxonomy=taxonomy, max_latency_s=max_latency_s, min_uptime=min_uptime)


def infer_preferences(query: str) -> Preferences:
    q = query.lower()
    weights = {
        "cost": 0.30,
        "quality": 0.30,
        "speed": 0.20,
        "reliability": 0.20,
    }
    if any(word in q for word in ("cheap", "cheapest", "low cost", "budget")):
        weights.update(cost=0.50, quality=0.20, speed=0.15, reliability=0.15)
    if any(word in q for word in ("best", "highest quality", "quality", "accurate")):
        weights.update(cost=0.15, quality=0.55, speed=0.15, reliability=0.15)
    if any(word in q for word in ("fast", "latency", "under", "below", "low latency")):
        weights["speed"] += 0.10
    if any(word in q for word in ("reliable", "uptime", "stable")):
        weights["reliability"] += 0.10

    total = sum(weights.values())
    normalized = {key: value / total for key, value in weights.items()}
    return Preferences(**normalized)


def rejection_reason(service, constraints: Constraints) -> str | None:
    if constraints.required_taxonomy and not service.taxonomy.startswith(constraints.required_taxonomy):
        return f"taxonomy {service.taxonomy} does not match {constraints.required_taxonomy}"
    if constraints.max_latency_s is not None and service.latency_seconds > constraints.max_latency_s:
        return f"latency {service.latency_seconds:.2f}s > max {constraints.max_latency_s:.2f}s"
    if constraints.min_uptime is not None and service.uptime < constraints.min_uptime:
        return f"uptime {service.uptime:.3f} < min {constraints.min_uptime:.3f}"
    if constraints.min_quality is not None and service.quality_score < constraints.min_quality:
        return f"quality {service.quality_score:.3f} < min {constraints.min_quality:.3f}"
    if constraints.max_cost is not None and service.cost_per_unit > constraints.max_cost:
        return f"cost {service.cost_per_unit:.8f} > max {constraints.max_cost:.8f}"
    return None


def cmd_score(args: argparse.Namespace) -> int:
    manifest_dir = Path(args.manifests)
    manifests = load_manifests(manifest_dir)
    taxonomy = args.taxonomy or infer_taxonomy(args.query)
    constraints = infer_constraints(args.query, taxonomy)
    preferences = infer_preferences(args.query)

    candidate_manifests = [
        m for m in manifests
        if not taxonomy or str(m.get("taxonomy", "")).startswith(taxonomy)
    ]
    if not candidate_manifests:
        print(f"No candidate manifests found for taxonomy={taxonomy or 'any'} in {manifest_dir}")
        return 1

    services = [parse_manifest(m, io_ratio=preferences.io_ratio) for m in candidate_manifests]
    selected = filter_services(services, constraints)
    ranked = score_topsis(selected, preferences)

    print(f"Query: {args.query}")
    print(f"Taxonomy: {taxonomy or 'any'}")
    print(
        "Preferences: "
        f"cost={preferences.cost:.2f}, quality={preferences.quality:.2f}, "
        f"speed={preferences.speed:.2f}, reliability={preferences.reliability:.2f}"
    )
    if constraints.max_latency_s is not None or constraints.min_uptime is not None:
        parts = []
        if constraints.max_latency_s is not None:
            parts.append(f"latency <= {constraints.max_latency_s:.2f}s")
        if constraints.min_uptime is not None:
            parts.append(f"uptime >= {constraints.min_uptime:.3f}")
        print(f"Hard constraints: {', '.join(parts)}")

    if not ranked:
        print("\nNo service satisfies the hard constraints.")
    else:
        winner = ranked[0]
        print(f"\nSelected: {winner.service.display_name}")
        print(f"Reason: {winner.reasoning}")
        print("\nRanked services:")
        for item in ranked[: args.limit]:
            print(
                f"{item.rank}. {item.service.display_name} "
                f"(score={item.total_score:.4f}, cost=${item.service.cost_per_unit:.8f}/unit, "
                f"quality={item.service.quality_score:.3f}, latency={item.service.latency_seconds:.2f}s, "
                f"uptime={item.service.uptime:.3f})"
            )

    rejected = []
    for service in services:
        reason = rejection_reason(service, constraints)
        if reason:
            rejected.append((service.display_name, reason))

    if rejected:
        print("\nRejected by hard constraints:")
        for name, reason in rejected[: args.limit]:
            print(f"- {name}: {reason}")
    else:
        print("\nRejected by hard constraints: none")

    return 0 if ranked else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asm", description="Agent Service Manifest CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="Rank services for a natural-language service request")
    score.add_argument("query", help='Example: "cheap reliable TTS under 1s"')
    score.add_argument("--taxonomy", help="Override inferred taxonomy, e.g. ai.audio.tts")
    score.add_argument("--manifests", default=str(DEFAULT_MANIFEST_DIR), help="Directory of .asm.json manifests")
    score.add_argument("--limit", type=int, default=5, help="Maximum ranked/rejected rows to print")
    score.set_defaults(func=cmd_score)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
