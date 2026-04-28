#!/usr/bin/env python3
"""Audit public MCP server repositories for value metadata exposure.

The goal is not to prove every repository lacks pricing or SLA data. It is a
small, reproducible ecosystem measurement: sample public GitHub repositories
that appear to publish MCP servers, inspect public repo text, and quantify how
often agents can find structured value metadata before invoking a service.

Outputs:
  experiments/results/mcp_ecosystem_audit.csv
  experiments/results/mcp_ecosystem_audit.json
  experiments/results/mcp_ecosystem_audit.md
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_QUERIES = [
    "topic:mcp-server",
    "mcp server in:name,description",
    "modelcontextprotocol server in:readme",
    "mcp-server in:name,description",
]

VALUE_PATTERNS = {
    "pricing": re.compile(r"\b(pricing|price|cost|billing|free tier|paid|usd|\$|per request|per token)\b", re.I),
    "sla": re.compile(r"\b(sla|uptime|latency|p50|p95|p99|rate limit|throttle|qps|requests per)\b", re.I),
    "quality": re.compile(r"\b(benchmark|eval|evaluation|accuracy|quality|leaderboard|score|pass rate)\b", re.I),
    "payment": re.compile(r"\b(payment|stripe|invoice|subscription|paid plan|billing account|payment method)\b", re.I),
    "structured_asm": re.compile(r"\b(x-asm|asm_version|agent service manifest|service manifest)\b", re.I),
}


@dataclass
class RepoAudit:
    repo: str
    url: str
    stars: int
    default_branch: str
    query_source: str
    search_rank: int
    pricing: bool
    sla: bool
    quality: bool
    payment: bool
    structured_asm: bool
    inspected_chars: int
    evidence: str


def fetch_json(url: str, token: str | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "asm-ecosystem-audit",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_error: Exception | None = None
    for attempt in range(3):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (http.client.RemoteDisconnected, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch JSON after retries: {url}") from last_error


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "asm-ecosystem-audit"})
    try:
        with urlopen(req, timeout=6) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text" not in content_type and "json" not in content_type and "octet-stream" not in content_type:
                return ""
            return resp.read(250_000).decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError):
        return ""


def search_repositories(queries: Iterable[str], sample_size: int, token: str | None) -> list[dict]:
    repos: dict[str, dict] = {}
    for query in queries:
        encoded = quote(query)
        url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page=100"
        try:
            data = fetch_json(url, token)
        except HTTPError as exc:
            print(f"warning: GitHub search failed for {query!r}: HTTP {exc.code}")
            continue
        for rank, item in enumerate(data.get("items", []), 1):
            full_name = item["full_name"]
            item = dict(item)
            item["_asm_query_source"] = query
            item["_asm_search_rank"] = rank
            repos.setdefault(full_name, item)
            if len(repos) >= sample_size:
                return list(repos.values())[:sample_size]
        time.sleep(1.0)
    return list(repos.values())[:sample_size]


def repo_text(full_name: str, branch: str) -> str:
    raw_base = f"https://raw.githubusercontent.com/{full_name}/{branch}"
    candidates = [
        "README.md",
        "README.mdx",
        "package.json",
        "pyproject.toml",
        "mcp.json",
    ]
    chunks = []
    for candidate in candidates:
        text = fetch_text(f"{raw_base}/{candidate}")
        if text:
            chunks.append(f"\n--- {candidate} ---\n{text}")
        time.sleep(0.15)
    return "\n".join(chunks)


def evidence_for(text: str, keys: list[str]) -> str:
    snippets = []
    flat = re.sub(r"\s+", " ", text)
    for key in keys:
        pattern = VALUE_PATTERNS[key]
        match = pattern.search(flat)
        if match:
            start = max(match.start() - 70, 0)
            end = min(match.end() + 90, len(flat))
            snippets.append(f"{key}: ...{flat[start:end]}...")
    return " | ".join(snippets)[:600]


def audit_repo(item: dict) -> RepoAudit:
    full_name = item["full_name"]
    branch = item.get("default_branch") or "main"
    text = repo_text(full_name, branch)
    flags = {name: bool(pattern.search(text)) for name, pattern in VALUE_PATTERNS.items()}
    keys = [name for name, present in flags.items() if present]
    return RepoAudit(
        repo=full_name,
        url=item["html_url"],
        stars=int(item.get("stargazers_count") or 0),
        default_branch=branch,
        query_source=item.get("_asm_query_source", ""),
        search_rank=int(item.get("_asm_search_rank") or 0),
        pricing=flags["pricing"],
        sla=flags["sla"],
        quality=flags["quality"],
        payment=flags["payment"],
        structured_asm=flags["structured_asm"],
        inspected_chars=len(text),
        evidence=evidence_for(text, keys),
    )


def summarize(rows: list[RepoAudit], generated_at: str, queries: list[str]) -> dict:
    n = len(rows)
    def rate(field: str) -> float:
        return round(sum(1 for row in rows if getattr(row, field)) / n, 4) if n else 0.0

    return {
        "generated_at": generated_at,
        "sample_size": n,
        "queries": queries,
        "rates": {
            "pricing": rate("pricing"),
            "sla": rate("sla"),
            "quality": rate("quality"),
            "payment": rate("payment"),
            "structured_asm": rate("structured_asm"),
            "all_value_fields": round(
                sum(1 for row in rows if row.pricing and row.sla and row.quality and row.payment) / n,
                4,
            ) if n else 0.0,
        },
        "counts": {
            field: sum(1 for row in rows if getattr(row, field))
            for field in ["pricing", "sla", "quality", "payment", "structured_asm"]
        },
    }


def write_outputs(rows: list[RepoAudit], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "mcp_ecosystem_audit.csv"
    json_path = output_dir / "mcp_ecosystem_audit.json"
    md_path = output_dir / "mcp_ecosystem_audit.md"

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(asdict(row) for row in rows)

    json_path.write_text(
        json.dumps({"summary": summary, "rows": [asdict(row) for row in rows]}, indent=2),
        encoding="utf-8",
    )

    rates = summary["rates"]
    counts = summary["counts"]
    n = summary["sample_size"]
    lines = [
        "# MCP Ecosystem Value Metadata Audit",
        "",
        f"Generated at: {summary['generated_at']}",
        f"Sample size: {n} public GitHub repositories",
        "",
        "This audit samples public repositories likely to contain MCP servers and scans public README/config text for value metadata that an agent could use before invocation. It is a conservative text audit, not a manual legal or pricing verification.",
        "",
        "## Coverage",
        "",
        "| Metadata class | Repos | Rate |",
        "|---|---:|---:|",
    ]
    for field in ["pricing", "sla", "quality", "payment", "structured_asm"]:
        lines.append(f"| {field} | {counts[field]} / {n} | {rates[field] * 100:.1f}% |")
    lines.append(f"| all_value_fields | {round(rates['all_value_fields'] * n)} / {n} | {rates['all_value_fields'] * 100:.1f}% |")
    lines.extend([
        "",
        "## Sample",
        "",
        "| Repo | Stars | Pricing | SLA/rate | Quality | Payment | ASM/x-asm |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows[:25]:
        yn = lambda value: "yes" if value else "no"
        lines.append(
            f"| [{row.repo}]({row.url}) | {row.stars} | {yn(row.pricing)} | {yn(row.sla)} | "
            f"{yn(row.quality)} | {yn(row.payment)} | {yn(row.structured_asm)} |"
        )
    lines.extend([
        "",
        "## Method",
        "",
        "GitHub repository search queries:",
        "",
    ])
    lines.extend(f"- `{query}`" for query in summary["queries"])
    lines.extend([
        "",
        "Scanned files when present: `README.md`, `README.mdx`, `package.json`, `pyproject.toml`, `mcp.json`.",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit public MCP server repos for ASM-relevant value metadata.")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--token", default=None, help="Optional GitHub token for higher API rate limits.")
    parser.add_argument("--query", action="append", default=None, help="Override GitHub search query. Can be repeated.")
    args = parser.parse_args()

    queries = args.query or DEFAULT_QUERIES
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = search_repositories(queries, args.sample_size, args.token)
    rows = []
    for index, item in enumerate(repos, 1):
        print(f"[{index}/{len(repos)}] auditing {item['full_name']}", flush=True)
        rows.append(audit_repo(item))
    summary = summarize(rows, generated_at, queries)
    write_outputs(rows, summary, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
