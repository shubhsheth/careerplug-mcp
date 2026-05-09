import os
import fastmcp
import httpx
from bs4 import BeautifulSoup

mcp = fastmcp.FastMCP("careerplug")

_BASE = "https://app.careerplug.com"
_SESSION_COOKIE = os.environ.get("CAREERPLUG_SESSION_COOKIE", "")
_CSRF_TOKEN = os.environ.get("CAREERPLUG_CSRF_TOKEN", "")

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        if not _SESSION_COOKIE or not _CSRF_TOKEN:
            raise RuntimeError(
                "Set CAREERPLUG_SESSION_COOKIE and CAREERPLUG_CSRF_TOKEN env vars before starting the server."
            )
        _client = httpx.AsyncClient(
            base_url=_BASE,
            cookies={"_career_plug_ats_session": _SESSION_COOKIE},
            headers={
                "X-CSRF-Token": _CSRF_TOKEN,
                "Accept": "text/html, */*",
                "X-Requested-With": "XMLHttpRequest",
            },
            follow_redirects=True,
        )
    return _client


async def _fetch_html(path: str, params: dict) -> str:
    r = await _get_client().get(path, params=params)
    r.raise_for_status()
    return r.text


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
async def get_list_html(path: str, params: dict | None = None) -> str:
    """Debug tool: fetch raw HTML from a CareerPlug list endpoint. E.g. path='/manage/jobs/list', params={'page': 1}."""
    html = await _fetch_html(path, params or {})
    return html


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
    return []  # jobs selector discovery pending — call get_list_html to inspect HTML


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
