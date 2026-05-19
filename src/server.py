import asyncio
import io
from pathlib import Path

import fastmcp
import httpx
import pypdf
import browser_cookie3

from client import fetch_html
from parsers import parse_jobs, parse_applicants, parse_applicant_details, parse_applicant_documents, parse_attachment_s3_url

mcp = fastmcp.FastMCP("careerplug")

_DASHBOARD_HTML = Path(__file__).parent.parent / "src" / "resources" / "dashboard.html"


@mcp.resource("careerplug://dashboard", mime_type="text/html")
@mcp.tool
def get_dashboard() -> str:
    """Return the CareerPlug dashboard as an HTML string."""
    return _DASHBOARD_HTML.read_text()


@mcp.tool
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    status: int | None = None,
    sort_by: str = "jobs.created_at",
    sort_direction: str = "DESC",
    refresh: bool = False,
) -> list:
    """List jobs from CareerPlug.

    Args:
        page: Page number for pagination (1-indexed).
        per_page: Number of results per page.
        status: Filter by job status. None returns all jobs.
            0=draft, 1=active, 2=closed, 3=passive.
        sort_by: Field to sort by. Valid values: jobs.created_at, jobs.name,
            jobs.refreshed_at, location_name, app_count, jobs.updated_at.
        sort_direction: Sort direction. Valid values: ASC, DESC.
        refresh: Pass ``refresh=1`` to CareerPlug to bust its server-side
            cache and return fresh data.

    Returns:
        List of job dicts with keys: id, title, job_url, status, location,
        applicant_count, posted_date.
    """
    params = {
        "page": page,
        "per_page": per_page,
        "refresh": "1" if refresh else "",
        "status": "" if status is None else status,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
    }
    html = await fetch_html("/manage/jobs/list", params)
    return parse_jobs(html)


@mcp.tool
async def list_applicants(
    page: int = 1,
    per_page: int = 20,
    status: str = "active",
    sort_by: str = "date-desc",
    job_ids: list[int] = [],
    locations: list[int] = [],
) -> list:
    """List applicants from CareerPlug.

    Args:
        page: Page number for pagination (1-indexed).
        per_page: Number of results per page.
        status: Applicant status filter. Valid values: active, new, in_process,
            disqualified, hired, pipeline, inactive.
        sort_by: Sort order. Valid values: date-asc, date-desc, name-asc,
            name-desc, job_name-asc, job_name-desc, score-asc, score-desc.
        job_ids: Filter to applicants on these job IDs. Empty list returns all jobs.
        locations: Filter by location IDs. Empty list returns all locations.

    Returns:
        List of applicant dicts with keys: id, name, profile_url, job_title,
        job_url, location, current_step.
    """
    params: dict = {
        "page": page,
        "per_page": per_page,
        "search": "",
        "status": status,
        "apps_sort": sort_by,
        "apps_group": "none",
        "apps_ids_bulk_toggle": "false",
        "apps_hiring_pipeline_step": status,
        "pipeline": "f",
    }
    if job_ids:
        params["apps_j[]"] = job_ids
    if locations:
        params["apps_category[]"] = [f"location-{loc}" for loc in locations]
    html = await fetch_html("/manage/apps/list", params)
    return parse_applicants(html)


@mcp.tool
async def get_applicant_details(app_id: int) -> dict:
    """Fetch full profile for a single applicant, including uploaded documents with text.

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
        ``download_url``, ``uploaded_date``, and ``text``.
        ``text`` contains extracted PDF text, an explanatory string for
        non-PDF files, or ``None`` if the S3 URL could not be resolved.
        Fields absent from the page are ``None``.
    """
    overview_html, docs_html = await asyncio.gather(
        fetch_html(f"/manage/apps/{app_id}", {}),
        fetch_html(f"/manage/apps/{app_id}", {"tab": "documents", "linked_from_dupe": "false"}),
    )
    result = parse_applicant_details(overview_html)

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

    docs = parse_applicant_documents(docs_html)
    result["documents"] = list(await asyncio.gather(*[_extract_text(d) for d in docs]))
    return result


@mcp.tool
async def debug_cookie_search() -> dict:
    """Diagnostic tool: report cookie search results across all supported browsers.

    Checks each browser for the CareerPlug session cookie without attempting
    to build the HTTP client or make any requests.

    Returns:
        Dict keyed by browser name. Each value has ``found`` (bool),
        ``has_session_cookie`` (bool), and ``all_cookie_names`` (list of str)
        on success, or ``found`` (False) and ``error`` (str) on failure.

    Note:
        This is a temporary diagnostic tool and may be removed in a future
        iteration once the cookie-search flow is considered stable.
    """
    browsers = [
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
        ("Brave", browser_cookie3.brave),
        ("Edge", browser_cookie3.edge),
        ("Chromium", browser_cookie3.chromium),
    ]
    results = {}
    for name, loader in browsers:
        try:
            cookiejar = loader(domain_name=".careerplug.com")
            cookies = [c.name for c in cookiejar]
            has_session = "_career_plug_ats_session" in cookies
            results[name] = {"found": True, "has_session_cookie": has_session, "all_cookie_names": cookies}
        except Exception as e:
            results[name] = {"found": False, "error": str(e)}
    return results


if __name__ == "__main__":
    mcp.run()
