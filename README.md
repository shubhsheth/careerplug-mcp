# careerplug-mcp

An MCP server for CareerPlug, built with [FastMCP](https://gofastmcp.com).

## Tools

| Tool | Description |
|---|---|
| `list_jobs` | List all open jobs |
| `list_applicants` | List all applicants |

## Setup

```bash
uv sync
```

## Running

**With an MCP client (stdio transport):**

```bash
uv run python src/careerplug_mcp/server.py
```

**With the MCP inspector (browser UI for testing):**

```bash
fastmcp dev src/careerplug_mcp/server.py
```

## Connecting to Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "careerplug": {
      "command": "uv",
      "args": ["run", "python", "/path/to/careerplug-mcp/src/careerplug_mcp/server.py"]
    }
  }
}
```
