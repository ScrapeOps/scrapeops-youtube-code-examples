"""
Step 3: curl_cffi with datacenter and residential proxies

Set proxy URLs in your .env file:
  DATACENTER_PROXY=http://user:pass@host:port
  RESIDENTIAL_PROXY=http://user:pass@host:port

Usage:
  python 3_test_curl_cffi_with_DC_and_residential.py -t fbref
  python 3_test_curl_cffi_with_DC_and_residential.py -t sportsdirect
  python 3_test_curl_cffi_with_DC_and_residential.py -t hepsiburada
"""

from curl_cffi import requests as curl_requests

from helpers import get_env, parse_target_arg, print_response_summary, save_html


def fetch_with_proxy(
    target_key: str,
    target_url: str,
    label: str,
    proxy_url: str,
    output_file: str,
) -> None:
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    print(f"\nRequesting {target_url} with curl_cffi + {label} proxy...")

    try:
        response = curl_requests.get(
            target_url,
            impersonate="chrome",
            proxies=proxies,
            timeout=60,
        )
    except Exception as exc:
        print(f"\n{label} FAILED: {type(exc).__name__}: {exc}")
        return

    print_response_summary(label, response.status_code, response.text)
    save_html(output_file, response.text, target_key)


def main() -> None:
    target_key, target_url = parse_target_arg("Step 3: curl_cffi + proxies")
    print(f"Target: {target_key}")

    datacenter_proxy = get_env("DATACENTER_PROXY")
    residential_proxy = get_env("RESIDENTIAL_PROXY")

    if not datacenter_proxy and not residential_proxy:
        print("No proxy URLs configured.")
        print("Add DATACENTER_PROXY and/or RESIDENTIAL_PROXY to your .env file.")
        return

    if datacenter_proxy:
        fetch_with_proxy(
            target_key,
            target_url,
            "datacenter",
            datacenter_proxy,
            "3_curl_cffi_datacenter.html",
        )

    if residential_proxy:
        fetch_with_proxy(
            target_key,
            target_url,
            "residential",
            residential_proxy,
            "3_curl_cffi_residential.html",
        )


if __name__ == "__main__":
    main()
