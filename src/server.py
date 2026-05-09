import fastmcp
import httpx
import browser_cookie3
from bs4 import BeautifulSoup

mcp = fastmcp.FastMCP("careerplug")

_BASE = "https://app.careerplug.com"

_client: httpx.AsyncClient | None = None


def _build_client() -> httpx.AsyncClient:
    """Read session cookie from Chrome and CSRF token from CareerPlug page meta tag."""
    cookiejar = browser_cookie3.chrome(domain_name=".careerplug.com")
    session_cookie = next(
        (c.value for c in cookiejar if c.name == "_career_plug_ats_session"),
        None,
    )
    if not session_cookie:
        raise RuntimeError(
            "No CareerPlug session found in Chrome. "
            "Please log into app.careerplug.com in Chrome and try again."
        )

    # Synchronous bootstrap request to get the CSRF token from the page meta tag
    r = httpx.get(
        f"{_BASE}/manage/jobs",
        cookies={"_career_plug_ats_session": session_cookie},
        headers={"Accept": "text/html"},
        follow_redirects=True,
        timeout=15,
    )
    r.raise_for_status()
    meta = BeautifulSoup(r.text, "html.parser").find("meta", {"name": "csrf-token"})
    if not meta:
        raise RuntimeError(
            "Could not find CSRF token on CareerPlug. "
            "Your session may have expired — please reload app.careerplug.com in Chrome and try again."
        )

    return httpx.AsyncClient(
        base_url=_BASE,
        cookies={"_career_plug_ats_session": session_cookie},
        headers={
            "X-CSRF-Token": meta["content"],
            "Accept": "text/html, */*",
            "X-Requested-With": "XMLHttpRequest",
        },
        follow_redirects=True,
    )


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


async def _fetch_html(path: str, params: dict) -> str:
    r = await _get_client().get(path, params=params)
    r.raise_for_status()
    return r.text


def _parse_jobs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select("tr.job.index-item"):
        id_input = row.select_one("td.text-center input[data-id]")
        a_title = row.select_one("td.max-width a.name")
        badge = row.select_one("td.max-width span.badge")
        location = row.select_one("td.location")
        count_td = row.select_one("td.text-capitalize:not(.location)")
        min_width_tds = row.select("td.min-width")
        posted_date = min_width_tds[1].get_text(strip=True) if len(min_width_tds) >= 2 else None
        count_text = count_td.get_text(strip=True) if count_td else None
        results.append({
            "id": id_input["data-id"] if id_input else None,
            "title": a_title.get_text(strip=True) if a_title else None,
            "job_url": a_title["href"] if a_title else None,
            "status": badge.get_text(strip=True) if badge else None,
            "location": location.get_text(strip=True) if location else None,
            "applicant_count": int(count_text) if count_text and count_text.isdigit() else None,
            "posted_date": posted_date,
        })
    return results


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


@mcp.tool
async def list_jobs(
    page: int = 1,
    status: int | None = None,
    refresh: bool = False,
) -> list:
    """List jobs from CareerPlug. status: None=all, 0=draft, 1=active, 2=closed, 3=passive."""
    params = {
        "page": page,
        "refresh": "1" if refresh else "",
        "status": "" if status is None else status,
    }
    html = await _fetch_html("/manage/jobs/list", params)
    return _parse_jobs(html)


@mcp.tool
async def list_applicants(
    page: int = 1,
    status: str = "active",
    job_id: int | None = None,
) -> list:
    """List applicants. status: active|new|in_process|disqualified|hired|pipeline|inactive. job_id filters to a specific job."""
    if job_id is not None:
        params = {
            "app_link": "true",
            "apps_hiring_pipeline_step": "all",
            "apps_j[]": job_id,
            "apps_job_status": "all",
            "page": page,
        }
    else:
        params = {"page": page, "status": status}
    html = await _fetch_html("/manage/apps/list", params)
    return _parse_applicants(html)


if __name__ == "__main__":
    mcp.run()
