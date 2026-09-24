"""
Step 5: Botasaurus browser + ScrapeOps residential proxies

Uses Botasaurus with bypass_cloudflare=True and routes traffic through
the ScrapeOps Residential Proxy Aggregator.

Important:
  Do NOT use block_images_and_css=True while solving Turnstile.
  Blocking CSS collapses the widget (height=0), so Botasaurus cannot find
  or click the checkbox even when you can still see the challenge UI.

  After Cloudflare clears, we wait for DOM interactive (not full page load)
  and then for a content marker — that avoids the 60s "document ready" hang
  caused by slow assets over residential proxies.

Proxy resolution (first match wins):
  1. RESIDENTIAL_PROXY in .env
  2. Built from SCRAPEOPS_API_KEY →
     http://scrapeops:API_KEY@residential-proxy.scrapeops.io:8181

Usage:
  python 5_test_botasaurus_residential.py
  python 5_test_botasaurus_residential.py --target sportsdirect
  python 5_test_botasaurus_residential.py -t hepsiburada --headless
"""

import argparse

from botasaurus.browser import Driver, Wait, browser

from helpers import (
    get_scrapeops_residential_proxy,
    is_cloudflare_blocked,
    print_response_summary,
    resolve_target,
    save_html,
)

# First matching selector that means "real page content is here"
PAGE_READY_SELECTORS = {
    "fbref": ["#content", "h1", ".section_wrapper"],
    "sportsdirect": ["h1", "#productDetails", ".product-title"],
    "hepsiburada": ["h1", "[data-test-id='product-name']", "#ProductDescription"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Step 5: Botasaurus + ScrapeOps residential proxies"
    )
    parser.add_argument(
        "-t",
        "--target",
        default=None,
        help="Site to test: fbref | sportsdirect | hepsiburada | <full URL>",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless (often detected by Cloudflare)",
    )
    return parser.parse_args()


def wait_for_page_content(driver: Driver, target_key: str) -> None:
    selectors = PAGE_READY_SELECTORS.get(target_key, ["h1", "main", "body"])
    for selector in selectors:
        try:
            el = driver.wait_for_element(selector, wait=Wait.LONG)
            if el:
                print(f"  Page ready marker found: {selector}")
                return
        except Exception:
            continue
    print("  No page marker found — saving whatever HTML is present.")


def main() -> None:
    args = parse_args()
    target_key, target_url = resolve_target(args.target)
    proxy = get_scrapeops_residential_proxy()

    if not proxy:
        print("No residential proxy configured.")
        print("Set RESIDENTIAL_PROXY or SCRAPEOPS_API_KEY in your .env file.")
        return

    print(f"Target:   {target_key}")
    print(f"URL:      {target_url}")
    print(f"Headless: {args.headless}")
    print(f"Proxy:    {proxy.split('@')[-1]}")  # hide credentials
    print("Launching Botasaurus browser...")

    @browser(
        proxy=proxy,
        headless=args.headless,
        # Critical for post-CF hang: don't wait for every asset over residential
        wait_for_complete_page_load=False,
        # Images only — CSS must stay enabled so Turnstile has height/clickable
        block_images=True,
        close_on_crash=True,
        create_error_logs=False,
        output=None,
        max_retry=2,
    )
    def scrape_with_botasaurus(driver: Driver, data: dict) -> dict:
        url = data["url"]
        key = data["target_key"]

        print("  Solving Cloudflare (if present)...")
        # google_get uses Google as referrer, which helps CF trust the session
        driver.google_get(url, bypass_cloudflare=True)

        if driver.is_bot_detected_by_cloudflare():
            print("  Still on Cloudflare challenge page.")
        else:
            print("  Cloudflare cleared (or not present).")

        wait_for_page_content(driver, key)

        html = driver.page_html or ""
        return {
            "html": html,
            "title": driver.title or "",
            "still_blocked": is_cloudflare_blocked(html),
        }

    try:
        result = scrape_with_botasaurus(
            {"url": target_url, "target_key": target_key}
        )
    except Exception as exc:
        print(f"\nBotasaurus FAILED: {type(exc).__name__}: {exc}")
        return

    if not result:
        print("\nBotasaurus returned no result.")
        return

    html = result.get("html", "")
    status = 403 if (not html or result.get("still_blocked")) else 200
    print_response_summary("Botasaurus + residential", status, html)
    if result.get("title"):
        print(f"  Page title:    {result['title']}")
    save_html("5_botasaurus_residential.html", html, target_key)


if __name__ == "__main__":
    main()
