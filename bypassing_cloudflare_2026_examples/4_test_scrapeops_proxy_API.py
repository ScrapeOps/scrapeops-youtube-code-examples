"""
Step 4: ScrapeOps Proxy API with Cloudflare bypass

Set your API key in .env:
  SCRAPEOPS_API_KEY=your_key_here

Docs: https://scrapeops.io/docs/web-scraping-proxy-api-aggregator/advanced-functionality/anti-bot-bypass/

Usage:
  python 4_test_scrapeops_proxy_API.py -t fbref
  python 4_test_scrapeops_proxy_API.py -t sportsdirect
  python 4_test_scrapeops_proxy_API.py -t hepsiburada
"""

import requests

from helpers import get_env, parse_target_arg, print_response_summary, save_html

SCRAPEOPS_ENDPOINT = "https://proxy.scrapeops.io/v1/"
DEFAULT_BYPASS = "cloudflare_level_2"


def fetch_with_scrapeops(
    target_key: str,
    target_url: str,
    bypass: str | None = None,
) -> None:
    api_key = get_env("SCRAPEOPS_API_KEY")
    if not api_key:
        print("SCRAPEOPS_API_KEY is not set. Add it to your .env file.")
        return

    params = {
        "api_key": api_key,
        "url": target_url,
    }
    if bypass:
        params["bypass"] = bypass

    label = f"ScrapeOps ({bypass or 'default'})"
    print(f"\nRequesting {target_url} via {label}...")

    response = requests.get(
        SCRAPEOPS_ENDPOINT,
        params=params,
        timeout=120,
    )
    print_response_summary(label, response.status_code, response.text)

    suffix = bypass or "default"
    save_html(f"4_scrapeops_{suffix}.html", response.text, target_key)


def main() -> None:
    target_key, target_url = parse_target_arg("Step 4: ScrapeOps Proxy API")
    print(f"Target: {target_key}")

    # Try without bypass first — cheaper and useful for the demo narrative.
    fetch_with_scrapeops(target_key, target_url)

    # Cloudflare bypass — bump to level_3 if level_2 is not enough.
    fetch_with_scrapeops(target_key, target_url, bypass=DEFAULT_BYPASS)


if __name__ == "__main__":
    main()
