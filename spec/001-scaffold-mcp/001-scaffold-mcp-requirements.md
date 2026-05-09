# Spec: Scaffold CareerPlug MCP Server

## Objective

Scaffold a FastMCP-based MCP server for CareerPlug with two stub tools: `list_jobs` and `list_applicants`. The goal is a runnable server skeleton that can be extended with real API logic later.

## User Stories

- As a developer, I want a working FastMCP server so I can connect it to an LLM client and test tool discovery.
- As a developer, I want `list_jobs` and `list_applicants` tools registered so that LLM clients can call them and receive placeholder responses.

## Functional Requirements

- FR-1: The project uses `uv` for dependency management with a `pyproject.toml`.
- FR-2: FastMCP is declared as a dependency.
- FR-3: A server entry point exists at `src/careerplug_mcp/server.py`.
- FR-4: `list_jobs` tool is registered on the server and returns an empty list.
- FR-5: `list_applicants` tool is registered on the server and returns an empty list.
- FR-6: The server can be started via `fastmcp run src/careerplug_mcp/server.py` or `uv run src/careerplug_mcp/server.py`.

## Non-Functional Requirements

- NFR-1: No external API calls at this stage — tools are pure stubs.
- NFR-2: Code follows standard Python conventions (PEP 8, type hints).

## Out of Scope

- Real CareerPlug API integration
- Authentication / API key handling
- Input parameters on either tool
- Testing infrastructure (deferred to next iteration)

## Assumptions

- Python 3.11+ is available
- `uv` is available in the environment
- MCP server name is `careerplug`

## Tech Stack

- Language: Python 3.11+
- MCP framework: FastMCP (latest via `uv add fastmcp`)
- Package manager: uv

## Commands

```
Install: uv add fastmcp
Run (stdio): fastmcp run src/careerplug_mcp/server.py
Run (dev/inspector): fastmcp dev src/careerplug_mcp/server.py
```

## Project Structure

```
pyproject.toml               → uv project config + dependencies
src/
  careerplug_mcp/
    __init__.py              → package marker
    server.py                → FastMCP server definition + tool registrations
```

## Code Style

```python
import fastmcp

mcp = fastmcp.FastMCP("careerplug")

@mcp.tool
def list_jobs() -> list:
    """List all open jobs."""
    return []

@mcp.tool
def list_applicants() -> list:
    """List all applicants."""
    return []

if __name__ == "__main__":
    mcp.run()
```

- Function names: `snake_case`
- Docstrings: one-line, present tense
- Type hints on all tool return values

## Testing Strategy

Deferred — no tests in this scaffold iteration.

## Boundaries

- **Always:** Use type hints on tool functions; include docstrings (they become tool descriptions in MCP clients)
- **Ask first:** Adding dependencies beyond fastmcp; changing the package name
- **Never:** Make real HTTP calls from stub tools; commit secrets

## Success Criteria

- `uv run src/careerplug_mcp/server.py` starts without errors
- `fastmcp dev src/careerplug_mcp/server.py` launches the MCP inspector and shows both `list_jobs` and `list_applicants` in the tool list
- Both tools return an empty list when invoked
