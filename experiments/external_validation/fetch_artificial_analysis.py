#!/usr/bin/env python3
"""Fetch Artificial Analysis leaderboard data for ASM-cataloged LLMs.

STATUS: WORK IN PROGRESS — DO NOT CITE IN PAPER.

Artificial Analysis publishes per-model multi-axis benchmarks at
https://artificialanalysis.ai but does not expose a stable JSON API. The data
is embedded in Next.js streaming RSC chunks. The current best-effort regex
extractor matches 0 records as of 2026-05-03 because the streaming format
does not consistently yield well-formed JSON objects under simple regex
brace-balancing. Two paths to finish:

  1. Manual CSV: copy the table from the website into
     experiments/results/external_validation/artificial_analysis_manual.csv
     and feed that into the correlation analysis. Less elegant but works
     today.
  2. Headless browser: render the page with Playwright/Puppeteer, extract
     the React tree state, dump as JSON. Heavier dependency.

Until either lands, the §6.8 (External Preference Correlation) experiment
relies on LM Arena Elo (HF Datasets) and OpenRouter rankings, both of which
have stable bulk export paths.

Output (when working):
    experiments/results/external_validation/artificial_analysis_snapshot.json
    experiments/results/external_validation/artificial_analysis_snapshot.csv
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "experiments" / "results" / "external_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://artificialanalysis.ai/leaderboards/models"

# Map ASM service_id -> Artificial Analysis model name candidates (lowercase, partial-match).
ASM_TO_AA: dict[str, list[str]] = {
    "openai/gpt-4o@2024-11-20":            ["gpt-4o (nov '24)", "gpt-4o", "gpt 4o"],
    "anthropic/claude-sonnet-4@4.0":       ["claude sonnet 4", "claude-sonnet-4", "claude 4 sonnet"],
    "google/gemini-2.5-pro@2.5":           ["gemini 2.5 pro", "gemini-2.5-pro"],
    "deepseek/deepseek-v4-flash@4.0":      ["deepseek-v4", "deepseek v4", "deepseek v3.2", "deepseek-v3.2"],
    "qwen/qwen3-max@3.0":                  ["qwen3-max", "qwen 3 max", "qwen3 max"],
    "moonshot/kimi-k2.5@2.5":              ["kimi k2.5", "kimi-k2.5", "kimi k2"],
    "zhipu/glm-5@5.0":                     ["glm-5", "glm 5", "glm-4.6", "glm 4.6"],
    "minimax/m2.7@2.7":                    ["minimax m2.7", "minimax-m2", "minimax m2"],
}

FIELDS_TO_KEEP = (
    "name", "model_creator_name", "intelligenceIndex",
    "price1mInputTokens", "price1mOutputTokens",
    "medianOutputTokensPerSecond", "medianTimeToFirstTokenSeconds",
    "medianEndToEndResponseTimeSeconds", "contextWindowTokens",
)


def fetch_page() -> str:
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (asm-validation)"})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_next_data(html: str) -> dict:
    """Find embedded model records in Next.js RSC streaming chunks.

    The leaderboard page uses Next.js server components, which serialise data
    as escaped JSON inside <script> tags rather than __NEXT_DATA__. We extract
    each model object by scanning for JSON dicts that contain
    'intelligenceIndex' and a 'name' field within ~1KB of each other.
    """
    # Unescape JSON string-of-string layers used by RSC.
    unescaped = html.replace('\\"', '"').replace("\\\\", "\\")

    # Each model object looks like:
    # {"name":"GPT-4o (Nov '24)", ..., "intelligenceIndex":40.5, ...}
    # We scan for opening brace + 'intelligenceIndex' within a bounded window.
    found: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(r'\{[^{}]*"intelligenceIndex":[0-9.]+[^{}]*\}', re.DOTALL)
    for m in pattern.finditer(unescaped):
        blob = m.group(0)
        # Best-effort fix: balance braces and ensure all double-quoted keys are intact.
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        name = obj.get("name") or obj.get("model_name") or ""
        if not name:
            continue
        key = name.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        found.append(obj)
    return {"_models": found}


def find_models(data: dict) -> list[dict]:
    return data.get("_models") or []


def project(model: dict) -> dict:
    out = {}
    for k in FIELDS_TO_KEEP:
        v = model.get(k)
        if isinstance(v, str) and v == "$undefined":
            v = None
        out[k] = v
    return out


def match_asm(model_name: str) -> str | None:
    name_l = model_name.lower()
    for asm_id, aliases in ASM_TO_AA.items():
        for alias in aliases:
            if alias in name_l:
                return asm_id
    return None


def main() -> None:
    print(f"Fetching {URL} ...", file=sys.stderr)
    html = fetch_page()
    data = extract_next_data(html)
    models = find_models(data)
    print(f"  found {len(models)} model rows in __NEXT_DATA__", file=sys.stderr)

    rows = []
    for m in models:
        compact = project(m)
        compact["asm_service_id"] = match_asm(compact.get("name") or "")
        rows.append(compact)

    matched = [r for r in rows if r.get("asm_service_id")]
    print(f"  matched {len(matched)} ASM-cataloged models", file=sys.stderr)
    for r in matched:
        print(f"    {r['asm_service_id']:<40} -> {r.get('name')}: intelligence={r.get('intelligenceIndex')}",
              file=sys.stderr)

    snapshot = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": URL,
        "total_models_seen": len(rows),
        "asm_matched": len(matched),
        "asm_models": matched,
        "all_models": rows,
    }
    json_path = OUTPUT_DIR / "artificial_analysis_snapshot.json"
    json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = OUTPUT_DIR / "artificial_analysis_snapshot.csv"
    if matched:
        import csv as _csv
        keys = ["asm_service_id"] + [k for k in matched[0].keys() if k != "asm_service_id"]
        with csv_path.open("w", newline="", encoding="utf-8") as fp:
            writer = _csv.DictWriter(fp, fieldnames=keys)
            writer.writeheader()
            for r in matched:
                writer.writerow(r)

    print(f"\nWrote {json_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"Wrote {csv_path.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
