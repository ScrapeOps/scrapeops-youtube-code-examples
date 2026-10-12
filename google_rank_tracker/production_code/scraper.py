#!/usr/bin/env python3
"""Fetch and parse Google search results through the ScrapeOps Proxy API."""

import argparse
import os
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

from parser import GoogleSerpParser, ParsedSerp, find_domain_rank


class GoogleSerpScraper:
    """Fetch Google HTML through ScrapeOps and parse the organic results."""
    
    BASE_URL = "https://www.google.com/search"
    SCRAPEOPS_PROXY_URL = "https://proxy.scrapeops.io/v1/"
    MAX_RETRIES = 3
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize scraper.
        
        Args:
            api_key: ScrapeOps API key. Defaults to SCRAPEOPS_API_KEY.
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("SCRAPEOPS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ScrapeOps API key required. Pass api_key or set SCRAPEOPS_API_KEY."
            )
        self.session = requests.Session()
        self.parser = GoogleSerpParser()
        
    def _build_url(self, keyword: str, location: str = "us", 
                   language: str = "en", page: int = 1) -> str:
        """Build Google search URL with localization parameters."""
        params = {
            "q": keyword,
            "gl": location,      # Country
            "hl": language,      # Language
            "start": (page - 1) * 10,
            "num": 10,
        }
        query_string = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{self.BASE_URL}?{query_string}"
    
    def fetch_serp(self, keyword: str, location: str = "us",
                   language: str = "en", page: int = 1) -> str:
        """Fetch raw Google SERP HTML through the ScrapeOps Proxy API."""
        url = self._build_url(keyword, location, language, page)
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    self.SCRAPEOPS_PROXY_URL,
                    params={
                        "api_key": self.api_key,
                        "url": url,
                    },
                    timeout=90,
                )
                response.raise_for_status()
                return response.text
            except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    time.sleep(attempt * 2)

        raise RuntimeError(
            f"ScrapeOps request failed after {self.MAX_RETRIES} attempts"
        ) from last_error
    
    def search(self, keyword: str, location: str = "us",
               language: str = "en", page: int = 1) -> ParsedSerp:
        """Fetch a Google SERP and parse it into structured results."""
        html = self.fetch_serp(keyword, location, language, page)
        parsed = self.parser.parse(
            html,
            keyword=keyword,
            location=location,
        )
        if not parsed.organic_results:
            raise RuntimeError(
                "ScrapeOps returned a page, but no organic Google results "
                "could be parsed."
            )
        return parsed


def main():
    parser = argparse.ArgumentParser(description="Google SERP Rank Tracker")
    parser.add_argument("--keywords", required=True, help="Comma-separated keywords")
    parser.add_argument("--domain", required=True, help="Target domain to track")
    parser.add_argument("--location", default="us", help="Country code (default: us)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument(
        "--api-key",
        help="ScrapeOps API key (defaults to SCRAPEOPS_API_KEY)",
    )
    
    args = parser.parse_args()
    
    scraper = GoogleSerpScraper(api_key=args.api_key)
    
    keywords = [k.strip() for k in args.keywords.split(",")]
    
    for keyword in keywords:
        print(f"\n{'='*60}")
        print(f"Keyword: {keyword}")
        print(f"{'='*60}")
        
        try:
            parsed = scraper.search(keyword, args.location, args.language)
            rank = find_domain_rank(parsed, args.domain)

            if rank is not None:
                result = next(
                    result
                    for result in parsed.organic_results
                    if result.position == rank
                )
                print(f"✓ Found at position {rank}: {result.url}")
            else:
                print(
                    f"✗ Not found in top "
                    f"{len(parsed.organic_results)} organic results"
                )
                
        except Exception as e:
            print(f"Error: {e}")
        
        # Rate limiting
        time.sleep(2)


if __name__ == "__main__":
    main()
