import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

TARGETS = {
    "fbref": "https://fbref.com/en/",
    "sportsdirect": (
        "https://www.sportsdirect.com/"
        "adidas-manchester-united-tiro-24-training-shorts-adults-463325"
        "#colcode=46332518"
    ),
    "hepsiburada": (
        "https://www.hepsiburada.com/"
        "adidas-tiro26-cocuk-pantolon-p-HBCV0000GL6KF2"
    ),
}

DEFAULT_TARGET = "fbref"

RESPONSES_DIR = Path(__file__).parent / "responses"
OUTPUT_DIR = Path(__file__).parent / "output"

CLOUDFLARE_MARKERS = (
    "Just a moment...",
    "cf-browser-verification",
    "challenge-platform",
    "Checking your browser",
    "Attention Required! | Cloudflare",
)


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_scrapeops_residential_proxy() -> str:
    """
    Prefer RESIDENTIAL_PROXY from .env; otherwise build the ScrapeOps
    residential proxy URL from SCRAPEOPS_API_KEY.
    """
    proxy = get_env("RESIDENTIAL_PROXY")
    if proxy:
        return proxy

    api_key = get_env("SCRAPEOPS_API_KEY")
    if not api_key:
        return ""

    return f"http://scrapeops.country=us:{api_key}@residential-proxy.scrapeops.io:8181"


def resolve_target(raw: str | None = None) -> tuple[str, str]:
    """
    Resolve a short name or full URL into (target_key, url).

    Priority: function arg > --target CLI flag > TARGET env > default (fbref).
    """
    value = (raw or "").strip()
    if not value:
        value = get_env("TARGET") or DEFAULT_TARGET

    key = value.lower()
    if key in TARGETS:
        return key, TARGETS[key]

    if value.startswith("http://") or value.startswith("https://"):
        host = urlparse(value).netloc.replace("www.", "").split(":")[0]
        short = host.split(".")[0] if host else "custom"
        return short, value

    known = ", ".join(TARGETS)
    raise ValueError(
        f"Unknown target '{value}'. Use one of: {known} — or pass a full URL."
    )


def parse_target_arg(description: str = "Cloudflare bypass demo script") -> tuple[str, str]:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-t",
        "--target",
        default=None,
        help=(
            "Site to test: fbref | sportsdirect | hepsiburada | <full URL>. "
            "Also settable via TARGET in .env"
        ),
    )
    args = parser.parse_args()
    return resolve_target(args.target)


def ensure_dirs(target_key: str | None = None) -> Path:
    RESPONSES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    if target_key:
        target_dir = RESPONSES_DIR / target_key
        target_dir.mkdir(exist_ok=True)
        return target_dir
    return RESPONSES_DIR


def is_cloudflare_blocked(html: str) -> bool:
    return any(marker in html for marker in CLOUDFLARE_MARKERS)


def print_response_summary(label: str, status_code: int, html: str) -> None:
    cf_blocked = is_cloudflare_blocked(html)
    if cf_blocked:
        protection = "Cloudflare BLOCKED"
    elif status_code in (401, 403, 429, 503):
        protection = f"BLOCKED (HTTP {status_code})"
    elif status_code == 200:
        protection = "OK"
    else:
        protection = f"HTTP {status_code}"

    print(f"\n{label}")
    print(f"  Status code:   {status_code}")
    print(f"  Content size:  {len(html):,} bytes")
    print(f"  Protection:    {protection}")


def save_html(filename: str, html: str, target_key: str | None = None) -> Path:
    folder = ensure_dirs(target_key)
    path = folder / filename
    path.write_text(html, encoding="utf-8")
    print(f"  Saved HTML to: {path}")
    return path
