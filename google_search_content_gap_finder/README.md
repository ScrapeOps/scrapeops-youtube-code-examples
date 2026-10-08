# Content Gap Finder — Demo Repo

Companion code for the ScrapeOps video **"Scraping Google Search — Build a Content Gap Finder"**.

Two ways to run the same pipeline:


| Path         | What                                                                      | Time               | Cost per run                                    |
| ------------ | ------------------------------------------------------------------------- | ------------------ | ----------------------------------------------- |
| 🤖 **Agent** | Claude (or any MCP client) + ScrapeOps MCP server — see `demo_prompts.md` | ~15-30 min         | Scraping + LLM tokens                           |
| 🐍 **Code**  | The Python pipeline in this repo (below)                                  | ~30 min setup once | ~$0.60 / 1k keywords - if on $29 proxy API plan |


---

## Quickstart (Python path)

```bash
pip install -r requirements.txt

# 1. Build your keyword universe (seeds × modifiers + competitor sitemaps)
python keyword_expander.py --seeds seeds.txt --out keywords.txt

# 2. Scrape Google SERPs for every keyword  →  data/serp_results.csv
export SCRAPEOPS_API_KEY="your-key"          # get one at scrapeops.io
python serp_scraper.py --keywords keywords.txt --out data/serp_results.csv

# 3. Find the gaps  →  data/content_gaps.csv
python gap_engine.py --serps data/serp_results.csv \
    --my-domain yoursite.com \
    --competitors zoho.com hubspot.com salesforce.com pipedrive.com \
    --out data/content_gaps.csv
```



### Demo mode (no API key, no network)

Every script runs offline against bundled fixtures — handy for rehearsals:

```bash
python serp_scraper.py --keyword "best crm for small business" --demo
python gap_engine.py --demo
```



## Config

Copy `config.example.json` → `config.json` and edit. CLI flags override config values.

```json
{
  "api_key": "env:SCRAPEOPS_API_KEY",
  "my_domain": "yoursite.com",
  "competitors": ["competitor1.com", "competitor2.com"],
  "geo": { "country": "us", "hl": "en", "gl": "us" },
  "max_retries": 3
}
```



## MCP path (agent version)

See `mcp_config.json` and `demo_prompts.md`. The agent does scraping, parsing,
comparison, and ranking conversationally — no code required.

## Files

```
├── serp_scraper.py       # Google SERP scraper (browser-rendered Proxy API)
├── keyword_expander.py   # seeds × intent modifiers + sitemap-slug extraction
├── gap_engine.py         # SERPs + your domain + competitors → prioritized gaps
├── demo_prompts.md       # the exact 4-prompt sequence for the MCP/agent demo
├── mcp_config.json       # MCP server registration for Claude Code/Desktop
├── config.example.json
├── seeds.txt             # example seed keywords
├── fixtures/
│   └── serp_demo.html    # realistic Google SERP markup for --demo mode
└── data/
    └── sample_serp_results.csv   # 10 keywords × 10 results, for --demo gap run
```

