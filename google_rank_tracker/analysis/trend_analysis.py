#!/usr/bin/env python3
"""
Historical trend analysis for Google Rank Tracker

Generate reports and visualizations from ranking history.
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "production_code"))

from database import RankTrackerDB


class TrendAnalyzer:
    """Analyze ranking trends over time."""
    
    def __init__(self, db: RankTrackerDB):
        self.db = db
    
    def get_keyword_trend(self, keyword_id: int, days: int = 30) -> Dict:
        """Get trend data for a single keyword."""
        history = self.db.get_ranking_history(keyword_id, days)
        
        if not history:
            return {"error": "No data"}
        
        positions = [r.position for r in history if r.position]
        dates = [r.date.isoformat() for r in history]
        
        return {
            "keyword_id": keyword_id,
            "dates": dates,
            "positions": positions,
            "current": positions[0] if positions else None,
            "best": min(positions) if positions else None,
            "worst": max(positions) if positions else None,
            "average": sum(positions) / len(positions) if positions else None,
            "volatility": self._calculate_volatility(positions),
            "trend": self._calculate_trend(positions),
        }
    
    def get_competitor_comparison(self, keywords: List[str], 
                                  domains: List[str],
                                  days: int = 30) -> Dict:
        """Compare multiple domains across keywords."""
        comparison = {
            "period_days": days,
            "keywords": {},
        }
        
        for keyword in keywords:
            kw_data = {
                "domains": {},
                "leader": None,
                "biggest_mover": None,
            }
            
            for domain in domains:
                history = self._history_for_keyword_domain(keyword, domain, days)
                
                if history:
                    positions = [r.position for r in history if r.position]
                    kw_data["domains"][domain] = {
                        "current": positions[0] if positions else None,
                        "average": sum(positions) / len(positions) if positions else None,
                        "trend": self._calculate_trend(positions),
                    }
            
            # Determine leader
            if kw_data["domains"]:
                leader = min(
                    kw_data["domains"].items(),
                    key=lambda x: x[1]["average"] or 999
                )
                kw_data["leader"] = leader[0]
            
            comparison["keywords"][keyword] = kw_data
        
        return comparison

    def _history_for_keyword_domain(self, keyword: str, domain: str, days: int):
        """Find ranking history for a keyword/domain pair without creating junk rows."""
        domain_key = domain.lower().replace("https://", "").replace("http://", "").rstrip("/")
        domain_key = domain_key.replace("www.", "")

        matches = [
            kw for kw in self.db.get_keywords()
            if kw.keyword == keyword and domain_key in kw.target_url.lower()
        ]
        if not matches:
            return []

        # Prefer rows that already have ranking history, then fuller URLs
        matches.sort(
            key=lambda kw: (
                len(self.db.get_ranking_history(kw.id, days)) == 0,
                len(kw.target_url),
            )
        )
        return self.db.get_ranking_history(matches[0].id, days)
    
    def get_visibility_score(self, keyword_ids: List[int], 
                             days: int = 30) -> Dict:
        """
        Calculate visibility score (weighted by position).
        
        Position 1 = 100 points, position 10 = 10 points, position 20+ = 0
        """
        scores = {}
        
        for kw_id in keyword_ids:
            history = self.db.get_ranking_history(kw_id, days)
            
            if not history:
                continue
            
            daily_scores = []
            for record in history:
                if record.position and record.position <= 20:
                    score = max(0, 100 - (record.position - 1) * 10)
                else:
                    score = 0
                daily_scores.append(score)
            
            scores[kw_id] = {
                "current_score": daily_scores[0] if daily_scores else 0,
                "average_score": sum(daily_scores) / len(daily_scores) if daily_scores else 0,
                "trend": self._calculate_trend(daily_scores),
            }
        
        # Aggregate
        all_currents = [s["current_score"] for s in scores.values()]
        all_averages = [s["average_score"] for s in scores.values()]
        
        return {
            "overall_visibility": sum(all_currents) / len(all_currents) if all_currents else 0,
            "average_visibility": sum(all_averages) / len(all_averages) if all_averages else 0,
            "keyword_scores": scores,
        }
    
    def _calculate_volatility(self, positions: List[int]) -> float:
        """Calculate ranking volatility (standard deviation)."""
        if len(positions) < 2:
            return 0.0
        
        mean = sum(positions) / len(positions)
        variance = sum((p - mean) ** 2 for p in positions) / len(positions)
        return variance ** 0.5
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction.

        Ranking history is newest-first. Convert to chronological order so a
        falling position number (e.g. 8 → 4) is reported as improving.
        """
        if len(values) < 2:
            return "stable"

        chronological = list(reversed(values))

        # Simple linear regression slope
        n = len(chronological)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(chronological) / n
        
        numerator = sum((x[i] - x_mean) * (chronological[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # For rankings, negative slope = improving (lower position numbers)
        if slope < -0.5:
            return "improving"
        elif slope > 0.5:
            return "declining"
        else:
            return "stable"
    
    def generate_report(self, days: int = 30) -> Dict:
        """Generate comprehensive trend report."""
        keywords = self.db.get_keywords()
        
        report = {
            "generated_at": date.today().isoformat(),
            "period_days": days,
            "summary": {
                "total_keywords": len(keywords),
                "improving": 0,
                "declining": 0,
                "stable": 0,
            },
            "keywords": [],
        }
        
        for kw in keywords:
            trend = self.get_keyword_trend(kw.id, days)
            
            if "error" in trend:
                continue
            
            report["keywords"].append({
                "keyword": kw.keyword,
                "target_url": kw.target_url,
                **trend,
            })
            
            # Update summary
            trend_dir = trend.get("trend", "stable")
            report["summary"][trend_dir] = report["summary"].get(trend_dir, 0) + 1
        
        return report


def main():
    parser = argparse.ArgumentParser(description="Ranking Trend Analysis")
    parser.add_argument("--db", default="rank_tracker.db", help="Database path")
    parser.add_argument("--days", type=int, default=30, help="Analysis period")
    parser.add_argument("--keyword", help="Specific keyword to analyze")
    parser.add_argument("--compare", nargs="+", help="Domains to compare")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    db = RankTrackerDB(args.db)
    analyzer = TrendAnalyzer(db)
    
    if args.keyword:
        # Single keyword analysis
        keywords = db.get_keywords()
        matches = [k for k in keywords if k.keyword == args.keyword]

        if not matches:
            print(f"Keyword '{args.keyword}' not found")
        else:
            for kw in matches:
                trend = analyzer.get_keyword_trend(kw.id, args.days)
                print(json.dumps({"keyword": kw.keyword, "target_url": kw.target_url, **trend}, indent=2))
    
    elif args.compare:
        # Competitor comparison
        keywords = db.get_keywords()
        kw_list = list(dict.fromkeys(k.keyword for k in keywords))
        
        comparison = analyzer.get_competitor_comparison(
            kw_list[:5],  # Limit to 5 keywords
            args.compare,
            args.days
        )
        print(json.dumps(comparison, indent=2))
    
    else:
        # Full report
        report = analyzer.generate_report(args.days)
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
