# Spec: get_applicant_details Tool

## Objective

Add an MCP tool `get_applicant_details` that fetches a single applicant's profile
from CareerPlug and returns structured data. The existing `list_applicants` tool
returns a shallow summary (name, email, current step). This tool provides the full
profile view — contact info, applied source, job title, and the complete hiring
pipeline with each step's status — matching what a recruiter sees on
`/manage/apps/{app_id}`.

**User:** A recruiter or hiring manager using the MCP server to query CareerPlug
applicant data from an AI assistant.

**Success looks like:** Calling `get_applicant_details(app_id=148657239)` returns a
dict with all key fields correctly extracted from the HTML, without requiring any
additional requests beyond the single page fetch.

---

## User Stories

- As a recruiter, I want to look up an applicant by ID so I can see their contact
  info and where they are in the hiring pipeline.
- As a recruiter, I want to see all hiring steps and their statuses so I know what
  actions remain for this applicant.

---

## Functional Requirements

- FR-1: The tool accepts a single `app_id: int` parameter.
- FR-2: The tool fetches `GET /manage/apps/{app_id}` (full HTML page, no query
  params needed).
- FR-3: The tool returns a dict with these keys:
  - `name` — applicant's full name
  - `email` — email address
  - `phone` — phone number (or `None` if not present)
  - `applied_date` — date string as shown on the page (e.g. `"05/09/2026"`)
  - `applied_via` — source string (e.g. `"ZipRecruiter"`, or `None`)
  - `job_title` — position applied for (e.g. `"Dermatology Front Desk/ Receptionist"`)
  - `job_location` — location/office name (e.g. `"Elite Dermatology- Fulshear"`)
  - `current_step` — name of the hiring step currently active (e.g. `"New Application"`)
  - `hiring_steps` — list of dicts, one per step, each with `name` (str) and
    `status` (`"current"`, `"future"`, or `"completed"`)
- FR-4: Fields that cannot be found in the markup return `None` rather than
  raising an exception (consistent with existing parser behavior).
- FR-5: The tool follows the established pattern: `fetch_html` → `parse_*` →
  return structured data. No direct use of `_get_client()`.

---

## Non-Functional Requirements

- NFR-1: The parser must use `html.parser` as the BeautifulSoup backend (stdlib
  only — no lxml or html5lib).
- NFR-2: No new dependencies may be added.

---

## Out of Scope

- Fetching resume content or PDF data.
- Fetching comments, scorecards, or documents tabs.
- Advancing or deactivating an applicant (write operations).
- Handling pagination (there is only one page per applicant).

---

## Assumptions

- The `X-Requested-With: XMLHttpRequest` header already on the shared client does
  not cause `/manage/apps/{app_id}` to return a different response than a browser
  request. (If it does, `fetch_html` may need a `full_page=True` mode — but we
  will verify empirically first.)
- The "applied on / via" string format is always `"Applied on MM/DD/YYYY via
  Source"` and can be split by ` via `.
- The step status indicators use consistent CSS classes: `current` means active,
  `future` means not yet reached. Any step without an indicator `<i>` element
  will be treated as `completed` (it would have a checkmark icon instead).

---

## Tech Stack

Python 3.11+, FastMCP, BeautifulSoup4 (`html.parser`), httpx — same as the
existing server.

---

## Commands

```
Run server:   cd src && python server.py
Lint:         (none configured yet)
Test:         (none configured yet)
```

---

## Project Structure

```
src/server.py    → add @mcp.tool get_applicant_details
src/parsers.py   → add parse_applicant_details(html) -> dict
src/client.py    → no changes needed
docs/INDEX.md    → update endpoint table and "Adding a New Tool" section
```

---

## Code Style

Follow the exact pattern of `list_applicants` / `parse_applicants`:

```python
# server.py
@mcp.tool
async def get_applicant_details(app_id: int) -> dict:
    """Fetch full profile for a single applicant.

    Args:
        app_id: The numeric CareerPlug applicant ID.

    Returns:
        Dict with keys: name, email, phone, applied_date, applied_via,
        job_title, job_location, current_step, hiring_steps.
    """
    html = await fetch_html(f"/manage/apps/{app_id}", {})
    return parse_applicant_details(html)
```

```python
# parsers.py
def parse_applicant_details(html: str) -> dict:
    """Extract applicant profile data from a /manage/apps/{id} HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    # ... selectors ...
    return { ... }
```

---

## HTML Selectors (discovered from live DOM)

| Field | Selector | Notes |
|---|---|---|
| name | `.profile-show__applicant-name` | first text node; strip whitespace |
| email | `.profile-show__email a` | `.get_text(strip=True)` |
| phone | `.profile-show__phone a` | `.get_text(strip=True)` |
| applied_date + via | `.profile-show__job-activated` | text: `"Applied on MM/DD/YYYY via Source"` |
| job (title + location) | `.profile-show__job-name` | text: `"Applied for: TITLE, LOCATION"` |
| hiring steps | `.d-flex.flex-row` rows in `#accordion` | each row has a status `<i>` and a `.card-title` |
| step status | `<i class="fa-light fa-circle fa-stack-2x {status}">` | class is `current`, `future`; absence = completed |
| step name | `.overview-accordion__hiring-step .card-title` | `.get_text(strip=True)` |

---

## Testing Strategy

No automated test framework is configured. Verification is manual:

1. Start the MCP server.
2. Call `get_applicant_details(app_id=148657239)` (or any known applicant ID).
3. Confirm all fields are populated correctly.

---

## Boundaries

- **Always:** Follow the `fetch_html` → `parse_*` pattern; return `None` for
  missing fields; use `html.parser`.
- **Ask first:** Adding new dependencies; changing `client.py` behavior.
- **Never:** Make write/POST requests from this tool; store credentials.

---

## Success Criteria

1. `get_applicant_details(app_id=<id>)` returns a dict with all nine keys present.
2. `name`, `email`, and `current_step` are non-`None` for any active applicant.
3. `hiring_steps` is a list with at least one entry; each entry has `name` and
   `status`.
4. `applied_date` and `applied_via` are correctly split from the "Applied on…"
   string when present.
5. The tool appears in the FastMCP tool list alongside `list_applicants` and
   `list_jobs`.
6. No existing tools are broken.
