#!/usr/bin/env python3
"""
Google SERP HTML Parser

Robust parsing with fallback selectors for Google's constantly-changing markup.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass
class ParsedResult:
    """Structured organic search result."""
    position: int
    url: str
    title: str
    description: str
    domain: str


@dataclass
class ParsedSerp:
    """Complete parsed SERP."""
    keyword: str
    location: str
    organic_results: List[ParsedResult]
    total_results: Optional[int]
    features: dict


class GoogleSerpParser:
    """
    Parser for Google Search HTML with multiple selector strategies.
    
    Google frequently A/B tests their markup. This parser tries multiple
    selectors and falls back gracefully when structure changes.
    """
    
    # Primary selectors (most common current structure)
    ORGANIC_SELECTORS = [
        "div.g",                    # Standard organic container
        "div[data-hveid] div.g",    # With tracking ID
        "div.MjjYud",               # Alternative container
        "div.v7W49e",               # Another variant
    ]
    
    # Fallback selectors for different layouts
    FALLBACK_SELECTORS = [
        "div.rc",
        "div[data-async-context]",
        "div.kvH3mc",
    ]
    
    TITLE_SELECTORS = [
        "h3",
        "h3.LC20lb",
        "h3.DKV0Md",
    ]
    
    LINK_SELECTORS = [
        "a[href^='http']",
        "a[data-ved]",
    ]
    
    DESCRIPTION_SELECTORS = [
        "div.VwiC3b",
        "span.aCOpRe",
        "div[data-sncf]",
        "div.IsZvec",
    ]
    
    def __init__(self):
        self.soup: Optional[BeautifulSoup] = None
    
    def parse(self, html: str, keyword: str = "", location: str = "us") -> ParsedSerp:
        """
        Parse SERP HTML into structured data.
        
        Args:
            html: Raw HTML from Google Search
            keyword: The search keyword (for reference)
            location: Country code
            
        Returns:
            ParsedSerp with organic results and features
        """
        self.soup = BeautifulSoup(html, "html.parser")
        
        organic_results = self._extract_organic_results()
        total_results = self._extract_total_results()
        features = self._detect_serp_features()
        
        return ParsedSerp(
            keyword=keyword,
            location=location,
            organic_results=organic_results,
            total_results=total_results,
            features=features,
        )
    
    def _extract_organic_results(self) -> List[ParsedResult]:
        """Extract organic search results with fallback selectors."""
        results = []
        
        # Try primary selectors first
        containers = []
        for selector in self.ORGANIC_SELECTORS:
            containers = self.soup.select(selector)
            if containers:
                break
        
        # Fallback if no containers found
        if not containers:
            for selector in self.FALLBACK_SELECTORS:
                containers = self.soup.select(selector)
                if containers:
                    break
        
        for container in containers:
            result = self._parse_result_container(container, len(results) + 1)
            if result:
                results.append(result)
        
        return results
    
    def _parse_result_container(self, container, position: int) -> Optional[ParsedResult]:
        """Parse a single result container."""
        # Extract URL
        url = self._extract_url(container)
        if not url:
            return None
        
        # Skip non-organic results
        if self._is_ad(container) or self._is_serp_feature(container):
            return None
        
        # Extract title
        title = self._extract_text_by_selectors(container, self.TITLE_SELECTORS)
        
        # Extract description
        description = self._extract_text_by_selectors(container, self.DESCRIPTION_SELECTORS)
        
        # Extract domain
        domain = urlparse(url).netloc
        
        return ParsedResult(
            position=position,
            url=url,
            title=title or "",
            description=description or "",
            domain=domain,
        )
    
    def _extract_url(self, container) -> Optional[str]:
        """Extract URL from result container."""
        for selector in self.LINK_SELECTORS:
            link = container.select_one(selector)
            if link and link.get("href"):
                url = link["href"]
                # Skip Google internal links
                if url.startswith("http") and "google.com" not in url:
                    return url
        return None
    
    def _extract_text_by_selectors(self, container, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors to extract text."""
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None
    
    def _is_ad(self, container) -> bool:
        """Check if container is an ad."""
        # Look for ad indicators
        ad_indicators = container.select("[data-text-ad], [data-ad], .ads-ad")
        return len(ad_indicators) > 0
    
    def _is_serp_feature(self, container) -> bool:
        """Check if container is a SERP feature (not organic)."""
        # Featured snippets, knowledge panels, etc.
        feature_classes = ["kp-blk", "featured-snippet", "local-pack"]
        for cls in feature_classes:
            if container.select_one(f".{cls}"):
                return True
        return False
    
    def _extract_total_results(self) -> Optional[int]:
        """Extract total results count."""
        result_stats = self.soup.select_one("#result-stats")
        if result_stats:
            text = result_stats.get_text()
            # Extract number from "About X results"
            match = re.search(r"([\d,]+)", text.replace(",", ""))
            if match:
                return int(match.group(1))
        return None
    
    def _detect_serp_features(self) -> dict:
        """Detect SERP features present on the page."""
        features = {
            "has_featured_snippet": False,
            "has_local_pack": False,
            "has_knowledge_panel": False,
            "has_image_pack": False,
            "has_video_carousel": False,
            "num_ads_top": 0,
            "num_ads_bottom": 0,
        }
        
        # Featured snippet
        if self.soup.select_one("[data-featured-snippet], .kp-blk"):
            features["has_featured_snippet"] = True
        
        # Local pack
        if self.soup.select_one("[data-local-pack], .local-pack"):
            features["has_local_pack"] = True
        
        # Knowledge panel
        if self.soup.select_one(".kp-wholepage, [data-kp]"):
            features["has_knowledge_panel"] = True
        
        # Image pack
        if self.soup.select_one("[data-image-pack], .image-pack"):
            features["has_image_pack"] = True
        
        # Video carousel
        if self.soup.select_one("[data-video-carousel], .video-carousel"):
            features["has_video_carousel"] = True
        
        # Count ads
        ads = self.soup.select("[data-text-ad], .ads-ad")
        features["num_ads_top"] = len([a for a in ads if self._is_top_ad(a)])
        features["num_ads_bottom"] = len(ads) - features["num_ads_top"]
        
        return features
    
    def _is_top_ad(self, ad_element) -> bool:
        """Determine if ad is at top of page."""
        # Check parent containers for position hints
        parent = ad_element.parent
        while parent:
            if parent.get("id") == "tads":
                return True
            if parent.get("id") == "bottomads":
                return False
            parent = parent.parent
        return True  # Default to top


def find_domain_rank(parsed_serp: ParsedSerp, domain: str) -> Optional[int]:
    """
    Find the ranking position of a domain in parsed SERP.
    
    Args:
        parsed_serp: ParsedSerp object
        domain: Domain to find (e.g., "scrapeops.com")
        
    Returns:
        Position (1-indexed) or None if not found
    """
    for result in parsed_serp.organic_results:
        if domain in result.domain or domain in result.url:
            return result.position
    return None


# Example usage
if __name__ == "__main__":
    # Example: parse saved HTML file
    with open("sample_serp.html", "r") as f:
        html = f.read()
    
    parser = GoogleSerpParser()
    serp = parser.parse(html, keyword="proxy api", location="us")
    
    print(f"Keyword: {serp.keyword}")
    print(f"Total results: {serp.total_results:,}")
    print(f"\nTop 10 organic results:")
    
    for result in serp.organic_results[:10]:
        print(f"{result.position}. {result.domain}")
        print(f"   {result.title[:60]}...")
        print(f"   {result.url[:80]}...")
        print()
    
    # Check specific domain
    rank = find_domain_rank(serp, "scrapeops.com")
    if rank:
        print(f"scrapeops.com ranks at position {rank}")
    else:
        print("scrapeops.com not found in top results")
