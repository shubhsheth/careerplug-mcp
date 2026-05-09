# Spec: download_attachment Tool

## Objective

Add an MCP tool `download_attachment` that retrieves the raw PDF bytes for a
specific document attached to a CareerPlug applicant and returns them
base64-encoded. The existing `get_applicant_details` tool surfaces document
metadata (name, attachment ID, relative download URL) but cannot actually fetch
the file — the relative URL requires session cookies and redirects through
CareerPlug's proxy. This tool fetches a fresh pre-signed S3 URL from the
documents tab and downloads the PDF directly from S3 before the URL expires.

**User:** A recruiter or AI assistant that needs to read, summarize, or store an
applicant's uploaded document (e.g. resume, cover letter).

**Success looks like:** Calling `download_attachment(app_id=148598800,
attachment_id=209946715)` returns a dict with `filename` and `content`
(base64-encoded PDF bytes) that round-trips back to the original file.

---

## User Stories

- As a recruiter, I want to download an applicant's resume so I can read it
  outside CareerPlug.
- As an AI assistant, I want the raw PDF bytes for an applicant's document so I
  can pass them to a PDF parser for summarization.

---

## Functional Requirements

- FR-1: The tool accepts two parameters: `app_id: int` and `attachment_id: int`.
- FR-2: The tool fetches `/manage/apps/{app_id}?tab=documents&linked_from_dupe=false`
  using the authenticated `fetch_html` client to obtain a fresh page containing
  pre-signed S3 URLs.
- FR-3: The tool locates the pre-signed S3 URL by finding all elements with a
  `data-pdf-text-layer-renderer-url` attribute and selecting the one whose URL
  path encodes `attachment_id`. The attachment ID is encoded in the S3 path as
  `/attachments/A/B/C/` where the digits concatenate to form the ID (e.g.
  `/attachments/209/946/715/` → `209946715`).
- FR-4: If no matching S3 URL is found, the tool raises `ValueError` with a
  message indicating the attachment was not found on the page.
- FR-5: The tool immediately downloads the PDF from the S3 URL using a plain
  `httpx.AsyncClient` with no CareerPlug auth headers (the pre-signed URL is
  self-authenticating). The download must start within the URL's 10-second
  expiry window.
- FR-6: The tool returns a dict with two keys:
  - `filename` — the original filename parsed from the last path segment of the
    S3 URL before the query string (e.g. `"Carliyah_Jones_Resume.pdf"`).
  - `content` — the PDF bytes base64-encoded as a UTF-8 string.
- FR-7: The tool follows the established pattern: `fetch_html` for the documents
  tab, a new `parse_attachment_s3_url(html, attachment_id)` parser, then a
  direct S3 download. No direct use of `_get_client()`.

---

## Non-Functional Requirements

- NFR-1: Uses `html.parser` as the BeautifulSoup backend — no new dependencies
  beyond what is already installed (`httpx`, `beautifulsoup4`, `base64` stdlib).
- NFR-2: The S3 download uses a fresh, short-lived `httpx.AsyncClient` (via
  `async with`) rather than reusing the CareerPlug client, so no auth headers
  leak to S3.
- NFR-3: The fetch and download happen sequentially (not in parallel) because
  the download URL depends on the fetch result.

---

## Out of Scope

- Uploading or deleting attachments (write operations).
- Extracting text from the PDF (requires a separate library).
- Caching the S3 URL or PDF bytes between calls.
- Handling multi-page or chunked downloads.
- Returning anything other than raw bytes (no text extraction, no thumbnails).

---

## Assumptions

- Every attachment rendered on the documents tab has a corresponding
  `.pdf-text-layer-renderer` element with `data-pdf-text-layer-renderer-url`.
- The S3 URL path always encodes the attachment ID as three slash-separated
  segments under `/attachments/` (e.g. `209/946/715` for `209946715`).
- The pre-signed URL is valid for 10 seconds from page render; sequential
  fetch→parse→download completes within that window under normal network
  conditions.
- A plain `httpx.AsyncClient` with default settings can reach S3 directly from
  the server running the MCP tool.

---

## Tech Stack

Python 3.11+, FastMCP, BeautifulSoup4 (`html.parser`), httpx, `base64` (stdlib)
— no new dependencies.

---

## Commands

```
Run server: cd src && python server.py
```

---

## Project Structure

```
src/server.py    → add @mcp.tool download_attachment
src/parsers.py   → add parse_attachment_s3_url(html, attachment_id) -> str
src/client.py    → no changes needed
docs/INDEX.md    → update endpoint table and tool list
```

---

## Code Style

```python
# parsers.py
def parse_attachment_s3_url(html: str, attachment_id: int) -> str:
    """Find the pre-signed S3 URL for a specific attachment on the documents tab.

    Args:
        html: Raw HTML from /manage/apps/{id}?tab=documents.
        attachment_id: Numeric attachment ID to locate.

    Returns:
        The pre-signed S3 URL string.

    Raises:
        ValueError: If no URL matching attachment_id is found.
    """
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("[data-pdf-text-layer-renderer-url]"):
        url = el["data-pdf-text-layer-renderer-url"]
        # ID is encoded in S3 path as /attachments/A/B/C/; strip digits and join.
        match = re.search(r"/attachments/([\d/]+)/", url)
        if match and int(match.group(1).replace("/", "")) == attachment_id:
            return url
    raise ValueError(f"Attachment {attachment_id} not found on documents tab for this applicant.")


# server.py
@mcp.tool
async def download_attachment(app_id: int, attachment_id: int) -> dict:
    """Download a document attached to a CareerPlug applicant as raw PDF bytes.

    Args:
        app_id: Numeric CareerPlug applicant ID.
        attachment_id: Numeric attachment ID (from get_applicant_details documents list).

    Returns:
        Dict with keys:
        - ``filename``: original filename (e.g. ``"Resume.pdf"``).
        - ``content``: base64-encoded PDF bytes as a UTF-8 string.
    """
    docs_html = await fetch_html(
        f"/manage/apps/{app_id}",
        {"tab": "documents", "linked_from_dupe": "false"},
    )
    s3_url = parse_attachment_s3_url(docs_html, attachment_id)
    filename = s3_url.split("?")[0].rsplit("/", 1)[-1]
    async with httpx.AsyncClient() as client:
        r = await client.get(s3_url)
        r.raise_for_status()
    return {"filename": filename, "content": base64.b64encode(r.content).decode()}
```

---

## Testing Strategy

Manual verification: call `download_attachment(app_id=148598800, attachment_id=209946715)`
and confirm:
- Returns a dict with `filename` and `content` keys.
- `filename` matches the uploaded file name (e.g. `"Carliyah_Jones_Resume.pdf"`).
- `base64.b64decode(result["content"])` starts with `%PDF-` (valid PDF magic bytes).
- Calling with a nonexistent `attachment_id` raises `ValueError`.

---

## Boundaries

- **Always:** Use `fetch_html` for the CareerPlug request; use a plain
  `httpx.AsyncClient` (no auth headers) for the S3 download; parse the S3 URL
  with `parse_attachment_s3_url` in `parsers.py`.
- **Ask first:** Adding new dependencies; changing `client.py`; changing the
  return format.
- **Never:** Make write/POST requests; store credentials; reuse the CareerPlug
  client for the S3 download.

---

## Success Criteria

1. `download_attachment(app_id, attachment_id)` returns a dict with `filename`
   and `content`.
2. `base64.b64decode(result["content"])` starts with `%PDF-`.
3. `filename` matches the name of the uploaded file.
4. Passing a nonexistent `attachment_id` raises `ValueError`.
5. The tool appears in the FastMCP tool list.
6. No existing tools are broken.
