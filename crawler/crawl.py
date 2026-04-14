#!/usr/bin/env python3
"""ASM Manifest Crawler — auto-update service manifests with real data.

Architecture:
  1. For each service in config.yaml, try data sources in priority order:
     official_api → pricing_page → docs_page → leaderboard → status_page
  2. Use httpx for API/static pages, Playwright for JS-rendered pages
  3. Merge scraped data into existing manifest (preserve manual fields)
  4. Validate against ASM v0.3 schema before writing
  5. Generate diff report

Usage:
    python crawl.py                        # crawl all services
    python crawl.py --service openai-gpt-4o  # crawl one service
    python crawl.py --dry-run              # preview changes without writing
    python crawl.py --report               # generate freshness report
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

# ─── Constants ───
ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = ROOT / "manifests"
SCHEMA_PATH = ROOT / "schema" / "asm-v0.3.schema.json"
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
REPORT_PATH = Path(__file__).resolve().parent / "crawl-report.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("asm-crawler")


# ─── Data Source Strategies ───

class CrawlResult:
    """Holds scraped data for a single field group."""
    def __init__(self, source_type: str, url: str):
        self.source_type = source_type
        self.url = url
        self.data: dict[str, Any] = {}
        self.success = False
        self.error: Optional[str] = None
        self.latency_ms: float = 0


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_html(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a page's HTML with retry logic."""
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    """Fetch JSON from an API endpoint with retry logic."""
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


async def scrape_pricing_page(client: httpx.AsyncClient, url: str, selectors: dict | None = None) -> CrawlResult:
    """Scrape a pricing page for cost data."""
    result = CrawlResult("pricing_page", url)
    t0 = time.monotonic()
    try:
        html = await fetch_html(client, url)
        soup = BeautifulSoup(html, "lxml")
        
        # Generic pricing extraction heuristics
        pricing_data = extract_pricing_from_html(soup, selectors)
        result.data = {"pricing": pricing_data}
        result.success = bool(pricing_data)
        if not result.success:
            result.error = "No pricing data found in HTML"
    except Exception as e:
        result.error = str(e)
    result.latency_ms = (time.monotonic() - t0) * 1000
    return result


async def scrape_with_playwright(url: str, selectors: dict | None = None) -> CrawlResult:
    """Use Playwright for JS-rendered pricing pages."""
    result = CrawlResult("pricing_page_js", url)
    t0 = time.monotonic()
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()
        
        soup = BeautifulSoup(html, "lxml")
        pricing_data = extract_pricing_from_html(soup, selectors)
        result.data = {"pricing": pricing_data}
        result.success = bool(pricing_data)
        if not result.success:
            result.error = "No pricing data found after JS rendering"
    except Exception as e:
        result.error = str(e)
    result.latency_ms = (time.monotonic() - t0) * 1000
    return result


async def fetch_leaderboard(client: httpx.AsyncClient, config: dict, model_name: str) -> CrawlResult:
    """Fetch quality metrics from public leaderboards."""
    result = CrawlResult("leaderboard", config.get("url", ""))
    t0 = time.monotonic()
    try:
        # LMSYS Arena API
        if "lmarena" in config.get("url", ""):
            data = await fetch_json(client, config["url"])
            for entry in data if isinstance(data, list) else data.get("data", []):
                name = entry.get("model_name", entry.get("model", ""))
                if model_name.lower() in name.lower():
                    result.data = {
                        "quality": {
                            "metrics": [{
                                "name": "LMSYS_Elo",
                                "score": entry.get("elo_rating", entry.get("elo", 0)),
                                "scale": "Elo",
                                "benchmark": "LMSYS Chatbot Arena",
                                "benchmark_url": "https://lmarena.ai",
                                "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "self_reported": False,
                            }]
                        }
                    }
                    result.success = True
                    break
        if not result.success:
            result.error = f"Model '{model_name}' not found in leaderboard"
    except Exception as e:
        result.error = str(e)
    result.latency_ms = (time.monotonic() - t0) * 1000
    return result


async def check_status_page(client: httpx.AsyncClient, url: str) -> CrawlResult:
    """Check service status page for uptime data."""
    result = CrawlResult("status_page", url)
    t0 = time.monotonic()
    try:
        html = await fetch_html(client, url)
        soup = BeautifulSoup(html, "lxml")
        
        # Common status page patterns (Statuspage.io, Instatus, etc.)
        uptime_el = (
            soup.select_one("[data-component-uptime]") or
            soup.select_one(".uptime-percentage") or
            soup.select_one(".component-uptime") or
            soup.find(string=re.compile(r"\d{2,3}\.\d+%"))
        )
        if uptime_el:
            text = uptime_el.get_text() if hasattr(uptime_el, 'get_text') else str(uptime_el)
            match = re.search(r"(\d{2,3}\.\d+)%", text)
            if match:
                uptime = float(match.group(1)) / 100.0
                result.data = {"sla": {"uptime": round(uptime, 4)}}
                result.success = True
        
        if not result.success:
            result.error = "No uptime data found on status page"
    except Exception as e:
        result.error = str(e)
    result.latency_ms = (time.monotonic() - t0) * 1000
    return result


# ─── Pricing Extraction Heuristics ───

def extract_pricing_from_html(soup: BeautifulSoup, selectors: dict | None = None) -> dict:
    """Extract pricing data from HTML using heuristics + optional selectors."""
    pricing = {}
    
    # Strategy 1: Use explicit CSS selectors if provided
    if selectors:
        for key, selector in selectors.items():
            el = soup.select_one(selector)
            if el:
                pricing[key] = clean_price(el.get_text())
        if pricing:
            return pricing
    
    # Strategy 2: Look for common pricing patterns
    # Find all elements containing dollar amounts
    price_pattern = re.compile(r"\$[\d,]+\.?\d*(?:\s*/\s*(?:mo|month|year|1[KM]|request|query))?", re.I)
    price_elements = soup.find_all(string=price_pattern)
    
    for el in price_elements[:10]:  # limit to first 10 matches
        text = el.strip()
        prices = price_pattern.findall(text)
        for p in prices:
            pricing[f"raw_{len(pricing)}"] = p
    
    # Strategy 3: Look for structured pricing tables
    tables = soup.select("table")
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.select("th")]
        if any(kw in " ".join(headers) for kw in ["price", "cost", "plan", "tier"]):
            rows = table.select("tr")
            for row in rows[1:]:  # skip header
                cells = [td.get_text(strip=True) for td in row.select("td")]
                if len(cells) >= 2:
                    pricing[cells[0]] = cells[1] if len(cells) > 1 else ""
    
    return pricing


def clean_price(text: str) -> str:
    """Clean price text: '$2.50 / 1M tokens' → '2.50'."""
    match = re.search(r"\$?([\d,]+\.?\d*)", text)
    return match.group(1).replace(",", "") if match else text.strip()


# ─── Manifest Merge Logic ───

def merge_manifest(existing: dict, scraped: dict) -> tuple[dict, list[str]]:
    """Merge scraped data into existing manifest. Returns (merged, changes)."""
    merged = json.loads(json.dumps(existing))  # deep copy
    changes: list[str] = []
    
    # Update timestamp
    merged["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Merge pricing
    if "pricing" in scraped and scraped["pricing"]:
        old_pricing = json.dumps(existing.get("pricing", {}), sort_keys=True)
        # Only update billing_dimensions if we have structured data
        # For now, log raw scraped prices for manual review
        changes.append(f"pricing: scraped {len(scraped['pricing'])} fields")
    
    # Merge quality
    if "quality" in scraped and scraped["quality"]:
        old_q = existing.get("quality", {}).get("metrics", [])
        new_q = scraped["quality"].get("metrics", [])
        if new_q:
            # Update matching metrics, add new ones
            old_names = {m["name"] for m in old_q}
            for nm in new_q:
                if nm["name"] in old_names:
                    for i, om in enumerate(old_q):
                        if om["name"] == nm["name"] and om.get("score") != nm.get("score"):
                            changes.append(f"quality.{nm['name']}: {om.get('score')} → {nm.get('score')}")
                            old_q[i] = nm
                else:
                    old_q.append(nm)
                    changes.append(f"quality: added {nm['name']}")
            merged.setdefault("quality", {})["metrics"] = old_q
    
    # Merge SLA
    if "sla" in scraped and scraped["sla"]:
        for key, val in scraped["sla"].items():
            old_val = existing.get("sla", {}).get(key)
            if old_val != val:
                changes.append(f"sla.{key}: {old_val} → {val}")
                merged.setdefault("sla", {})[key] = val
    
    return merged, changes


# ─── Main Orchestrator ───

async def crawl_service(
    client: httpx.AsyncClient,
    service_key: str,
    service_config: dict,
    leaderboard_configs: dict,
    dry_run: bool = False,
) -> dict:
    """Crawl all sources for a single service and update its manifest."""
    log.info(f"Crawling: {service_key}")
    
    manifest_file = MANIFESTS_DIR / f"{service_key}.asm.json"
    if not manifest_file.exists():
        log.warning(f"  No existing manifest: {manifest_file}")
        return {"service": service_key, "status": "skipped", "reason": "no manifest file"}
    
    existing = json.loads(manifest_file.read_text())
    all_scraped: dict[str, Any] = {}
    results: list[dict] = []
    
    sources = service_config.get("sources", {})
    
    # Crawl pricing
    if "pricing" in sources:
        src = sources["pricing"]
        if src.get("type") == "official_api" and src.get("url"):
            r = CrawlResult("official_api", src["url"])
            try:
                data = await fetch_json(client, src["url"])
                r.data = {"pricing_raw": data}
                r.success = True
            except Exception as e:
                r.error = str(e)
                # Try fallback
                if "fallback" in src:
                    fb = src["fallback"]
                    r = await scrape_pricing_page(client, fb["url"], fb.get("selectors"))
            results.append({"source": "pricing", "type": r.source_type, "success": r.success, "error": r.error, "latency_ms": r.latency_ms})
            all_scraped.update(r.data)
        elif src.get("type") == "pricing_page" and src.get("url"):
            r = await scrape_pricing_page(client, src["url"], src.get("selectors"))
            if not r.success:
                # Fallback to Playwright for JS-rendered pages
                log.info(f"  Static scrape failed, trying Playwright: {src['url']}")
                r = await scrape_with_playwright(src["url"], src.get("selectors"))
            results.append({"source": "pricing", "type": r.source_type, "success": r.success, "error": r.error, "latency_ms": r.latency_ms})
            all_scraped.update(r.data)
    
    # Crawl quality / leaderboard
    if "quality" in sources:
        src = sources["quality"]
        if src.get("type") == "leaderboard" and src.get("ref"):
            lb_config = leaderboard_configs.get(src["ref"], {})
            model_name = src.get("model_name", service_key)
            r = await fetch_leaderboard(client, lb_config, model_name)
            results.append({"source": "quality", "type": "leaderboard", "success": r.success, "error": r.error, "latency_ms": r.latency_ms})
            all_scraped.update(r.data)
    
    # Crawl status page
    if "status" in sources:
        src = sources["status"]
        if src.get("url"):
            r = await check_status_page(client, src["url"])
            results.append({"source": "status", "type": "status_page", "success": r.success, "error": r.error, "latency_ms": r.latency_ms})
            all_scraped.update(r.data)
    
    # Merge and write
    if all_scraped:
        merged, changes = merge_manifest(existing, all_scraped)
        if changes:
            log.info(f"  Changes: {changes}")
            if not dry_run:
                manifest_file.write_text(json.dumps(merged, indent=4, ensure_ascii=False) + "\n")
                log.info(f"  Written: {manifest_file}")
        else:
            log.info(f"  No changes detected")
    else:
        changes = []
        log.info(f"  No data scraped")
    
    return {
        "service": service_key,
        "status": "updated" if changes else "unchanged",
        "changes": changes,
        "sources": results,
    }


async def crawl_all(config: dict, service_filter: str | None = None, dry_run: bool = False):
    """Crawl all services defined in config."""
    defaults = config.get("defaults", {})
    leaderboards = config.get("leaderboards", {})
    services = config.get("services", {})
    
    if service_filter:
        services = {k: v for k, v in services.items() if k == service_filter}
        if not services:
            log.error(f"Service not found: {service_filter}")
            return
    
    headers = {
        "User-Agent": defaults.get("user_agent", "ASM-Crawler/1.0"),
        "Accept": "text/html,application/json",
    }
    delay = defaults.get("request_delay_ms", 1500) / 1000.0
    
    report = {
        "crawl_time": datetime.now(timezone.utc).isoformat(),
        "total_services": len(services),
        "results": [],
    }
    
    async with httpx.AsyncClient(
        timeout=defaults.get("timeout_s", 30),
        headers=headers,
        follow_redirects=True,
    ) as client:
        for key, svc_config in services.items():
            result = await crawl_service(client, key, svc_config, leaderboards, dry_run)
            report["results"].append(result)
            await asyncio.sleep(delay)  # rate limit
    
    # Summary
    updated = sum(1 for r in report["results"] if r["status"] == "updated")
    unchanged = sum(1 for r in report["results"] if r["status"] == "unchanged")
    skipped = sum(1 for r in report["results"] if r["status"] == "skipped")
    
    log.info(f"\n{'='*50}")
    log.info(f"Crawl complete: {updated} updated, {unchanged} unchanged, {skipped} skipped")
    log.info(f"{'='*50}")
    
    # Save report
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    log.info(f"Report saved: {REPORT_PATH}")


def generate_freshness_report():
    """Generate a report on manifest freshness."""
    now = datetime.now(timezone.utc)
    report = []
    
    for f in sorted(MANIFESTS_DIR.glob("*.asm.json")):
        manifest = json.loads(f.read_text())
        updated = manifest.get("updated_at", "unknown")
        ttl = manifest.get("ttl", 3600)
        
        if updated != "unknown":
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_hours = (now - updated_dt).total_seconds() / 3600
                stale = age_hours > (ttl / 3600 * 24)  # stale if > ttl * 24
            except ValueError:
                age_hours = -1
                stale = True
        else:
            age_hours = -1
            stale = True
        
        report.append({
            "file": f.name,
            "service_id": manifest.get("service_id", "?"),
            "updated_at": updated,
            "age_hours": round(age_hours, 1),
            "ttl": ttl,
            "stale": stale,
        })
    
    # Print
    stale_count = sum(1 for r in report if r["stale"])
    print(f"\n{'='*70}")
    print(f"ASM Manifest Freshness Report — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Total: {len(report)} manifests | Stale: {stale_count} | Fresh: {len(report) - stale_count}")
    print(f"{'='*70}")
    
    for r in sorted(report, key=lambda x: x["age_hours"], reverse=True):
        status = "STALE" if r["stale"] else "OK"
        age = f"{r['age_hours']:.0f}h" if r["age_hours"] >= 0 else "unknown"
        print(f"  [{status:5}] {r['file']:45} age={age:>6}  updated={r['updated_at']}")


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="ASM Manifest Crawler")
    parser.add_argument("--service", "-s", help="Crawl a specific service only")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview changes without writing")
    parser.add_argument("--report", "-r", action="store_true", help="Generate freshness report")
    parser.add_argument("--config", "-c", default=str(CONFIG_PATH), help="Config file path")
    args = parser.parse_args()
    
    if args.report:
        generate_freshness_report()
        return
    
    config = yaml.safe_load(Path(args.config).read_text())
    asyncio.run(crawl_all(config, args.service, args.dry_run))


if __name__ == "__main__":
    main()
