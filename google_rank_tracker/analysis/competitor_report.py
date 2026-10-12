#!/usr/bin/env python3
"""
Competitor comparison report generator

Compare your rankings against competitors across multiple keywords.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT.parent / "production_code"))

from database import RankTrackerDB
from trend_analysis import TrendAnalyzer


class CompetitorReport:
    """Generate competitor comparison reports."""
    
    def __init__(self, db: RankTrackerDB):
        self.db = db
        self.analyzer = TrendAnalyzer(db)
    
    def generate(self, keywords: List[str], 
                 your_domain: str,
                 competitor_domains: List[str],
                 days: int = 30) -> Dict:
        """
        Generate competitor comparison report.
        
        Args:
            keywords: Keywords to analyze
            your_domain: Your domain
            competitor_domains: List of competitor domains
            days: Analysis period
            
        Returns:
            Comparison report dict
        """
        all_domains = [your_domain] + competitor_domains
        
        report = {
            "generated_at": date.today().isoformat(),
            "period_days": days,
            "your_domain": your_domain,
            "competitors": competitor_domains,
            "keywords_analyzed": len(keywords),
            "overall": {
                "you": {"wins": 0, "avg_position": 0, "top_3_count": 0},
                "competitors": {d: {"wins": 0, "avg_position": 0, "top_3_count": 0} 
                              for d in competitor_domains},
            },
            "keyword_breakdown": [],
        }
        
        your_positions = []
        competitor_positions = {d: [] for d in competitor_domains}
        
        for keyword in keywords:
            kw_data = {
                "keyword": keyword,
                "rankings": {},
                "winner": None,
                "your_advantage": None,
            }
            
            best_position = 999
            winner = None
            
            for domain in all_domains:
                history = self.analyzer._history_for_keyword_domain(keyword, domain, days)
                
                if history:
                    positions = [r.position for r in history if r.position]
                    
                    if positions:
                        current = positions[0]
                        avg = sum(positions) / len(positions)
                        
                        kw_data["rankings"][domain] = {
                            "current": current,
                            "average": round(avg, 1),
                            "best": min(positions),
                            "worst": max(positions),
                        }
                        
                        # Track for overall stats
                        if domain == your_domain:
                            your_positions.append(current)
                            if current <= 3:
                                report["overall"]["you"]["top_3_count"] += 1
                        else:
                            competitor_positions[domain].append(current)
                            if current <= 3:
                                report["overall"]["competitors"][domain]["top_3_count"] += 1
                        
                        # Determine winner
                        if current < best_position:
                            best_position = current
                            winner = domain
            
            kw_data["winner"] = winner
            
            if winner == your_domain:
                report["overall"]["you"]["wins"] += 1
                kw_data["your_advantage"] = True
            elif winner:
                report["overall"]["competitors"][winner]["wins"] += 1
                kw_data["your_advantage"] = False
            
            report["keyword_breakdown"].append(kw_data)
        
        # Calculate averages
        if your_positions:
            report["overall"]["you"]["avg_position"] = round(
                sum(your_positions) / len(your_positions), 1
            )
        
        for domain in competitor_domains:
            if competitor_positions[domain]:
                report["overall"]["competitors"][domain]["avg_position"] = round(
                    sum(competitor_positions[domain]) / len(competitor_positions[domain]), 1
                )
        
        return report
    
    def print_text_report(self, report: Dict):
        """Print human-readable text report."""
        print("\n" + "="*70)
        print("COMPETITOR RANKING REPORT")
        print("="*70)
        print(f"Period: {report['period_days']} days")
        print(f"Your domain: {report['your_domain']}")
        print(f"Competitors: {', '.join(report['competitors'])}")
        print(f"Keywords analyzed: {report['keywords_analyzed']}")
        
        print("\n" + "-"*70)
        print("OVERALL PERFORMANCE")
        print("-"*70)
        
        you = report["overall"]["you"]
        print(f"\n{report['your_domain']}:")
        print(f"  Wins: {you['wins']}")
        print(f"  Avg position: {you['avg_position']}")
        print(f"  Top 3 rankings: {you['top_3_count']}")
        
        for domain, stats in report["overall"]["competitors"].items():
            print(f"\n{domain}:")
            print(f"  Wins: {stats['wins']}")
            print(f"  Avg position: {stats['avg_position']}")
            print(f"  Top 3 rankings: {stats['top_3_count']}")
        
        print("\n" + "-"*70)
        print("KEYWORD BREAKDOWN")
        print("-"*70)
        
        for kw in report["keyword_breakdown"]:
            winner_marker = "🏆" if kw["winner"] == report["your_domain"] else "  "
            print(f"\n{winner_marker} {kw['keyword']}")
            print(f"   Winner: {kw['winner'] or 'N/A'}")
            
            for domain, data in kw["rankings"].items():
                marker = "→" if domain == report["your_domain"] else " "
                print(f"   {marker} {domain}: #{data['current']} "
                      f"(avg: {data['average']}, best: {data['best']})")


def main():
    parser = argparse.ArgumentParser(description="Competitor Comparison Report")
    parser.add_argument("--db", default="rank_tracker.db", help="Database path")
    parser.add_argument("--your-domain", required=True, help="Your domain")
    parser.add_argument("--competitors", nargs="+", required=True,
                       help="Competitor domains")
    parser.add_argument("--keywords", nargs="+", required=True,
                       help="Keywords to analyze")
    parser.add_argument("--days", type=int, default=30, help="Analysis period")
    parser.add_argument("--json", help="Output JSON file")
    
    args = parser.parse_args()
    
    db = RankTrackerDB(args.db)
    reporter = CompetitorReport(db)
    
    report = reporter.generate(
        keywords=args.keywords,
        your_domain=args.your_domain,
        competitor_domains=args.competitors,
        days=args.days,
    )
    
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {args.json}")
    else:
        reporter.print_text_report(report)


if __name__ == "__main__":
    main()
