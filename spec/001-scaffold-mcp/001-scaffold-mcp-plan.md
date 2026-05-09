# Plan: Scaffold CareerPlug MCP Server

## Implementation Order

1. Initialize uv project (`pyproject.toml`) with fastmcp dependency
2. Create `src/careerplug_mcp/__init__.py` (package marker)
3. Create `src/careerplug_mcp/server.py` with `list_jobs` and `list_applicants` tools

## Tasks

- [ ] Task: Initialize uv project and add fastmcp dependency
  - Acceptance: `pyproject.toml` exists with fastmcp in dependencies; `uv.lock` generated
  - Verify: `uv run python -c "import fastmcp"` exits 0
  - Files: `pyproject.toml`, `uv.lock`

- [ ] Task: Create server entry point with two stub tools
  - Acceptance: `src/careerplug_mcp/server.py` defines a FastMCP server named `careerplug` with `list_jobs` and `list_applicants` tools; both return `[]`
  - Verify: `uv run python src/careerplug_mcp/server.py` starts without errors
  - Files: `src/careerplug_mcp/__init__.py`, `src/careerplug_mcp/server.py`
