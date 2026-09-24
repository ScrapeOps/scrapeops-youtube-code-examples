"""
Step 1: Basic Python request

Expected result on protected sites: 403 with Cloudflare challenge page.

Usage:
  python 1_test_python_request.py -t fbref
  python 1_test_python_request.py -t sportsdirect
  python 1_test_python_request.py -t hepsiburada
"""

import requests

from helpers import parse_target_arg, print_response_summary, save_html

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def main() -> None:
    target_key, target_url = parse_target_arg("Step 1: basic requests")
    print(f"Target: {target_key}")
    print(f"Requesting {target_url} with the requests library...")

    try:
        response = requests.get(target_url, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"\nrequests FAILED: {type(exc).__name__}: {exc}")
        return

    print_response_summary("requests", response.status_code, response.text)
    save_html("1_python_requests.html", response.text, target_key)


if __name__ == "__main__":
    main()
