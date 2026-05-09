# Spec: Inline PDF Text in get_applicant_details

## Objective

Consolidate PDF text extraction into `get_applicant_details` so callers receive
document text in a single tool call. Previously, callers had to call
`get_applicant_details` to get document metadata and then call
`download_attachment` separately to get the text of each PDF. The separate tool
is redundant because the documents-tab HTML (which contains the pre-signed S3
URLs) is already fetched inside `get_applicant_details`.

**User:** A recruiter or AI assistant that wants to read an applicant's resume or
cover letter without issuing multiple tool calls.

**Success looks like:** Calling `get_applicant_details(app_id=148598800)` returns
a dict whose `documents` list includes a `text` key on each entry — populated
with extracted text for PDFs, and a short explanatory string for non-PDFs.
The `download_attachment` tool no longer exists.

---

## User Stories

- As an AI assistant, I want `get_applicant_details` to return the full text of
  every attached PDF so I can summarize a resume without making a second tool call.
- As a recruiter, I want to see document content alongside profile metadata so I
  can evaluate an applicant in one step.

---

## Functional Requirements

- FR-1: `get_applicant_details` fetches the documents tab HTML exactly as it does
  today (one `asyncio.gather` call alongside the overview tab).
- FR-2: For each document entry returned by `parse_applicant_documents`, the tool
  attempts to resolve a pre-signed S3 URL using `parse_attachment_s3_url`.
- FR-3: If an S3 URL is found, the tool downloads the PDF from S3 with a plain
  `httpx.AsyncClient` (no CareerPlug auth headers) and extracts all text via
  `pypdf.PdfReader`. The extracted text is joined with `"\n"` and stored under
  the `text` key of the document dict.
- FR-4: All PDF downloads happen in parallel via `asyncio.gather` so total
  latency is bounded by the slowest single download, not the sum.
- FR-5: If `parse_attachment_s3_url` raises `ValueError` (attachment not found
  on page), `text` is set to `None`.
- FR-6: If the file is not a PDF (determined by attempting `pypdf.PdfReader` and
  catching `pypdf.errors.PdfReadError`, or by the filename not ending in `.pdf`),
  `text` is set to `"Not a PDF document — text extraction is not supported for
  this file type."`.
- FR-7: The `download_attachment` tool is removed from `src/server.py`.
- FR-8: The `parse_attachment_s3_url` parser in `src/parsers.py` is retained
  unchanged (it is still used by FR-2).

---

## Non-Functional Requirements

- NFR-1: No new dependencies. `pypdf` and `httpx` are already installed.
- NFR-2: S3 downloads use a short-lived `httpx.AsyncClient` (via `async with`)
  separate from the CareerPlug client so no auth headers leak to S3.
- NFR-3: A single failure to download or parse one document must not abort the
  entire `get_applicant_details` call; other documents and all profile fields
  must still be returned.

---

## Out of Scope

- Uploading or deleting attachments (write operations).
- Caching S3 URLs or PDF bytes between calls.
- Extracting text from non-PDF formats (`.docx`, images, etc.).
- Returning raw PDF bytes.

---

## Assumptions

- Every PDF attachment rendered on the documents tab has a corresponding element
  with `data-pdf-text-layer-renderer-url`; non-PDF attachments may not.
- The S3 URL path encodes the attachment ID as three slash-separated segments
  under `/attachments/` (e.g. `209/946/715` → `209946715`).
- The pre-signed URL is valid for ~10 seconds; since `get_applicant_details`
  fetches the docs HTML and immediately triggers downloads, the window is met
  under normal network conditions.

---

## Tech Stack

Python 3.11+, FastMCP, BeautifulSoup4 (`html.parser`), httpx, pypdf, asyncio —
no new dependencies.

---

## Commands

```
Run server: cd src && python server.py
```

---

## Project Structure

```
src/server.py    → remove download_attachment; extend get_applicant_details
src/parsers.py   → no changes (parse_attachment_s3_url retained)
src/client.py    → no changes
docs/INDEX.md    → remove download_attachment references; document text field
```

---

## Code Style

```python
# server.py — get_applicant_details (updated)
@mcp.tool
async def get_applicant_details(app_id: int) -> dict:
    overview_html, docs_html = await asyncio.gather(
        fetch_html(f"/manage/apps/{app_id}", {}),
        fetch_html(f"/manage/apps/{app_id}", {"tab": "documents", "linked_from_dupe": "false"}),
    )
    result = parse_applicant_details(overview_html)
    docs = parse_applicant_documents(docs_html)

    async def _extract_text(doc: dict) -> dict:
        try:
            s3_url = parse_attachment_s3_url(docs_html, doc["attachment_id"])
        except ValueError:
            return {**doc, "text": None}
        filename = s3_url.split("?")[0].rsplit("/", 1)[-1]
        if not filename.lower().endswith(".pdf"):
            return {**doc, "text": "Not a PDF document — text extraction is not supported for this file type."}
        async with httpx.AsyncClient() as client:
            r = await client.get(s3_url)
            r.raise_for_status()
        try:
            reader = pypdf.PdfReader(io.BytesIO(r.content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except pypdf.errors.PdfReadError:
            text = "Not a PDF document — text extraction is not supported for this file type."
        return {**doc, "text": text}

    result["documents"] = list(await asyncio.gather(*[_extract_text(d) for d in docs]))
    return result
```

---

## Testing Strategy

Manual verification: call `get_applicant_details(app_id=<id>)` and confirm:
- Returns a dict with all existing profile fields intact.
- `documents` is a list; each entry has `name`, `attachment_id`, `download_url`,
  `uploaded_date`, and `text`.
- For a PDF attachment, `text` is a non-empty string starting with readable content.
- For a non-PDF attachment (if one exists), `text` is the explanatory string.
- If `attachment_id` is absent or not found, `text` is `None`.

---

## Boundaries

- **Always:** Use `fetch_html` for CareerPlug requests; use a plain
  `httpx.AsyncClient` for S3 downloads; keep `parse_attachment_s3_url` in
  `parsers.py`.
- **Ask first:** Adding new dependencies; changing `client.py`.
- **Never:** Make write/POST requests; store credentials; reuse the CareerPlug
  client for S3 downloads.

---

## Success Criteria

1. `get_applicant_details(app_id)` returns documents with a `text` field.
2. PDF documents have non-empty extracted text.
3. Non-PDF documents have the explanatory string instead of `None` or an error.
4. A single document download failure does not abort the whole call.
5. `download_attachment` no longer appears in the FastMCP tool list.
6. All other tools (`list_jobs`, `list_applicants`, `debug_cookie_search`) still work.
