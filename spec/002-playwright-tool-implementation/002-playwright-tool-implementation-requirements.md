# Spec: Implement list_jobs and list_applicants with httpx

## Objective

Implement real data fetching for the two stub MCP tools by using httpx to call CareerPlug's internal list endpoints, which return server-rendered HTML table rows. Auth relies on the user's existing browser session (session cookie + CSRF token) — no credentials stored in code.

## User Stories

- As an LLM client, I want `list_jobs` to return real job data from CareerPlug so I can surface open roles.
- As an LLM client, I want `list_applicants` to return real applicant data, optionally filtered by job, so I can track hiring progress.
- As a developer, I want both tools to accept filter parameters that map directly to the CareerPlug URL query structure so the tool interface is predictable.

## Functional Requirements

- FR-1: `list_jobs` accepts `page: int = 1`, `status: int | None = None`, `refresh: bool = False`.
- FR-2: `list_jobs` calls `GET /manage/jobs/list` with params `page`, `refresh` (1 or ""), `status` (int or "").
- FR-3: `list_applicants` accepts `page: int = 1`, `status: str = "active"`, `job_id: int | None = None`.
- FR-4: `list_applicants` without `job_id` calls `GET /manage/apps/list` with params `page`, `status`. Valid status values: `new`, `in_process`, `active`, `disqualified`, `hired`, `pipeline`, `inactive`.
- FR-5: `list_applicants` with `job_id` calls `GET /manage/apps/list` with params `app_link=true`, `apps_hiring_pipeline_step=all`, `apps_j[]={job_id}`, `apps_job_status=all`, `page`.
- FR-6: Both tools authenticate using a `_career_plug_ats_session` cookie and `X-CSRF-Token` header provided by the user at startup (via env vars `CAREERPLUG_SESSION_COOKIE` and `CAREERPLUG_CSRF_TOKEN`).
- FR-7: Both tools parse the returned HTML table rows using BeautifulSoup and return a list of dicts.
- FR-8: `list_applicants` returns dicts with keys: `id`, `name`, `profile_url`, `job_title`, `job_url`, `current_step`, `location`.
- FR-9: `list_jobs` returns dicts with keys determined by inspecting the `/manage/jobs/list` HTML response (discovery step — see Tasks).
- FR-10: Both tools raise a clear error if the session cookie env var is not set.

## Non-Functional Requirements

- NFR-1: No credentials are stored or committed in code — auth values come from env vars.
- NFR-2: No browser is launched; all requests use httpx directly.
- NFR-3: Tools are `async` (use `httpx.AsyncClient`) to avoid blocking the MCP server event loop.
- NFR-4: A single `httpx.AsyncClient` is reused across calls (module-level client, constructed lazily).

## Known HTML Selectors (from live DOM inspection)

### `/manage/apps/list` response

Each applicant row: `tr.app.index-item[data-id]`

| Field | Selector |
|-------|----------|
| `id` | `tr[data-id]` attribute |
| `name` | `td.td_applicant a` text |
| `profile_url` | `td.td_applicant a` href |
| `job_title` | `td.td_applied-for a` text |
| `job_url` | `td.td_applied-for a` href |
| `location` | `td.td_applied-for span.subinfo` text |
| `current_step` | `td.td_current-step .text-margin` text |

### `/manage/jobs/list` response

Selectors to be discovered via `get_page_html` debug tool (see Tasks).

## Out of Scope

- Auto-pagination (callers request a specific page).
- Filtering applicants by hiring pipeline step (hardcoded to `all`).
- Error handling for expired sessions beyond what httpx raises naturally.
- Automatic CSRF token refresh.

## Assumptions

- Python 3.11+ and `uv` are available.
- `httpx` and `beautifulsoup4` packages will be added as dependencies.
- The user provides a valid `_career_plug_ats_session` cookie and CSRF token via env vars before starting the server.
- The `/manage/jobs/list` endpoint exists and returns a similar HTML table structure (to be confirmed during implementation).

## Tech Stack

- Language: Python 3.11+
- MCP framework: FastMCP
- HTTP client: httpx (async)
- HTML parsing: BeautifulSoup (bs4)
- Package manager: uv

## Commands

```
Install deps:   uv add httpx beautifulsoup4
Run dev server: fastmcp dev src/server.py
Run stdio:      fastmcp run src/server.py
Syntax check:   uv run python -c "import src.server"
```

## Project Structure

```
src/
  server.py    → FastMCP server, tool definitions, httpx client, extraction logic
spec/
  002-playwright-tool-implementation/
    002-playwright-tool-implementation-requirements.md
    002-playwright-tool-implementation-plan.md
```

## Code Style

```python
@mcp.tool
async def list_applicants(
    page: int = 1,
    status: str = "active",
    job_id: int | None = None,
) -> list:
    """List applicants. status: active|new|in_process|disqualified|hired|pipeline|inactive. job_id filters to a specific job."""
    ...
```

- All tool functions are `async`
- URL building is inline
- Extraction helpers are private module-level `async` functions prefixed with `_`
- Docstrings document valid parameter values

## Tasks (in order)

1. **Discover `/manage/jobs/list` selectors** — call `get_page_html("https://app.careerplug.com/manage/jobs/list?page=1")` and inspect the response to find row selectors and field mappings.
2. **Add httpx and bs4 deps** — `uv add httpx beautifulsoup4`
3. **Implement auth** — read env vars, build shared `httpx.AsyncClient` with session cookie and CSRF header.
4. **Implement `list_applicants`** — call `/manage/apps/list`, parse rows with known selectors.
5. **Implement `list_jobs`** — call `/manage/jobs/list`, parse rows with discovered selectors.
6. **Remove `get_page_html` debug tool** — no longer needed after selector discovery.

## Testing Strategy

Manual verification against live CareerPlug data.

Verification steps:
1. Set `CAREERPLUG_SESSION_COOKIE` and `CAREERPLUG_CSRF_TOKEN` env vars
2. Run `fastmcp dev src/server.py`
3. Call `list_jobs()` — expect non-empty list of job dicts
4. Call `list_jobs(status=1)` — expect only active jobs
5. Call `list_applicants()` — expect active applicants
6. Call `list_applicants(job_id=<id>)` — expect applicants for that job
7. Call `list_applicants(status="new")` — expect only new applicants

## Boundaries

- **Always:** Use env vars for auth; close httpx client on shutdown; use `async` for all tool functions.
- **Ask first:** Adding a new filter parameter; changing the base URL; switching auth strategy.
- **Never:** Store credentials in code or config files; launch a browser.

## Success Criteria

- Both tools return a non-empty list of dicts when called with valid env vars.
- The `status` filter visibly changes the results.
- The `job_id` filter returns only applicants for that job.
