import fastmcp
import browser_cookie3

from client import fetch_html
from parsers import parse_jobs, parse_applicants

mcp = fastmcp.FastMCP("careerplug")


@mcp.tool
async def list_jobs(
    page: int = 1,
    status: int | None = None,
    refresh: bool = False,
) -> list:
    """List jobs from CareerPlug.

    Args:
        page: Page number for pagination (1-indexed).
        status: Filter by job status. None returns all jobs.
            0=draft, 1=active, 2=closed, 3=passive.
        refresh: Pass ``refresh=1`` to CareerPlug to bust its server-side
            cache and return fresh data.

    Returns:
        List of job dicts with keys: id, title, job_url, status, location,
        applicant_count, posted_date.
    """
    params = {
        "page": page,
        "refresh": "1" if refresh else "",
        "status": "" if status is None else status,
    }
    html = await fetch_html("/manage/jobs/list", params)
    return parse_jobs(html)


@mcp.tool
async def list_applicants(
    page: int = 1,
    status: str = "active",
    job_id: int | None = None,
) -> list:
    """List applicants from CareerPlug.

    When ``job_id`` is provided, uses the pipeline-centric query mode
    (``app_link=true``, ``apps_hiring_pipeline_step=all``) that CareerPlug's
    frontend uses on the job detail page. This is a distinct query path with
    different URL params, not a filter added to the default list view.

    When ``job_id`` is absent, queries the global applicants list filtered
    by ``status``.

    Args:
        page: Page number for pagination (1-indexed).
        status: Applicant status filter for the global list view.
            Valid values: active, new, in_process, disqualified, hired,
            pipeline, inactive. Ignored when ``job_id`` is set.
        job_id: If provided, return only applicants for this job ID across
            all pipeline steps.

    Returns:
        List of applicant dicts with keys: id, name, profile_url, job_title,
        job_url, location, current_step.
    """
    if job_id is not None:
        # job_id triggers CareerPlug's pipeline-centric query mode, which uses
        # entirely different params from the global applicant list view.
        params = {
            "app_link": "true",
            "apps_hiring_pipeline_step": "all",
            "apps_j[]": job_id,
            "apps_job_status": "all",
            "page": page,
        }
    else:
        params = {"page": page, "status": status}
    html = await fetch_html("/manage/apps/list", params)
    return parse_applicants(html)


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
