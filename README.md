# careerplug-mcp

An MCP server for CareerPlug, built with [FastMCP](https://gofastmcp.com).

## Tools

| Tool | Parameters | Description |
|---|---|---|
| `list_jobs` | `page` (int), `status` (None/0/1/2/3), `refresh` (bool) | List jobs. status: None=all, 0=draft, 1=active, 2=closed, 3=passive. |
| `list_applicants` | `page` (int), `status` (str), `job_id` (int, optional) | List applicants. status: active/new/in_process/disqualified/hired/pipeline/inactive. Pass `job_id` to filter to a specific job. |
| `debug_cookie_search` | — | Diagnostic: shows which browsers were found and whether the session cookie exists in each. |

## Authentication

No configuration required. The server reads your existing browser session automatically.

**Before starting the server**, make sure you are logged into
[app.careerplug.com](https://app.careerplug.com) in Chrome, Firefox, Brave,
Edge, or Chromium.

- If the server reports a missing session cookie, log into CareerPlug in your
  browser and try again.
- If tools stop working after previously succeeding, your session has expired.
  Reload CareerPlug in your browser and restart the MCP server.

## Setup

Install `uv` if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install dependencies:

```bash
uv sync
```

## Running

**With an MCP client (stdio transport):**

```bash
uv run python src/server.py
```

**With the MCP inspector (browser UI for testing):**

```bash
uv run fastmcp dev inspector src/server.py
```

## Connecting to Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "careerplug": {
      "command": "uv",
      "args": ["run", "python", "/path/to/careerplug-mcp/src/server.py"]
    }
  }
}
```
