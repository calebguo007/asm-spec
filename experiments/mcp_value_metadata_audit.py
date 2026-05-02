#!/usr/bin/env python3
"""Audit MCP registries/directories/corpora for service-value metadata.

This expands the original GitHub-repository audit beyond ad hoc repo search.
It samples external MCP discovery surfaces and asks a narrower question:

  Do MCP ecosystem entries expose machine-actionable value metadata that an
  agent can use before invoking a service?

Sources:
  - Official MCP Registry API
  - Glama MCP Registry API
  - MCP Atlas browse page
  - FindMCP homepage/search metadata
  - MCPCorpus server dataset on Hugging Face

Outputs:
  experiments/results/mcp_value_metadata_audit.csv
  experiments/results/mcp_value_metadata_audit.json
  experiments/results/mcp_value_metadata_audit.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


OFFICIAL_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
GLAMA_URL = "https://glama.ai/api/mcp/v1/servers"
MCP_ATLAS_URL = "https://mcpatlas.dev/browse"
FINDMCP_URL = "https://findmcp.dev/"
MCPCORPUS_URL = (
    "https://huggingface.co/datasets/Snak1nya/MCPCorpus/resolve/main/"
    "Website/mcpso_servers_cleaned.json"
)


VALUE_CLASSES = [
    "pricing",
    "sla_rate_limit",
    "quality_benchmark",
    "payment",
    "provenance",
    "security_trust",
]


PATTERNS = {
    "pricing": re.compile(
        r"\b(pricing|price|cost|billing|billable|paid|free tier|quota|credit|"
        r"subscription|plan|usage|metered|\$|usd|eur|per request|per call|per token|"
        r"per month|per seat)\b",
        re.I,
    ),
    "sla_rate_limit": re.compile(
        r"\b(sla|uptime|availability|latency|p50|p95|p99|throughput|rate limit|"
        r"ratelimit|throttle|qps|rps|requests per|retry|timeout|region)\b",
        re.I,
    ),
    "quality_benchmark": re.compile(
        r"\b(quality|benchmark|eval|evaluation|score|rating|rank|leaderboard|"
        r"accuracy|precision|recall|f1|pass rate|test result|verified|curated)\b",
        re.I,
    ),
    "payment": re.compile(
        r"\b(payment|checkout|stripe|invoice|billing account|payment method|"
        r"merchant|purchase|marketplace|subscribe|subscription|api key provisioning|"
        r"ap2|mandate)\b",
        re.I,
    ),
    "provenance": re.compile(
        r"\b(source|repository|github|package|npm|pypi|docker|version|license|"
        r"author|publisher|owner|last updated|updated at|last commit|commit|"
        r"created|published|verified publisher)\b",
        re.I,
    ),
    "security_trust": re.compile(
        r"\b(security|auth|oauth|api key|permission|scope|sandbox|secret|token|"
        r"credential|signed|signature|verified|vulnerability|scan|risk|trust|"
        r"read-only|destructive|license|archived)\b",
        re.I,
    ),
}


STRUCTURED_KEYS = {
    "pricing": {"pricing", "price", "cost", "billing", "plans", "quota", "credits"},
    "sla_rate_limit": {"sla", "latency", "uptime", "rate_limit", "rateLimit", "timeout", "qps"},
    "quality_benchmark": {"quality", "benchmark", "score", "rating", "rank", "leaderboard", "evaluation"},
    "payment": {"payment", "checkout", "billing", "subscription", "marketplace"},
    "provenance": {
        "url",
        "repository",
        "github",
        "version",
        "license",
        "author_name",
        "publisher",
        "publishedAt",
        "updatedAt",
        "last_commit",
    },
    "security_trust": {
        "security",
        "auth",
        "oauth",
        "api_key",
        "apiKey",
        "environmentVariablesJsonSchema",
        "license",
        "archived",
    },
}


@dataclass
class AuditRow:
    source: str
    source_url: str
    entry_id: str
    name: str
    title: str
    description: str
    repository_url: str
    category: str
    pricing: str
    sla_rate_limit: str
    quality_benchmark: str
    payment: str
    provenance: str
    security_trust: str
    all_core_value_classes: bool
    structured_value_classes: int
    machine_actionable_value_classes: int
    evidence: str


def fetch_json(url: str, *, timeout: int = 60) -> Any:
    req = Request(url, headers={"User-Agent": "asm-value-metadata-audit/0.1"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_text(url: str, *, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": "asm-value-metadata-audit/0.1"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def stable_id(source: str, value: str) -> str:
    digest = hashlib.sha1(f"{source}:{value}".encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return html.unescape(value)
    try:
        return html.unescape(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except TypeError:
        return str(value)


def collect_keys(value: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_str = str(key)
            keys.add(key_str)
            keys.add(f"{prefix}.{key_str}" if prefix else key_str)
            keys.update(collect_keys(child, f"{prefix}.{key_str}" if prefix else key_str))
    elif isinstance(value, list):
        for child in value:
            keys.update(collect_keys(child, prefix))
    return keys


def structured_hit(value_class: str, keys: set[str]) -> bool:
    wanted = STRUCTURED_KEYS[value_class]
    normalized = {key.lower().replace("-", "_") for key in keys}
    for wanted_key in wanted:
        wk = wanted_key.lower().replace("-", "_")
        if wk in normalized:
            return True
        if any(key.endswith("." + wk) for key in normalized):
            return True
    return False


def classify(value_class: str, text: str, keys: set[str]) -> str:
    has_text = bool(PATTERNS[value_class].search(text))
    has_structured = structured_hit(value_class, keys)
    if has_structured and has_text:
        if value_class in {"provenance", "security_trust"}:
            return "machine_actionable"
        return "structured_unverified"
    if has_structured:
        return "structured_unverified"
    if has_text:
        return "human_readable"
    return "absent"


def evidence_for(text: str) -> str:
    flat = re.sub(r"\s+", " ", text)
    snippets = []
    for value_class, pattern in PATTERNS.items():
        match = pattern.search(flat)
        if not match:
            continue
        start = max(match.start() - 55, 0)
        end = min(match.end() + 80, len(flat))
        snippets.append(f"{value_class}: ...{flat[start:end]}...")
    return " | ".join(snippets)[:900]


def row_from_payload(
    *,
    source: str,
    source_url: str,
    payload: dict[str, Any],
    entry_id: str,
    name: str,
    title: str = "",
    description: str = "",
    repository_url: str = "",
    category: str = "",
) -> AuditRow:
    text = flatten_text(payload)
    keys = collect_keys(payload)
    labels = {value_class: classify(value_class, text, keys) for value_class in VALUE_CLASSES}
    structured_count = sum(1 for label in labels.values() if label in {"structured_unverified", "structured_verified", "machine_actionable"})
    machine_count = sum(1 for label in labels.values() if label == "machine_actionable")
    return AuditRow(
        source=source,
        source_url=source_url,
        entry_id=entry_id,
        name=name,
        title=title,
        description=re.sub(r"\s+", " ", description)[:320],
        repository_url=repository_url,
        category=category,
        pricing=labels["pricing"],
        sla_rate_limit=labels["sla_rate_limit"],
        quality_benchmark=labels["quality_benchmark"],
        payment=labels["payment"],
        provenance=labels["provenance"],
        security_trust=labels["security_trust"],
        all_core_value_classes=all(labels[field] != "absent" for field in ["pricing", "sla_rate_limit", "quality_benchmark", "payment"]),
        structured_value_classes=structured_count,
        machine_actionable_value_classes=machine_count,
        evidence=evidence_for(text),
    )


def fetch_official_registry(limit: int) -> list[AuditRow]:
    rows: list[AuditRow] = []
    cursor = None
    while len(rows) < limit:
        url = f"{OFFICIAL_REGISTRY_URL}?limit={min(100, limit - len(rows))}"
        if cursor:
            url += f"&cursor={quote(cursor)}"
        data = fetch_json(url)
        servers = data.get("servers") or []
        if not servers:
            break
        for wrapper in servers:
            server = wrapper.get("server") or {}
            meta = wrapper.get("_meta") or {}
            payload = {"server": server, "_meta": meta}
            repo = ""
            packages = server.get("packages") or []
            for package in packages:
                if isinstance(package, dict) and "registry_base_url" in package:
                    repo = str(package.get("registry_base_url") or "")
                    break
            rows.append(
                row_from_payload(
                    source="official_mcp_registry",
                    source_url=OFFICIAL_REGISTRY_URL,
                    payload=payload,
                    entry_id=str(server.get("name") or stable_id("official", flatten_text(payload))),
                    name=str(server.get("name") or ""),
                    title=str(server.get("title") or ""),
                    description=str(server.get("description") or ""),
                    repository_url=repo,
                    category="",
                )
            )
            if len(rows) >= limit:
                break
        cursor = (data.get("metadata") or {}).get("nextCursor")
        if not cursor:
            break
        time.sleep(0.15)
    return rows


def fetch_glama(limit: int) -> list[AuditRow]:
    rows: list[AuditRow] = []
    cursor = None
    while len(rows) < limit:
        url = f"{GLAMA_URL}?limit={min(100, limit - len(rows))}"
        if cursor:
            url += f"&after={quote(cursor)}"
        data = fetch_json(url)
        servers = data.get("servers") or []
        if not servers:
            break
        for server in servers:
            repo_obj = server.get("repository") or {}
            rows.append(
                row_from_payload(
                    source="glama",
                    source_url=GLAMA_URL,
                    payload=server,
                    entry_id=str(server.get("id") or stable_id("glama", flatten_text(server))),
                    name=str(server.get("name") or ""),
                    title=str(server.get("name") or ""),
                    description=str(server.get("description") or ""),
                    repository_url=str(repo_obj.get("url") or ""),
                    category=",".join(server.get("attributes") or []),
                )
            )
            if len(rows) >= limit:
                break
        page_info = data.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break
        time.sleep(0.15)
    return rows


def fetch_mcpatlas(limit: int) -> list[AuditRow]:
    try:
        page = fetch_text(MCP_ATLAS_URL)
    except (HTTPError, URLError, TimeoutError, OSError):
        return []

    urls = []
    for match in re.finditer(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", page):
        url = match.group(0).rstrip(".,)")
        if url not in urls:
            urls.append(url)

    rows: list[AuditRow] = []
    for url in urls[:limit]:
        start = max(page.find(url) - 900, 0)
        end = min(page.find(url) + 1200, len(page))
        snippet = re.sub(r"<[^>]+>", " ", page[start:end])
        snippet = html.unescape(re.sub(r"\s+", " ", snippet))
        payload = {"repository": {"url": url}, "page_snippet": snippet, "source_page": MCP_ATLAS_URL}
        name = url.removeprefix("https://github.com/")
        rows.append(
            row_from_payload(
                source="mcp_atlas",
                source_url=MCP_ATLAS_URL,
                payload=payload,
                entry_id=stable_id("mcp_atlas", url),
                name=name,
                title=name,
                description=snippet[:300],
                repository_url=url,
                category="curated_registry",
            )
        )
    return rows


def fetch_findmcp(limit: int) -> list[AuditRow]:
    # FindMCP currently exposes a directory homepage and sitemap, but no stable
    # public JSON listing endpoint. We still record the surface-level metadata
    # so the audit documents the source and its discoverability limits.
    rows: list[AuditRow] = []
    try:
        page = fetch_text(FINDMCP_URL)
    except (HTTPError, URLError, TimeoutError, OSError):
        return rows
    payload = {"homepage": page[:50_000], "source_page": FINDMCP_URL}
    rows.append(
        row_from_payload(
            source="findmcp",
            source_url=FINDMCP_URL,
            payload=payload,
            entry_id=stable_id("findmcp", FINDMCP_URL),
            name="FindMCP directory homepage",
            title="FindMCP",
            description="Directory homepage metadata only; no stable public listing endpoint found during audit.",
            repository_url="",
            category="directory_homepage",
        )
    )
    return rows[:limit]


def fetch_mcpcorpus(limit: int, seed: int) -> list[AuditRow]:
    data = fetch_json(MCPCORPUS_URL, timeout=120)
    rng = random.Random(seed)
    if len(data) > limit:
        sample = rng.sample(data, limit)
    else:
        sample = list(data)
    rows = []
    for item in sample:
        github = item.get("github") or {}
        rows.append(
            row_from_payload(
                source="mcpcorpus",
                source_url=MCPCORPUS_URL,
                payload=item,
                entry_id=str(item.get("id") or stable_id("mcpcorpus", flatten_text(item))),
                name=str(item.get("name") or ""),
                title=str(item.get("title") or ""),
                description=str(item.get("description") or ""),
                repository_url=str(item.get("url") or github.get("html_url") or ""),
                category=str(item.get("category") or ""),
            )
        )
    return rows


def summarize(rows: list[AuditRow], generated_at: str, source_targets: dict[str, int]) -> dict[str, Any]:
    by_source: dict[str, dict[str, Any]] = {}
    for source in sorted({row.source for row in rows}):
        source_rows = [row for row in rows if row.source == source]
        by_source[source] = source_summary(source_rows)

    return {
        "generated_at": generated_at,
        "sample_size": len(rows),
        "source_targets": source_targets,
        "sources": by_source,
        "overall": source_summary(rows),
        "method": {
            "labels": ["absent", "human_readable", "structured_unverified", "structured_verified", "machine_actionable"],
            "core_value_classes": ["pricing", "sla_rate_limit", "quality_benchmark", "payment"],
            "audit_fields": VALUE_CLASSES,
            "note": (
                "This is a metadata-surface audit. It does not verify provider claims or "
                "crawl every linked repository; it asks what value metadata is directly "
                "available from registries, directories, and MCPCorpus records."
            ),
        },
    }


def source_summary(rows: list[AuditRow]) -> dict[str, Any]:
    n = len(rows)
    counts: dict[str, dict[str, int]] = {}
    rates: dict[str, dict[str, float]] = {}
    for field in VALUE_CLASSES:
        counts[field] = {}
        rates[field] = {}
        for label in ["absent", "human_readable", "structured_unverified", "structured_verified", "machine_actionable"]:
            count = sum(1 for row in rows if getattr(row, field) == label)
            counts[field][label] = count
            rates[field][label] = round(count / n, 4) if n else 0.0

    core_all = sum(1 for row in rows if row.all_core_value_classes)
    structured_any = sum(1 for row in rows if row.structured_value_classes > 0)
    machine_any = sum(1 for row in rows if row.machine_actionable_value_classes > 0)
    return {
        "n": n,
        "counts": counts,
        "rates": rates,
        "all_core_value_classes": {"count": core_all, "rate": round(core_all / n, 4) if n else 0.0},
        "any_structured_value_class": {"count": structured_any, "rate": round(structured_any / n, 4) if n else 0.0},
        "any_machine_actionable_value_class": {"count": machine_any, "rate": round(machine_any / n, 4) if n else 0.0},
    }


def write_outputs(rows: list[AuditRow], summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "mcp_value_metadata_audit.csv"
    json_path = output_dir / "mcp_value_metadata_audit.json"
    md_path = output_dir / "mcp_value_metadata_audit.md"

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(asdict(row) for row in rows)

    json_path.write_text(
        json.dumps({"summary": summary, "rows": [asdict(row) for row in rows]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# MCP Value Metadata Audit",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Sample size: {summary['sample_size']} entries",
        "",
        "This audit samples MCP registries, directories, and MCPCorpus records to measure whether service-selection value metadata is exposed before invocation.",
        "",
        "Label meanings:",
        "",
        "- `absent`: no direct signal found in the registry/directory/corpus record.",
        "- `human_readable`: text mentions the concept, but not in a machine-actionable schema.",
        "- `structured_unverified`: structured field exists, but without independent verification semantics.",
        "- `machine_actionable`: structured field is directly usable by an agent for provenance/security-style decisions.",
        "",
        "## Overall Coverage",
        "",
        "| Field | Absent | Human-readable | Structured | Machine-actionable |",
        "|---|---:|---:|---:|---:|",
    ]
    overall = summary["overall"]
    for field in VALUE_CLASSES:
        counts = overall["counts"][field]
        structured = counts["structured_unverified"] + counts["structured_verified"]
        lines.append(
            f"| {field} | {counts['absent']} | {counts['human_readable']} | "
            f"{structured} | {counts['machine_actionable']} |"
        )

    all_core = overall["all_core_value_classes"]
    lines.extend([
        "",
        f"Entries with all four core value classes (pricing + SLA/rate-limit + quality/benchmark + payment): "
        f"**{all_core['count']} / {overall['n']} ({all_core['rate'] * 100:.1f}%)**.",
        "",
        "## By Source",
        "",
        "| Source | n | All core classes | Any structured class | Any machine-actionable class |",
        "|---|---:|---:|---:|---:|",
    ])
    for source, data in summary["sources"].items():
        lines.append(
            f"| {source} | {data['n']} | "
            f"{data['all_core_value_classes']['count']} ({data['all_core_value_classes']['rate'] * 100:.1f}%) | "
            f"{data['any_structured_value_class']['count']} ({data['any_structured_value_class']['rate'] * 100:.1f}%) | "
            f"{data['any_machine_actionable_value_class']['count']} ({data['any_machine_actionable_value_class']['rate'] * 100:.1f}%) |"
        )

    lines.extend([
        "",
        "## Source Notes",
        "",
        "- Official MCP Registry: sampled via `https://registry.modelcontextprotocol.io/v0/servers`.",
        "- Glama: sampled via `https://glama.ai/api/mcp/v1/servers`.",
        "- MCP Atlas: sampled by extracting GitHub links and surrounding snippets from `https://mcpatlas.dev/browse`.",
        "- FindMCP: homepage metadata recorded; no stable public listing endpoint was found during this audit.",
        "- MCPCorpus: sampled from `Website/mcpso_servers_cleaned.json` on Hugging Face.",
        "",
        "## Methodological Caveats",
        "",
        "- This is a metadata-surface audit, not a full crawl of every linked repository or pricing page.",
        "- Keyword patterns can over-count human-readable mentions such as a tool that manages billing data but does not expose its own pricing.",
        "- Structured provenance/security fields are common because registries naturally contain repository, package, license, and auth metadata; this should not be confused with structured economic value metadata.",
        "- The strongest ASM claim should focus on the low rate of complete core value coverage, especially pricing + SLA + quality + payment in the same entry.",
        "",
        "## Sample Rows",
        "",
        "| Source | Name | Pricing | SLA/rate | Quality | Payment | Provenance | Security/trust |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in rows[:40]:
        lines.append(
            f"| {row.source} | {row.name[:70]} | {row.pricing} | {row.sla_rate_limit} | "
            f"{row.quality_benchmark} | {row.payment} | {row.provenance} | {row.security_trust} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit MCP ecosystem value metadata across registries/directories/corpora.")
    parser.add_argument("--output-dir", type=Path, default=Path("experiments/results"))
    parser.add_argument("--sample-size", type=int, default=600, help="Approximate total row target.")
    parser.add_argument("--official-limit", type=int, default=150)
    parser.add_argument("--glama-limit", type=int, default=150)
    parser.add_argument("--atlas-limit", type=int, default=75)
    parser.add_argument("--findmcp-limit", type=int, default=1)
    parser.add_argument("--mcpcorpus-limit", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    targets = {
        "official_mcp_registry": args.official_limit,
        "glama": args.glama_limit,
        "mcp_atlas": args.atlas_limit,
        "findmcp": args.findmcp_limit,
        "mcpcorpus": args.mcpcorpus_limit,
    }

    fetchers = [
        ("official_mcp_registry", lambda: fetch_official_registry(args.official_limit)),
        ("glama", lambda: fetch_glama(args.glama_limit)),
        ("mcp_atlas", lambda: fetch_mcpatlas(args.atlas_limit)),
        ("findmcp", lambda: fetch_findmcp(args.findmcp_limit)),
        ("mcpcorpus", lambda: fetch_mcpcorpus(args.mcpcorpus_limit, args.seed)),
    ]

    rows: list[AuditRow] = []
    for source, fetcher in fetchers:
        try:
            source_rows = fetcher()
        except Exception as exc:  # Keep the audit reproducible even if one aggregator changes.
            print(f"warning: failed to fetch {source}: {exc}")
            source_rows = []
        print(f"{source}: {len(source_rows)} rows")
        rows.extend(source_rows)

    if args.sample_size and len(rows) > args.sample_size:
        rng = random.Random(args.seed)
        rows = rng.sample(rows, args.sample_size)

    summary = summarize(rows, generated_at, targets)
    write_outputs(rows, summary, args.output_dir)

    overall = summary["overall"]
    all_core = overall["all_core_value_classes"]
    print(json.dumps({
        "generated_at": generated_at,
        "sample_size": len(rows),
        "all_core_value_classes": all_core,
        "sources": {source: data["n"] for source, data in summary["sources"].items()},
    }, indent=2))


if __name__ == "__main__":
    main()
