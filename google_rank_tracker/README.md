# Google Rank Tracking Demo Repo

Two approaches to track Google keyword rankings:

1. **LLM-First (ScrapeOps MCP)** — Ask questions in plain English, get answers instantly
2. **Production Code** — Automated daily tracking with historical data

## Quick Start

### Option A: MCP Demo (2 minutes)

See `mcp_demo/setup.md` to configure the ScrapeOps MCP server in your LLM client.

Then try the prompts in `mcp_demo/example_prompts.md`.

### Option B: Production Code (10 minutes)

```bash
cd production_code
pip install -r requirements.txt
cp .env.example .env
# Add your ScrapeOps API key to .env
python scraper.py --keywords "web scraping api,proxy api" --domain scrapeops.io
python scheduler.py  # Run daily tracking against keywords already in the DB
```

The production scraper sends the Google Search URL directly to the ScrapeOps
Proxy API using `requests`, then parses the returned HTML with `parser.py`.
`SCRAPEOPS_API_KEY` is loaded from `production_code/.env`; it can also be
provided with `--api-key`.

Seed keywords into the SQLite DB before running the scheduler:

```bash
cd production_code
python - <<'PY'
from database import RankTrackerDB
db = RankTrackerDB("rank_tracker.db")
db.add_keyword("proxy api", "https://scrapeops.io/")
db.add_keyword("web scraping api", "https://scrapeops.io/")
print(db.get_keywords())
PY

python scheduler.py --db rank_tracker.db
python scheduler.py --db rank_tracker.db --report
```

## Analysis Scripts

After you have ranking history in `production_code/rank_tracker.db`, use the
scripts in `analysis/` to inspect trends and competitors.

```bash
cd analysis

# Full trend report (JSON to stdout)
python trend_analysis.py --db ../production_code/rank_tracker.db --days 30

# Save report to a file
python trend_analysis.py --db ../production_code/rank_tracker.db --days 30 --output trend_report.json

# Single keyword (prints every tracked domain for that keyword)
python trend_analysis.py --db ../production_code/rank_tracker.db --keyword "proxy api"

# Compare domains across tracked keywords
python trend_analysis.py --db ../production_code/rank_tracker.db \
  --compare scrapeops.io brightdata.com oxylabs.io

# Competitor report (human-readable)
python competitor_report.py \
  --db ../production_code/rank_tracker.db \
  --your-domain scrapeops.io \
  --competitors brightdata.com oxylabs.io \
  --keywords "proxy api" "web scraping api" "serp api" \
  --days 30

# Competitor report as JSON
python competitor_report.py \
  --db ../production_code/rank_tracker.db \
  --your-domain scrapeops.io \
  --competitors brightdata.com oxylabs.io \
  --keywords "proxy api" "web scraping api" "serp api" \
  --json competitor_report.json
```

Domain args accept bare hostnames (`scrapeops.io`) or full URLs
(`https://scrapeops.io/`); they are matched against `target_url` values in the DB.

## Notebooks

Ad-hoc exploration lives in `notebooks/exploration.ipynb`.

```bash
# From the repo root
pip install jupyter
cd notebooks
jupyter notebook exploration.ipynb
# or: jupyter lab exploration.ipynb
```

The notebook expects ranking data at `../production_code/rank_tracker.db`.
It can:

- list tracked keywords
- show 30-day trends per keyword/domain
- bucket position distribution
- surface significant 7-day position changes
- export history to `ranking_export.json`

## Repo Structure

```
├── mcp_demo/              # LLM/MCP approach
│   ├── setup.md           # MCP configuration guide
│   ├── example_prompts.md # Ready-to-use prompts
│   └── claude_desktop_config.json
├── production_code/       # Python pipeline
│   ├── scraper.py         # Core SERP scraper (ScrapeOps Proxy API)
│   ├── parser.py          # HTML parsing with fallbacks
│   ├── database.py        # SQLite storage
│   ├── scheduler.py       # Daily job runner
│   ├── alerts.py          # Email/Slack alerts
│   └── requirements.txt
├── analysis/              # Historical analysis
│   ├── trend_analysis.py
│   └── competitor_report.py
└── notebooks/             # Ad-hoc exploration
    └── exploration.ipynb
```

## Which Approach?

| Factor | LLM + MCP | Production Code |
|--------|-----------|-----------------|
| Setup time | 2 minutes | 2-4 hours |
| Best for | Ad-hoc questions | Daily tracking |
| Scale | 10s of queries | 1000s of keywords |
| Cost per query | ~$0.01-0.10 | ~$0.0001-0.001 |
| Historical data | No | Yes |
| Automation | No | Yes |

**Recommendation:** Use MCP for discovery and insight, code for routine and scale.
