#!/usr/bin/env python3
"""
serp_scraper.py — Google SERP scraper for the Content Gap Finder.

Scrapes the top 10 organic results per keyword.

Defenses handled:
  - Browser rendering → ScrapeOps Proxy API opens Google in a browser
  - IP reputation     → ScrapeOps Proxy API handles proxy selection and retries
  - Throughput        → five concurrent requests, matching the API plan limit

Usage:
  python serp_scraper.py --keyword "best crm for small business"      # single keyword
  python serp_scraper.py --keywords keywords.txt --out data/serp_results.csv
  python serp_scraper.py --keyword "best crm" --demo                  # offline fixture
"""

import argparse
import concurrent.futures
import csv
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
FIXTURE = BASE_DIR / "fixtures" / "serp_demo.html"
CONFIG_PATH = BASE_DIR / "config.json"

GOOGLE_URL = "https://www.google.com/search"
PROXY_API_URL = "https://proxy.scrapeops.io/v1/"
MAX_WORKERS = 5


# ---------------------------------------------------------------- config
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    example = BASE_DIR / "config.example.json"
    return json.loads(example.read_text()) if example.exists() else {}


def get_api_key(cfg: dict) -> str | None:
    key = cfg.get("api_key", "")
    if key.startswith("env:"):
        return os.environ.get(key[4:])
    return key or os.environ.get("SCRAPEOPS_API_KEY")


# ---------------------------------------------------------------- scraping
def fetch_serp(keyword: str, cfg: dict, demo: bool = False) -> str:
    """Return raw HTML of the Google results page for `keyword`."""
    if demo:
        return FIXTURE.read_text()

    api_key = get_api_key(cfg)
    if not api_key:
        sys.exit("❌ No API key. Set SCRAPEOPS_API_KEY or use --demo.")

    geo = cfg.get("geo", {})
    google_params = {
        "q": keyword,
        "num": 10,
        "hl": geo.get("hl", "en"),
        "gl": geo.get("gl", "us"),
    }
    target_url = f"{GOOGLE_URL}?{urlencode(google_params)}"
    api_params = {
        "api_key": api_key,
        "url": target_url,
        "render_js": "true",
        "country": geo.get("country", "us"),
    }

    try:
        resp = requests.get(PROXY_API_URL, params=api_params, timeout=120)
        # Don't string-match "captcha" / "/sorry/index" — Google embeds those in
        # normal SERP JS. Treat HTTP 200 as success; empty parses retry below.
        if resp.status_code == 200:
            return resp.text
        print(f"  ⚠️  status {resp.status_code}")
    except requests.RequestException as e:
        print(f"  ⚠️  {e}")
    return ""


# ---------------------------------------------------------------- parsing
def parse_serp(html: str) -> list[dict]:
    """
    Extract organic positions 1-10.

    Stable-enough pattern: every organic result is an <h3> inside an <a>.
    Deliberately skipped: ads, map packs, featured snippets, AI overviews,
    "People Also Ask". If it isn't a clean organic result, we don't want it.
    """
    soup = BeautifulSoup(html, "lxml")
    results, seen = [], set()

    for h3 in soup.find_all("h3"):
        a = h3.find_parent("a")
        if not a or not a.get("href", "").startswith("http"):
            continue
        url = a["href"]
        domain = urlparse(url).netloc.replace("www.", "")
        if not domain or "google." in domain or domain in seen:
            continue
        seen.add(domain)
        results.append({"position": len(results) + 1, "title": h3.get_text(strip=True),
                        "url": url, "domain": domain})
        if len(results) == 10:
            break
    return results


def scrape_keyword(keyword: str, cfg: dict, demo: bool = False) -> tuple[str, list[dict]]:
    """Fetch and parse one keyword, retrying when the page has no organic results."""
    max_retries = 1 if demo else cfg.get("max_retries", 3)
    for attempt in range(1, max_retries + 1):
        html = fetch_serp(keyword, cfg, demo=demo)
        results = parse_serp(html) if html else []
        if results:
            return keyword, results
        if attempt < max_retries:
            print(f"  ⚠️  attempt {attempt}: no organic results — retrying")
            time.sleep(2 * attempt)
    return keyword, []


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description="Scrape Google SERPs → CSV")
    p.add_argument("--keyword", help="single keyword")
    p.add_argument("--keywords", help="file with one keyword per line")
    p.add_argument("--out", default=str(BASE_DIR / "data" / "serp_results.csv"))
    p.add_argument("--demo", action="store_true", help="offline fixture, no network")
    args = p.parse_args()

    cfg = load_config()
    keywords = []
    if args.keyword:
        keywords = [args.keyword]
    elif args.keywords:
        keywords = [k.strip() for k in Path(args.keywords).read_text().splitlines() if k.strip()]
    else:
        p.error("pass --keyword or --keywords")

    rows, failures = [], 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = [pool.submit(scrape_keyword, kw, cfg, args.demo) for kw in keywords]
        for i, job in enumerate(jobs, 1):
            kw, results = job.result()
            print(f"[{i}/{len(keywords)}] {kw}")
            if not results:
                failures += 1
                print("  ⚠️  no results parsed — logged, moving on")
            rows.extend({"keyword": kw, **result} for result in results)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "position", "title", "url", "domain"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ {len(rows)} results across {len(keywords)} keyword(s) → {out}")
    if failures:
        print(f"⚠️  {failures} keyword(s) failed to parse — see log lines above (designed to survive this)")


if __name__ == "__main__":
    main()
