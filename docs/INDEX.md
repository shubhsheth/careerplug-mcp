# careerplug-mcp — Architecture & Developer Guide

Read this file before making changes. It documents the key decisions that aren't
obvious from reading the code.

---

## Architecture Overview

This is a FastMCP server that wraps CareerPlug's internal HTML-rendering
endpoints. It is a scraper, not an API client — CareerPlug has no documented
public API. The endpoints it targets are:

- `/manage/jobs/list` — server-rendered HTML table of job listings
- `/manage/apps/list` — server-rendered HTML table of applicants
- `/manage/apps/{id}` — full applicant profile page (overview tab); fetched by `get_applicant_details`
- `/manage/apps/{id}?tab=documents` — applicant documents tab; also fetched by `get_applicant_details` in parallel

### Module Structure

| Module | Responsibility |
|---|---|
| `src/client.py` | Browser cookie auth, CSRF bootstrap, HTTP client singleton, `fetch_html` |
| `src/parsers.py` | BeautifulSoup HTML extraction for jobs and applicants |
| `src/server.py` | FastMCP server init, tool definitions, entry point |

---

## Authentication Model

No credentials are stored anywhere (no env vars, no config files).

On the first tool call:

1. `_find_session_cookie()` reads the `_career_plug_ats_session` cookie from
   the user's local browser profile. It tries Chrome → Firefox → Brave →
   Edge → Chromium and stops at the first hit.

2. `_build_client()` makes a single synchronous GET to `/manage/jobs` and
   extracts the CSRF token from `<meta name="csrf-token">`.

3. An `httpx.AsyncClient` is constructed with two required headers:
   - `X-CSRF-Token` — CareerPlug's AJAX endpoints reject requests without it.
   - `X-Requested-With: XMLHttpRequest` — Without this, CareerPlug returns a
     full-page login redirect instead of the HTML fragment the parsers expect.

The bootstrap GET is synchronous by design: it must complete before the async
client is returned, and FastMCP may invoke tool functions before any async
context is established.

---

## HTTP Client Singleton

`_client` in `src/client.py` is a module-level `AsyncClient` initialized lazily
on the first tool call and never reset within a process.

**If the session expires mid-run**, tools will start returning empty results or
errors. The fix is to reload CareerPlug in the browser and restart the MCP
server process. There is no automatic token refresh.

---

## HTML Parsing Approach

Both endpoints return server-rendered HTML table rows, not JSON.

- Jobs: `tr.job.index-item` rows in the `/manage/jobs/list` response
- Applicants: `tr.app.index-item[data-id]` rows in the `/manage/apps/list` response
- Applicant detail: a full HTML page at `/manage/apps/{id}`; key selectors are
  `.profile-show__applicant-name` (first text node), `.profile-show__email a`,
  `.profile-show__phone a`, `.profile-show__job-activated`, `.profile-show__job-name`,
  and `#accordion .d-flex.flex-row` for the hiring pipeline steps
- Applicant documents: `#profile-applicant-documents [id^="profile-applicant-document-has_attachment_"]`
  rows in the `?tab=documents` page; name from `.profile-applicant-documents__title`,
  download URL from `.profile-applicant-documents__download[href]`, date from
  `.form-text.text-muted`; `get_applicant_details` fetches both pages in parallel
  via `asyncio.gather` and returns documents under the `documents` key

Selectors were discovered via live DOM inspection (see `spec/002`). If
CareerPlug changes their markup, parsers silently return `None` for affected
fields rather than raising exceptions. Uses stdlib `html.parser` as the
BeautifulSoup backend to avoid a native dependency.

---

## `list_applicants` Query Parameters

`list_applicants` uses a single unified query mode. The params sent to
`/manage/apps/list` are:

| Param | Source |
|---|---|
| `page`, `per_page`, `status`, `apps_sort` | caller-supplied |
| `apps_j[]` | from `job_ids` arg (omitted when empty) |
| `apps_category[]` | from `locations` arg, each formatted as `location-{id}` (omitted when empty) |
| `search`, `apps_group`, `apps_ids_bulk_toggle`, `apps_hiring_pipeline_step`, `pipeline` | hardcoded; required for results to match the CareerPlug UI |

The old dual-code path (`job_id` triggering `app_link=true` / `apps_hiring_pipeline_step=all` params)
has been removed. `job_ids` (a list) now replaces the single `job_id` parameter.

---

## Known Limitations

- **No pagination loop**: callers must increment `page` manually.
- **No CSRF token refresh**: an expired session requires a process restart.
- **`debug_cookie_search`** is a temporary diagnostic tool; it may be removed
  once the cookie-search flow is considered stable.
- **`refresh` param on `list_jobs`** maps to CareerPlug's own server-side
  cache-bust mechanism; it does not affect local state.

---

## Adding a New Tool

Follow this pattern:

1. Add a `parse_*` function to `src/parsers.py` that accepts raw HTML and
   returns `list[dict]`.
2. Add an `@mcp.tool` async function to `src/server.py` that calls
   `fetch_html(path, params)` and passes the result to your parser.
3. Do not call `_get_client()` directly from tool functions — always go through
   `fetch_html`.
