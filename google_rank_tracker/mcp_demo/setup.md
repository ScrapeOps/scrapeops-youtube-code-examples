# ScrapeOps MCP Server Setup

## What is MCP?

Model Context Protocol (MCP) is the standard for connecting LLMs to external tools. The ScrapeOps MCP server exposes Google Search scraping as a tool that any MCP-compatible LLM can call.

## Supported Clients

- Claude Desktop
- Cursor
- Windsurf
- Any MCP-compatible client

## Setup Steps

### 1. Get Your ScrapeOps API Key

Sign up at [scrapeops.io](https://scrapeops.io) and grab your API key from the dashboard.

### 2. Configure Your LLM Client

#### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scrapeops": {
      "command": "npx",
      "args": ["-y", "@scrapeops/mcp-server"],
      "env": {
        "SCRAPEOPS_API_KEY": "your-api-key-here"
      }
    }
  }
}
```


#### Cursor

Add to your MCP settings in Cursor preferences.


#### TO NOTE!!

You might need to manually set your node version like we have in the example below:

```json 
{
  "mcpServers": {
    "scrapeops": {
      "command": "/path/to/npx",
      "args": ["-y", "@scrapeops/mcp"],
      "env": {
        "SCRAPEOPS_API_KEY": "your-api-key-here",
        "PATH": "/path/to/node/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```


### 3. Restart Your Client

The `scrape_google_search` tool should now be available.

## Verify It Works

Ask your LLM:

> "Use the scrapeops MCP tool to check where scrapeops.com ranks for 'proxy api' in the US in google search results"

The LLM should call the tool and return structured ranking data.


## Cost

Each MCP call consumes ScrapeOps API credits. Check your dashboard for usage.

## Next Steps

See `example_prompts.md` for ready-to-use ranking queries.
