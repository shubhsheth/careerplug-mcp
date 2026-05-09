# Spec: get_applicant_documents Tool

## Objective

Add an MCP tool `get_applicant_documents` that fetches the Documents tab for a
single applicant and returns a structured list of uploaded files. Recruiters
upload resumes and other files to an applicant's profile; this tool makes those
files discoverable and downloadable via the MCP server.

**User:** A recruiter or AI assistant querying CareerPlug applicant data.

**Success looks like:** Calling `get_applicant_documents(app_id=145891702)`
returns a list with one entry — `{"name": "Resume.PDF", "attachment_id": 207013606,
"download_url": "/manage/has_attachments/207013606", "uploaded_date": "03/30/2026"}`.

---

## User Stories

- As a recruiter, I want to list an applicant's uploaded documents so I can
  verify their resume was received.
- As an AI assistant, I want the download URL for an applicant's resume so I
  can fetch it for summarization.

---

## Functional Requirements

- FR-1: The tool accepts a single `app_id: int` parameter.
- FR-2: The tool fetches `GET /manage/apps/{app_id}?tab=documents&linked_from_dupe=false`.
- FR-3: The tool returns a list of dicts, one per document, each with:
  - `name` — display name of the document (e.g. `"Resume.PDF"`)
  - `attachment_id` — integer ID parsed from the download URL
  - `download_url` — relative URL string (e.g. `"/manage/has_attachments/207013606"`)
  - `uploaded_date` — date string stripped of the "Uploaded on " prefix (e.g. `"03/30/2026"`)
- FR-4: Returns an empty list when no documents are present.
- FR-5: Follows the established pattern: `fetch_html` → `parse_*` → return data.

---

## Non-Functional Requirements

- NFR-1: Uses `html.parser` as the BeautifulSoup backend — no new dependencies.

---

## Out of Scope

- Downloading or returning document file contents.
- Uploading or deleting documents (write operations).
- Fetching documents from other tabs (resume section on the Overview tab is
  rendered separately and not targeted here).

---

## Assumptions

- Document entries are in divs matching `[id^="profile-applicant-document-has_attachment_"]`
  inside `#profile-applicant-documents`.
- The download URL href on `.profile-applicant-documents__download` is the
  canonical source of both the download path and the attachment ID.
- The upload date text is always prefixed with `"Uploaded on "`.

---

## Tech Stack

Python 3.11+, FastMCP, BeautifulSoup4 (`html.parser`), httpx — same as existing.

---

## Commands

```
Run server: cd src && python server.py
```

---

## Project Structure

```
src/server.py    → add @mcp.tool get_applicant_documents
src/parsers.py   → add parse_applicant_documents(html) -> list[dict]
docs/INDEX.md    → update endpoint table
```

---

## Code Style

```python
# server.py
@mcp.tool
async def get_applicant_documents(app_id: int) -> list:
    """List uploaded documents for a single applicant.

    Args:
        app_id: The numeric CareerPlug applicant ID.

    Returns:
        List of dicts with keys: name, attachment_id, download_url,
        uploaded_date. Empty list if no documents are uploaded.
    """
    html = await fetch_html(f"/manage/apps/{app_id}", {"tab": "documents", "linked_from_dupe": "false"})
    return parse_applicant_documents(html)
```

---

## HTML Selectors (discovered from live DOM)

| Field | Selector | Notes |
|---|---|---|
| document rows | `#profile-applicant-documents [id^="profile-applicant-document-has_attachment_"]` | one per uploaded file |
| name | `.profile-applicant-documents__title` | `.get_text(strip=True)` |
| download URL | `.profile-applicant-documents__download[href]` | also contains attachment ID |
| attachment ID | parse from download URL | last path segment, cast to int |
| upload date | `.form-text.text-muted` | strip `"Uploaded on "` prefix |

---

## Testing Strategy

Manual verification: call `get_applicant_documents(app_id=145891702)` and
confirm one document entry with name `"Resume.PDF"`, attachment_id `207013606`,
and uploaded_date `"03/30/2026"`.

---

## Boundaries

- **Always:** Follow `fetch_html` → `parse_*` pattern; return `None` for missing
  sub-fields; use `html.parser`.
- **Ask first:** Adding new dependencies; changing `client.py`.
- **Never:** Make write/POST requests; store credentials.

---

## Success Criteria

1. `get_applicant_documents(app_id=<id>)` returns a list.
2. Each entry has all four keys: `name`, `attachment_id`, `download_url`, `uploaded_date`.
3. Returns `[]` for an applicant with no documents.
4. The tool appears in the FastMCP tool list alongside `get_applicant_details`.
5. No existing tools are broken.
