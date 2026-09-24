"""
Step 2: Request with curl_cffi (browser TLS impersonation)

curl_cffi mimics a real browser's TLS fingerprint, which can bypass
some Cloudflare checks — but not sites with strict Bot Management.

Usage:
  python 2_test_curl_cffi.py -t fbref
  python 2_test_curl_cffi.py -t sportsdirect
  python 2_test_curl_cffi.py -t hepsiburada
"""

from curl_cffi import requests as curl_requests

from helpers import parse_target_arg, print_response_summary, save_html


def main() -> None:
    target_key, target_url = parse_target_arg("Step 2: curl_cffi")
    print(f"Target: {target_key}")
    print(f"Requesting {target_url} with curl_cffi (impersonate=chrome)...")

    try:
        response = curl_requests.get(
            target_url,
            impersonate="chrome",
            timeout=30,
        )
    except Exception as exc:
        print(f"\ncurl_cffi FAILED: {type(exc).__name__}: {exc}")
        return

    print_response_summary("curl_cffi", response.status_code, response.text)
    save_html("2_curl_cffi.html", response.text, target_key)


if __name__ == "__main__":
    main()
