#!/usr/bin/env python3
"""
gap_engine.py — turn raw SERP rankings into a prioritized content-gap report.

For every keyword:
  Q1  Does MY domain rank top 10?          → yes: skip (or flag pos 8-10 as weak_win)
  Q2  How many tracked competitors rank?   → more = more validated
  Q3  Average competitor position?         → pos 1 = proven traffic, pos 9 = weak signal

priority_score = round(competitor_count^1.5 * (11 - avg_position) * 4)
  - count^1.5 rewards multi-competitor validation super-linearly
  - (11 - avg_pos) rewards stronger positions
  - ×4 just spreads the scale to 0-100ish

Usage:
  python gap_engine.py --serps data/serp_results.csv \
      --my-domain yoursite.com --competitors a.com b.com --out data/content_gaps.csv
  python gap_engine.py --demo        # bundled sample data, zero setup
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SAMPLE = BASE_DIR / "data" / "sample_serp_results.csv"


def load_serps(path: Path) -> dict[str, list[dict]]:
    by_keyword: dict[str, list[dict]] = defaultdict(list)
    with path.open() as f:
        for row in csv.DictReader(f):
            row["position"] = int(row["position"])
            by_keyword[row["keyword"]].append(row)
    return by_keyword


def analyze(serps: dict[str, list[dict]], my_domain: str, competitors: list[str]) -> list[dict]:
    my_domain = my_domain.replace("www.", "")
    competitors = [c.replace("www.", "") for c in competitors]
    report = []

    for keyword, results in serps.items():
        my_pos = next((r["position"] for r in results if r["domain"] == my_domain), None)
        comp_hits = [r for r in results if r["domain"] in competitors]

        if my_pos is not None and my_pos <= 7:
            continue  # we rank fine — not a gap

        entry_type = "gap"
        if my_pos is not None:  # positions 8-10
            entry_type = "weak_win"

        if not comp_hits:
            continue  # nobody we track ranks — no signal either way

        ranked_domains = sorted({r["domain"] for r in comp_hits})
        avg_pos = sum(r["position"] for r in comp_hits) / len(comp_hits)
        score = round(len(ranked_domains) ** 1.5 * (11 - avg_pos) * 4)

        report.append({
            "keyword": keyword,
            "type": entry_type,
            "competitors_ranking": len(ranked_domains),
            "competitor_domains": ", ".join(ranked_domains),
            "avg_competitor_position": round(avg_pos, 1),
            "my_position": my_pos or "",
            "priority_score": score,
        })

    report.sort(key=lambda r: r["priority_score"], reverse=True)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="SERP CSV → prioritized content gaps")
    p.add_argument("--serps", help="serp_results.csv from serp_scraper.py")
    p.add_argument("--my-domain", default="yoursite.com")
    p.add_argument("--competitors", nargs="+",
                   default=["competitor1.com", "competitor2.com", "competitor3.com"])
    p.add_argument("--out", default=str(BASE_DIR / "data" / "content_gaps.csv"))
    p.add_argument("--demo", action="store_true", help="use bundled sample SERP data")
    args = p.parse_args()

    serp_path = Path(args.serps) if args.serps else SAMPLE
    if args.demo:
        serp_path = SAMPLE
        print("🧪 demo mode — bundled sample data (10 keywords × 10 results)")

    serps = load_serps(serp_path)
    report = analyze(serps, args.my_domain, args.competitors)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["keyword", "type", "competitors_ranking", "competitor_domains",
              "avg_competitor_position", "my_position", "priority_score"]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report)

    gaps = [r for r in report if r["type"] == "gap"]
    weak = [r for r in report if r["type"] == "weak_win"]
    print(f"\n✅ {len(gaps)} gaps + {len(weak)} weak wins from {len(serps)} keywords → {out}\n")
    print("Top 5:")
    for r in report[:5]:
        icon = "🔥" if r["priority_score"] >= 70 else "⚡" if r["priority_score"] >= 50 else "🌊"
        print(f"  {icon} [{r['priority_score']:>3}] {r['keyword']}"
              f"  ({r['competitors_ranking']} competitors, avg pos {r['avg_competitor_position']})")


if __name__ == "__main__":
    main()
