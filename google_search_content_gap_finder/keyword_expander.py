#!/usr/bin/env python3
"""
keyword_expander.py — build the keyword universe.

Three sources:
  1. Seed terms (--seeds file) × intent modifiers  → the long tail
  2. Competitor sitemaps (--sitemap url)           → their content roadmap,
     as search phrases, free
  3. Dedupe + write one keyword per line

Usage:
  python keyword_expander.py --seeds seeds.txt --out keywords.txt
  python keyword_expander.py --seeds seeds.txt --sitemap https://competitor.com/sitemap.xml --out keywords.txt
  python keyword_expander.py --seeds seeds.txt --demo --out keywords.txt   # offline
"""

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

BASE_DIR = Path(__file__).resolve().parent

MODIFIERS = [
    "best {seed}",
    "{seed} pricing",
    "{seed} alternatives",
    "how to choose {seed}",
    "{seed} for small business",
    "{seed} for startups",
    "free {seed}",
    "{seed} template",
    "{seed} checklist",
]

DEMO_SITEMAP_URLS = [
    "/blog/best-crm-for-real-estate-agents",
    "/blog/crm-implementation-checklist",
    "/blog/crm-vs-spreadsheet",
    "/blog/hubspot-alternatives",
    "/blog/crm-for-small-business",
    "/blog/how-to-choose-a-crm",
]


def expand_seeds(seeds: list[str]) -> list[str]:
    out = list(seeds)
    for seed in seeds:
        out.extend(m.format(seed=seed) for m in MODIFIERS)
    return out


def slug_to_phrase(url: str) -> str | None:
    """'/blog/best-crm-for-real-estate-agents' → 'best crm for real estate agents'"""
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(html?|php)$", "", slug)
    phrase = slug.replace("-", " ").replace("_", " ").strip()
    # filter junk: dates, ids, category pages, super-short slugs
    if not phrase or len(phrase.split()) < 3 or re.search(r"\d{4}", phrase):
        return None
    return phrase


def sitemap_keywords(sitemap_url: str, demo: bool = False) -> list[str]:
    if demo:
        return [p for u in DEMO_SITEMAP_URLS if (p := slug_to_phrase(u))]
    # Same trick as the SERP scraper: impersonate Chrome's TLS fingerprint.
    resp = cffi_requests.get(sitemap_url, impersonate="chrome", timeout=30)
    resp.raise_for_status()
    locs = re.findall(r"<loc>([^<]+)</loc>", resp.text)
    phrases = [p for u in locs if (p := slug_to_phrase(u))]
    print(f"  🥷 {sitemap_url} → {len(phrases)} keyword phrases from {len(locs)} URLs")
    return phrases


def main() -> None:
    p = argparse.ArgumentParser(description="Seeds × modifiers + sitemaps → keyword list")
    p.add_argument("--seeds", required=True, help="file with one seed term per line")
    p.add_argument("--sitemap", action="append", default=[], help="competitor sitemap URL (repeatable)")
    p.add_argument("--out", default="keywords.txt")
    p.add_argument("--demo", action="store_true", help="offline: fake sitemap URLs")
    args = p.parse_args()

    seeds = [s.strip() for s in Path(args.seeds).read_text().splitlines() if s.strip()]
    keywords = expand_seeds(seeds)
    print(f"🏷️  {len(seeds)} seeds × {len(MODIFIERS)} modifiers → {len(keywords)} terms")

    for sm in args.sitemap:
        keywords.extend(sitemap_keywords(sm, demo=args.demo))
    if args.demo and not args.sitemap:
        keywords.extend(sitemap_keywords("demo://competitor/sitemap.xml", demo=True))

    # dedupe, preserve order
    seen, unique = set(), []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique.append(kw)

    Path(args.out).write_text("\n".join(unique) + "\n")
    print(f"✅ {len(unique)} unique keywords → {args.out}")


if __name__ == "__main__":
    main()
