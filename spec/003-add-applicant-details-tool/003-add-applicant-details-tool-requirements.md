# Spec: get_applicant_details Tool

## Objective

Add an MCP tool `get_applicant_details` that fetches a single applicant's full
profile from CareerPlug — including contact info, hiring pipeline state, and
uploaded documents — and returns all data in one structured response. The
existing `list_applicants` tool returns a shallow summary; this tool provides
the complete view a recruiter sees across the Overview and Documents tabs.

**User:** A recruiter or AI assistant querying CareerPlug applicant data.

**Success looks like:** Calling `get_applicant_details(app_id=148657239)` returns
a dict with all profile fields correctly extracted, plus a `documents` list
containing any uploaded files (e.g. resume) with name, attachment ID, download
URL, and upload date.

---

## User Stories

- As a recruiter, I want to look up an applicant by ID so I can see their
  contact info and where they are in the hiring pipeline.
- As a recruiter, I want to see all hiring steps and their statuses so I know
  what actions remain for this applicant.
- As an AI assistant, I want the download URL for an applicant's resume so I
  can fetch it for summarization.

---

## Functional Requirements

- FR-1: The tool accepts a single `app_id: int` parameter.
- FR-2: The tool fetches two pages in parallel using `asyncio.gather`:
  - `GET /manage/apps/{app_id}` — full applicant profile (overview tab)
  - `GET /manage/apps/{app_id}?tab=documents&linked_from_dupe=false` — documents tab
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
  - `is_duplicate` — boolean; `True` if CareerPlug flagged this as a duplicate
  - `documents` — list of dicts, one per uploaded file, each with:
    - `name` — display name (e.g. `"Resume.PDF"`)
    - `attachment_id` — integer ID parsed from the download URL
    - `download_url` — relative URL string (e.g. `"/manage/has_attachments/207013606"`)
    - `uploaded_date` — date string stripped of the "Uploaded on " prefix (e.g. `"03/30/2026"`)
- FR-4: Fields that cannot be found in the markup return `None`. `hiring_steps`
  and `documents` default to empty lists.
- FR-5: Follows the established pattern: `fetch_html` → `parse_*` → return data.
  No direct use of `_get_client()`.

---

## Non-Functional Requirements

- NFR-1: Uses `html.parser` as the BeautifulSoup backend — no new dependencies.
- NFR-2: The two HTTP fetches run in parallel (`asyncio.gather`) to avoid
  doubling latency.

---

## Out of Scope

- Downloading or returning document file contents.
- Uploading or deleting documents (write operations).
- Fetching comments, scorecards, or other tabs.
- Advancing or deactivating an applicant (write operations).
- Handling pagination (one page per applicant).

---

## Assumptions

- The "applied on / via" string format is always `"Applied on MM/DD/YYYY via
  Source"` and can be split by ` via `.
- Job title/location uses `rsplit(", ", 1)` so titles containing commas are
  preserved; location is always the last segment.
- Step status indicators use consistent CSS classes: `current` = active,
  `future` = not yet reached. Steps without an `<i>` element are `completed`.
- Document entries are in divs matching
  `[id^="profile-applicant-document-has_attachment_"]` inside
  `#profile-applicant-documents`.
- The upload date text is always prefixed with `"Uploaded on "`.

---

## Tech Stack

Python 3.11+, FastMCP, BeautifulSoup4 (`html.parser`), httpx, asyncio — same
as existing.

---

## Commands

```
Run server: cd src && python server.py
```

---

## Project Structure

```
src/server.py    → add @mcp.tool get_applicant_details (replaces two separate tools)
src/parsers.py   → add parse_applicant_details(html) and parse_applicant_documents(html)
docs/INDEX.md    → update endpoint table and HTML parsing section
```

---

## Code Style

```python
# server.py
import asyncio

@mcp.tool
async def get_applicant_details(app_id: int) -> dict:
    """Fetch full profile for a single applicant, including documents.

    Args:
        app_id: The numeric CareerPlug applicant ID (visible in the URL,
            e.g. 148657239 from ``/manage/apps/148657239``).

    Returns:
        Dict with keys: name, email, phone, applied_date, applied_via,
        job_title, job_location, current_step, hiring_steps, is_duplicate,
        documents.
        ``hiring_steps`` is a list of dicts with ``name`` and ``status``
        (``"current"``, ``"future"``, or ``"completed"``).
        ``documents`` is a list of dicts with ``name``, ``attachment_id``,
        ``download_url``, and ``uploaded_date``.
        Fields absent from the page are ``None``.
    """
    overview_html, docs_html = await asyncio.gather(
        fetch_html(f"/manage/apps/{app_id}", {}),
        fetch_html(f"/manage/apps/{app_id}", {"tab": "documents", "linked_from_dupe": "false"}),
    )
    result = parse_applicant_details(overview_html)
    result["documents"] = parse_applicant_documents(docs_html)
    return result
```

---

## HTML Selectors (discovered from live DOM)

### Overview tab (`/manage/apps/{id}`)

| Field | Selector | Notes |
|---|---|---|
| name | `.profile-show__applicant-name` | first text node (NavigableString); strip whitespace |
| email | `.profile-show__email a` | `.get_text(strip=True)` |
| phone | `.profile-show__phone a` | `.get_text(strip=True)` |
| applied_date + via | `.profile-show__job-activated` | text: `"Applied on MM/DD/YYYY via Source"` |
| job (title + location) | `.profile-show__job-name` | text: `"Applied for: TITLE, LOCATION"` |
| hiring steps | `#accordion .d-flex.flex-row` | one row per step |
| step status | `i.fa-stack-2x` inside `.overview-accordion__status` | class `current` / `future`; absence = completed |
| step name | `.overview-accordion__hiring-step .card-title` | `.get_text(strip=True)` |
| is_duplicate | `[data-deactivate-drawer-duplicate]` | attribute value `"true"` / `"false"` |

### Documents tab (`/manage/apps/{id}?tab=documents`)

| Field | Selector | Notes |
|---|---|---|
| document rows | `#profile-applicant-documents [id^="profile-applicant-document-has_attachment_"]` | one per uploaded file |
| name | `.profile-applicant-documents__title` | `.get_text(strip=True)` |
| download URL | `.profile-applicant-documents__download[href]` | also contains attachment ID |
| attachment ID | parse from download URL | last path segment, cast to int |
| upload date | `.form-text.text-muted` | strip `"Uploaded on "` prefix |

---

## Testing Strategy

Manual verification: call `get_applicant_details(app_id=148657239)` and confirm:
- All profile fields are populated.
- `documents` list contains any uploaded files with all four keys.
- For an applicant with no documents, `documents` is `[]`.

---

## Boundaries

- **Always:** Follow `fetch_html` → `parse_*` pattern; return `None` for missing
  sub-fields; use `html.parser`; fetch both pages in parallel.
- **Ask first:** Adding new dependencies; changing `client.py`.
- **Never:** Make write/POST requests; store credentials.

---

## Success Criteria

1. `get_applicant_details(app_id=<id>)` returns a dict with all eleven keys.
2. `name`, `email`, and `current_step` are non-`None` for any active applicant.
3. `hiring_steps` is a list with at least one entry; each entry has `name` and `status`.
4. `documents` is a list; each entry has `name`, `attachment_id`, `download_url`, `uploaded_date`.
5. Returns `documents: []` for an applicant with no uploaded files.
6. The tool appears in the FastMCP tool list; `get_applicant_documents` does NOT.
7. No existing tools are broken.
