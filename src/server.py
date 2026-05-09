import fastmcp
from playwright.async_api import async_playwright, Page

mcp = fastmcp.FastMCP("careerplug")

_CDP_URL = "http://localhost:9222"
_BASE = "https://app.careerplug.com"


async def _open_page(url: str) -> tuple:
    """Connect to existing Chrome via CDP and open url. Returns (playwright, browser, page)."""
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(_CDP_URL)
    context = browser.contexts[0]
    page = await context.new_page()
    await page.goto(url, wait_until="networkidle", timeout=30_000)
    return pw, browser, page


async def _close(pw, browser, page: Page) -> None:
    await page.close()
    await pw.stop()


@mcp.tool
async def get_page_html(url: str) -> str:
    """Return the fully rendered HTML of any CareerPlug page. Temporary debug tool for DOM inspection."""
    pw, browser, pg = await _open_page(url)
    try:
        return await pg.content()
    finally:
        await _close(pw, browser, pg)


@mcp.tool
async def list_jobs(
    page: int = 1,
    status: int | None = None,
    refresh: bool = False,
) -> list:
    """List jobs from CareerPlug. status: None=all, 0=draft, 1=active, 2=closed, 3=passive."""
    status_val = "" if status is None else str(status)
    refresh_val = "1" if refresh else ""
    url = f"{_BASE}/manage/jobs?page={page}&refresh={refresh_val}&status={status_val}"
    pw, browser, pg = await _open_page(url)
    try:
        return []  # extraction logic deferred until DOM is inspected
    finally:
        await _close(pw, browser, pg)


@mcp.tool
async def list_applicants(
    page: int = 1,
    status: str = "active",
    job_id: int | None = None,
) -> list:
    """List applicants. status: active|new|in_process|disqualified|hired|pipeline|inactive. job_id filters to a specific job."""
    if job_id is not None:
        url = (
            f"{_BASE}/manage/apps"
            f"?app_link=true&apps_hiring_pipeline_step=all"
            f"&apps_j[]={job_id}&apps_job_status=all&page={page}"
        )
    else:
        url = f"{_BASE}/manage/apps?page={page}&status={status}"
    pw, browser, pg = await _open_page(url)
    try:
        return []  # extraction logic deferred until DOM is inspected
    finally:
        await _close(pw, browser, pg)


if __name__ == "__main__":
    mcp.run()
