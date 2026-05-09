# Plan: Implement list_jobs and list_applicants with httpx

## Implementation Order

1. Add `httpx` and `beautifulsoup4` dependencies
2. Update `src/server.py`:
   a. Replace Playwright imports with httpx + bs4
   b. Add env-var-based auth (session cookie + CSRF token)
   c. Build shared async httpx client
   d. Implement `_fetch_html(url, params)` helper
   e. Implement `_parse_applicants(html)` using known selectors
   f. Implement `_parse_jobs(html)` using selectors from discovery step
   g. Wire `list_applicants` and `list_jobs` to fetch + parse
   h. Remove `get_page_html` debug tool

## Tasks

- [x] Task: Update spec requirements to reflect httpx approach
  - Acceptance: requirements doc documents httpx auth, HTML endpoints, known selectors
  - Files: `spec/002-playwright-tool-implementation/002-playwright-tool-implementation-requirements.md`

- [x] Task: Discover `/manage/jobs/list` selectors
  - Row: `tr.job.index-item`
  - `id`: `td.text-center input[data-id]` → `data-id` attr
  - `title`: `td.max-width a.name` text + href → `job_url`
  - `status`: `td.max-width span.badge` text
  - `location`: `td.location` text
  - `applicant_count`: `td.text-capitalize:not(.location)` text (int)
  - `posted_date`: second `td.min-width` text (first is the clicks link)

- [x] Task: Add httpx and beautifulsoup4 deps
  - Acceptance: `pyproject.toml` lists both; `uv run python -c "import httpx, bs4"` exits 0
  - Verify: `uv add httpx beautifulsoup4`
  - Files: `pyproject.toml`, `uv.lock`

- [x] Task: Implement auth and httpx client
  - Acceptance: module reads `CAREERPLUG_SESSION_COOKIE` and `CAREERPLUG_CSRF_TOKEN` env vars; raises `RuntimeError` if missing; constructs `httpx.AsyncClient` with correct headers/cookies
  - Files: `src/server.py`

- [x] Task: Implement `list_applicants`
  - Acceptance: calls `/manage/apps/list` with correct params, parses `tr.app.index-item` rows, returns list of dicts with keys `id`, `name`, `profile_url`, `job_title`, `job_url`, `location`, `current_step`
  - Verify: `list_applicants()` returns non-empty list; `list_applicants(status="new")` returns only new applicants; `list_applicants(job_id=<id>)` returns applicants for that job
  - Files: `src/server.py`

- [x] Task: Implement `list_jobs`
  - Acceptance: calls `/manage/jobs/list` with correct params, parses job rows, returns list of dicts
  - Verify: `list_jobs()` returns non-empty list; `list_jobs(status=1)` returns only active jobs
  - Files: `src/server.py`
  - **Depends on:** jobs selector discovery task

- [x] Task: Remove debug tools; `get_list_html` removed along with Playwright
  - Acceptance: `get_page_html` no longer appears in `src/server.py`; Playwright import removed; `playwright` removed from `pyproject.toml`
  - Files: `src/server.py`, `pyproject.toml`

## Key Design Decisions

### Auth via env vars
```python
import os

_SESSION_COOKIE = os.environ["CAREERPLUG_SESSION_COOKIE"]
_CSRF_TOKEN = os.environ["CAREERPLUG_CSRF_TOKEN"]
```
Raises `KeyError` (clear error) if not set. No default values.

### Shared async httpx client
```python
import httpx

_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=_BASE,
            cookies={"_career_plug_ats_session": _SESSION_COOKIE},
            headers={
                "X-CSRF-Token": _CSRF_TOKEN,
                "Accept": "text/html",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
    return _client
```

### Fetch helper
```python
async def _fetch_html(path: str, params: dict) -> str:
    r = await _get_client().get(path, params=params)
    r.raise_for_status()
    return r.text
```

### Applicants parser (known selectors)
```python
from bs4 import BeautifulSoup

def _parse_applicants(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select("tr.app.index-item"):
        a_name = row.select_one("td.td_applicant a")
        a_job = row.select_one("td.td_applied-for a")
        step = row.select_one("td.td_current-step .text-margin")
        loc = row.select_one("td.td_applied-for span.subinfo")
        results.append({
            "id": row.get("data-id"),
            "name": a_name.get_text(strip=True) if a_name else None,
            "profile_url": a_name["href"] if a_name else None,
            "job_title": a_job.get_text(strip=True) if a_job else None,
            "job_url": a_job["href"] if a_job else None,
            "location": loc.get_text(strip=True) if loc else None,
            "current_step": step.get_text(strip=True) if step else None,
        })
    return results
```

### Jobs parser (selectors TBD after discovery)
Fill in after inspecting `/manage/jobs/list` HTML.

## Files to Modify

- `src/server.py` — full rewrite of implementation (tool logic unchanged)
- `pyproject.toml` — replace `playwright` with `httpx` + `beautifulsoup4`
