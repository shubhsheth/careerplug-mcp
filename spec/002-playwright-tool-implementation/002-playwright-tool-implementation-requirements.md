# Spec: Playwright-backed list_jobs and list_applicants

## Objective

Implement real data fetching for the two stub MCP tools by using Playwright to navigate `app.careerplug.com` and extract structured data from the rendered pages. The server connects to the user's existing Chrome browser (already authenticated) via CDP rather than managing its own browser session or credentials.

## User Stories

- As an LLM client, I want `list_jobs` to return real job data from CareerPlug so I can surface open roles.
- As an LLM client, I want `list_applicants` to return real applicant data, optionally filtered by job, so I can track hiring progress.
- As a developer, I want both tools to accept filter parameters that map directly to the CareerPlug URL query structure so the tool interface is predictable.

## Functional Requirements

- FR-1: `list_jobs` accepts `page: int = 1`, `status: int | None = None`, `refresh: bool = False`.
- FR-2: `list_jobs` builds the URL: `/manage/jobs?page={page}&refresh={1 if refresh else ""}&status={status or ""}` where status values are: `None`/`""` = all, `0` = draft, `1` = active, `2` = closed, `3` = passive.
- FR-3: `list_applicants` accepts `page: int = 1`, `status: str = "active"`, `job_id: int | None = None`.
- FR-4: `list_applicants` without `job_id` builds URL: `/manage/apps?page={page}&status={status}`. Valid status values: `new`, `in_process`, `active`, `disqualified`, `hired`, `pipeline`, `inactive`.
- FR-5: `list_applicants` with `job_id` builds URL: `/manage/apps?app_link=true&apps_hiring_pipeline_step=all&apps_j[]={job_id}&apps_job_status=all&page={page}`.
- FR-6: Both tools connect to the user's existing Chrome browser at `http://localhost:9222` via CDP.
- FR-7: Both tools open a new page in the existing browser context, navigate to the target URL, and wait for JS rendering to complete (`networkidle`) before extracting data.
- FR-8: Both tools return a list of dicts. The exact field names are determined during the DOM inspection step (see Out of Scope / Tasks).
- FR-9: The opened page is closed after extraction regardless of success or failure.

## Non-Functional Requirements

- NFR-1: No credentials are stored or passed in code — auth relies entirely on the existing browser session.
- NFR-2: Each tool call opens and closes exactly one page; it does not launch a new browser.
- NFR-3: Tools are `async` to avoid blocking the MCP server event loop.

## Out of Scope

- Auto-pagination (fetching all pages automatically) — callers request a specific page.
- DOM selector discovery — this requires running against the live page and is a prerequisite task before implementing extraction logic (see Tasks).
- Error handling for expired sessions or network failures beyond what Playwright raises naturally.
- Filtering applicants by hiring pipeline step (the `apps_hiring_pipeline_step` param is hardcoded to `all`).

## Assumptions

- Python 3.11+ and `uv` are available.
- `playwright` package and Chromium browser are already installed (`uv add playwright` + `playwright install chromium`).
- The user runs Chrome with `--remote-debugging-port=9222` and is logged into CareerPlug before calling either tool.
- A single browser context at index `[0]` is available on the CDP connection.

## Tech Stack

- Language: Python 3.11+
- MCP framework: FastMCP
- Browser automation: Playwright (async API)
- Package manager: uv

## Commands

```
Install deps:   uv add playwright
Install browser: uv run playwright install chromium
Run dev server: fastmcp dev src/server.py
Run stdio:      fastmcp run src/server.py
Syntax check:   uv run python -c "import src.server"
```

## Project Structure

```
src/
  server.py    → FastMCP server, tool definitions, CDP helper, extraction logic
spec/
  002-playwright-tool-implementation/
    002-playwright-tool-implementation-requirements.md
    002-playwright-tool-implementation-plan.md
```

## Code Style

```python
@mcp.tool
async def list_jobs(
    page: int = 1,
    status: int | None = None,
    refresh: bool = False,
) -> list:
    """List jobs from CareerPlug. status: None=all, 0=draft, 1=active, 2=closed, 3=passive."""
    ...
```

- All tool functions are `async`
- URL building is inline (no separate builder function unless shared logic grows)
- Extraction helpers are private module-level `async` functions prefixed with `_`
- Docstrings document valid parameter values since they become the tool description in MCP clients

## Testing Strategy

Manual verification against live CareerPlug data — no automated tests in this iteration.

Verification steps:
1. Start Chrome with `--remote-debugging-port=9222`, logged into CareerPlug
2. Run `fastmcp dev src/server.py`
3. Call `list_jobs()` — expect non-empty list of job dicts
4. Call `list_jobs(status=1)` — expect only active jobs
5. Call `list_applicants()` — expect active applicants
6. Call `list_applicants(job_id=<id>)` — expect applicants for that job
7. Call `list_applicants(status="new")` — expect only new applicants

## Boundaries

- **Always:** Close the Playwright page in a `finally` block; use `async` for all tool functions; validate that `status` values match documented options in docstrings.
- **Ask first:** Adding a new filter parameter; changing the CDP URL; switching to a non-CDP auth strategy.
- **Never:** Store credentials in code or config files; launch a new browser (only attach to existing); implement extraction logic before inspecting the live DOM.

## Success Criteria

- Both tools return a non-empty list of dicts when called against a live, authenticated CareerPlug session.
- The `status` filter visibly changes the results (e.g., `list_jobs(status=1)` returns only active jobs).
- The `job_id` filter returns only applicants for that job.
- The page closes cleanly after each call with no dangling browser pages.
