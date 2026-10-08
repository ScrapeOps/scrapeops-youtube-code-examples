# Demo prompts — Content Gap Finder via ScrapeOps MCP

Setup (one time, ~60 seconds):

```bash
# Claude Code
claude mcp add scrapeops --env SCRAPEOPS_API_KEY=your-key -- npx -y @scrapeops/mcp-server

# Or paste mcp_config.json into Claude Desktop / Cursor MCP settings, then restart.
```

Then run this 4-prompt sequence in the agent chat. This is the exact flow from the video.

---

**Prompt 1 — single SERP (proves the tool works)**

> Scrape Google for "best crm for small business" and give me the top 10 organic results as a table: position, title, URL. Skip ads, featured snippets, AI overviews, and "People Also Ask". Organic positions 1–10 only. Use the ScrapeOps MCP, set the country=us, then extract the results from the HTML. 

**Prompt 2 — batch + save (the loop)**

> Now do the same for each of these keywords: 
crm
crm software
sales pipeline
customer management
contact management
best crm
crm pricing
crm alternatives
how to choose crm
crm for small business
crm for startups
crm vs spreadsheet
free crm
crm template
crm checklist
best crm software
crm software pricing
crm software alternatives
how to choose crm software
crm software for small business
crm software for startups
crm software vs spreadsheet
free crm software
crm software template
crm software checklist
best sales pipeline
sales pipeline pricing
sales pipeline alternatives
how to choose sales pipeline
sales pipeline for small business
sales pipeline for startups
sales pipeline vs spreadsheet
free sales pipeline
sales pipeline template
sales pipeline checklist
best customer management
customer management pricing
customer management alternatives
how to choose customer management
customer management for small business
customer management for startups
customer management vs spreadsheet
free customer management
customer management template
customer management checklist
best contact management
contact management pricing
contact management alternatives
how to choose contact management
contact management for small business
contact management for startups
contact management vs spreadsheet
free contact management
contact management template
contact management checklist

 Combine everything into one CSV at ./data/serp_results.csv with columns: keyword, position, title, url, domain. Be gentle — space the requests out, max 2 requests at a time.

**Prompt 3 — the gap analysis (no code, just reasoning)**

> Read ./data/serp_results.csv. My domain is onepagecrm.com. My competitors are zoho.com, hubspot.com, salesforce.com, pipedrive.com. Tell me which keywords at least one competitor ranks for in the top 10 where my domain does not appear at all. Also flag keywords where I rank positions 8–10 as "weak wins" instead of gaps.

**Prompt 4 — prioritize + export**

> Score each gap: more competitors ranking = higher score, and better average competitor position = higher score. Sort descending and write ./data/content_gaps.csv with columns: keyword, competitors_ranking, avg_competitor_position, priority_score, type (gap|weak_win). Show me the top 10.

---

### Gotchas specific to the agent path

- **Say the geo out loud.** Add "Use US proxies and google.com English results" (or your market) to prompt 1 — the agent won't infer your target market.
- **Chunk big keyword lists.** Agents get flaky past ~25 sequential tool calls in one prompt; split 1,000 keywords into batches, or use this path for discovery only and the Python pipeline for scale.
- **Verify the CSV.** Agents occasionally invent plausible-looking data. Spot-check 2–3 rows against a real Google search before trusting the report.
- **Key safety.** The API key lives in the MCP server config — don't paste it into the chat.
