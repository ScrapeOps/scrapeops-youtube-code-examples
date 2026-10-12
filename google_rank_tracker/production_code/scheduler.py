#!/usr/bin/env python3
"""
Daily scheduler for Google Rank Tracker

Run via cron for automated daily tracking.
"""

import argparse
import logging
import time
from datetime import date
from typing import List

from database import RankTrackerDB, Keyword
from scraper import GoogleSerpScraper
from parser import find_domain_rank

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("rank_tracker.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class RankTrackerScheduler:
    """Orchestrates daily rank tracking jobs."""
    
    def __init__(self, db_path: str = "rank_tracker.db",
                 api_key: str = None,
                 delay_between_requests: float = 2.0):
        """
        Initialize scheduler.
        
        Args:
            db_path: Path to SQLite database
            api_key: ScrapeOps API key
            delay_between_requests: Seconds to wait between requests
        """
        self.db = RankTrackerDB(db_path)
        self.api_key = api_key
        self.delay = delay_between_requests
        
        self.scraper = GoogleSerpScraper(api_key=api_key)
    
    def run_daily_check(self, keywords: List[Keyword] = None):
        """
        Run daily ranking check for all keywords.
        
        Args:
            keywords: Specific keywords to check (default: all)
        """
        if keywords is None:
            keywords = self.db.get_keywords()
        
        logger.info(f"Starting daily check for {len(keywords)} keywords")
        
        today = date.today()
        results = {
            "success": 0,
            "failed": 0,
            "not_found": 0,
        }
        
        for kw in keywords:
            try:
                position, url, title, features = self._check_keyword(kw)
                
                self.db.save_ranking(
                    keyword_id=kw.id,
                    position=position,
                    url=url,
                    title=title,
                    ranking_date=today,
                    serp_features=features,
                )
                
                if position:
                    logger.info(f"✓ '{kw.keyword}' → position {position}")
                    results["success"] += 1
                else:
                    logger.warning(f"✗ '{kw.keyword}' → not in top 100")
                    results["not_found"] += 1
                    
            except Exception as e:
                logger.error(f"✗ '{kw.keyword}' → error: {e}")
                results["failed"] += 1
            
            # Rate limiting
            time.sleep(self.delay)
        
        logger.info(f"Daily check complete: {results}")
        return results
    
    def _check_keyword(self, keyword: Keyword):
        """
        Check ranking for a single keyword.
        
        Returns:
            Tuple of (position, url, title, serp_features)
        """
        domain = self._extract_domain(keyword.target_url)
        
        parsed = self.scraper.search(
            keyword.keyword,
            keyword.location,
            keyword.language,
        )
        position = find_domain_rank(parsed, domain)
        
        # Find the actual result for URL/title
        url, title = None, None
        if position:
            for result in parsed.organic_results:
                if result.position == position:
                    url, title = result.url, result.title
                    break
        
        return position, url, title, parsed.features
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from a URL or bare hostname."""
        from urllib.parse import urlparse

        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc.replace("www.", "")
    
    def generate_report(self, days: int = 30) -> dict:
        """Generate summary report of ranking performance."""
        keywords = self.db.get_keywords()
        
        report = {
            "period_days": days,
            "total_keywords": len(keywords),
            "keywords": [],
        }
        
        for kw in keywords:
            history = self.db.get_ranking_history(kw.id, days)
            
            if not history:
                continue
            
            positions = [r.position for r in history if r.position]
            
            kw_report = {
                "keyword": kw.keyword,
                "target_url": kw.target_url,
                "current_position": history[0].position if history else None,
                "best_position": min(positions) if positions else None,
                "worst_position": max(positions) if positions else None,
                "avg_position": sum(positions) / len(positions) if positions else None,
                "days_tracked": len(history),
                "days_in_top_10": sum(1 for p in positions if p and p <= 10),
                "days_in_top_3": sum(1 for p in positions if p and p <= 3),
            }
            
            report["keywords"].append(kw_report)
        
        return report


def main():
    parser = argparse.ArgumentParser(description="Google Rank Tracker Scheduler")
    parser.add_argument("--db", default="rank_tracker.db", help="Database path")
    parser.add_argument(
        "--api-key",
        help="ScrapeOps API key (defaults to SCRAPEOPS_API_KEY)",
    )
    parser.add_argument("--delay", type=float, default=2.0,
                       help="Delay between requests (seconds)")
    parser.add_argument("--report", action="store_true",
                       help="Generate report instead of running checks")
    parser.add_argument("--days", type=int, default=30,
                       help="Days for report (default: 30)")
    
    args = parser.parse_args()
    
    scheduler = RankTrackerScheduler(
        db_path=args.db,
        api_key=args.api_key,
        delay_between_requests=args.delay,
    )
    
    if args.report:
        import json
        report = scheduler.generate_report(days=args.days)
        print(json.dumps(report, indent=2, default=str))
    else:
        scheduler.run_daily_check()


if __name__ == "__main__":
    main()
