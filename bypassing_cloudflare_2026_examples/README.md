# Bypassing Cloudflare in 2026 — code examples

Python examples from the ScrapeOps “Bypassing Cloudflare 2026” video. They walk through what fails on protected sites and what still works: a plain `requests` call, TLS impersonation with `curl_cffi`, datacenter vs residential proxies, the [ScrapeOps Proxy API](https://scrapeops.io/docs/web-scraping-proxy-api-aggregator/advanced-functionality/anti-bot-bypass/), a Botasaurus browser session, and parsing the resulting HTML.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your ScrapeOps API key to `.env` (get one at [scrapeops.io](https://scrapeops.io/app/register/main)):

```
SCRAPEOPS_API_KEY=your_key_here
```

Optional proxy URLs for steps 3 and 5:

```
DATACENTER_PROXY=http://user:pass@host:port
RESIDENTIAL_PROXY=http://scrapeops:YOUR_API_KEY@residential-proxy.scrapeops.io:8181
```

Default target is `fbref`. Override with `TARGET` in `.env` or `-t` / `--target` on the command line (`fbref`, `sportsdirect`, `hepsiburada`, or a full URL).

## Scripts

| Script | What it does |
| --- | --- |
| `1_test_python_request.py` | Baseline `requests` GET — usually a Cloudflare challenge |
| `2_test_curl_cffi.py` | Same request with Chrome TLS impersonation |
| `3_test_curl_cffi_with_DC_and_residential.py` | `curl_cffi` through datacenter and residential proxies |
| `4_test_scrapeops_proxy_API.py` | ScrapeOps Proxy API, then `bypass=cloudflare_level_2` |
| `5_test_botasaurus_residential.py` | Botasaurus + residential proxy (`--headless` optional) |
| `6_parse_html_response.py` | Parse saved HTML into JSON/CSV |

Example:

```bash
python 1_test_python_request.py -t fbref
python 4_test_scrapeops_proxy_API.py -t sportsdirect
python 5_test_botasaurus_residential.py -t hepsiburada
python 6_parse_html_response.py -t hepsiburada
```

HTML responses are written under `responses/<target>/`. Parsed output goes to `output/`. Those folders are gitignored so you do not commit live page dumps.
