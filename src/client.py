import httpx
import browser_cookie3
from bs4 import BeautifulSoup

_BASE = "https://app.careerplug.com"

_client: httpx.AsyncClient | None = None


def _find_session_cookie() -> str:
    """Search supported browsers for the CareerPlug session cookie.

    Tries Chrome, Firefox, Brave, Edge, and Chromium in order, stopping at the
    first browser that yields the ``_career_plug_ats_session`` cookie for the
    ``.careerplug.com`` domain.

    Returns:
        The raw cookie value string.

    Raises:
        RuntimeError: If no browser yields the session cookie. The message
            instructs the user to log in via the browser before retrying.
    """
    browsers = [
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
        ("Brave", browser_cookie3.brave),
        ("Edge", browser_cookie3.edge),
        ("Chromium", browser_cookie3.chromium),
    ]
    for _name, loader in browsers:
        try:
            cookiejar = loader(domain_name=".careerplug.com")
            value = next(
                (c.value for c in cookiejar if c.name == "_career_plug_ats_session"),
                None,
            )
            if value:
                return value
        except Exception:
            # browser_cookie3 raises various exceptions when a browser isn't
            # installed or its cookie DB is locked; skip and try the next browser.
            continue
    raise RuntimeError(
        "No CareerPlug session found in Chrome, Firefox, or Brave. "
        "Please log into app.careerplug.com in your browser and try again."
    )


def _build_client() -> httpx.AsyncClient:
    """Bootstrap the shared HTTP client with auth credentials from the browser.

    Reads the session cookie via ``_find_session_cookie``, then makes one
    synchronous GET to ``/manage/jobs`` to extract the CSRF token from the
    ``<meta name="csrf-token">`` tag. This synchronous bootstrap is intentional:
    it must complete before the async client is returned, and FastMCP may call
    tool functions before any async context is available.

    Returns:
        An ``httpx.AsyncClient`` pre-configured with the session cookie,
        CSRF token header, and ``X-Requested-With: XMLHttpRequest`` (required
        so CareerPlug returns HTML fragments instead of login redirects).

    Raises:
        RuntimeError: If the CSRF token cannot be found, indicating an expired
            or invalid session.
    """
    session_cookie = _find_session_cookie()

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
            # Without this header, CareerPlug returns a full-page login redirect
            # instead of the HTML table fragment the tools expect.
            "X-Requested-With": "XMLHttpRequest",
        },
        follow_redirects=True,
    )


def _get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, initializing it on first call.

    The client is constructed lazily so that authentication I/O only happens
    when a tool is first invoked, not at import time.

    Returns:
        The module-level ``_client`` singleton.
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


async def fetch_html(path: str, params: dict) -> str:
    """Fetch a CareerPlug HTML fragment from the given path.

    Args:
        path: URL path relative to ``_BASE`` (e.g. ``/manage/jobs/list``).
        params: Query parameters dict passed directly to httpx.

    Returns:
        The raw HTML response body as a string.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
    """
    r = await _get_client().get(path, params=params)
    r.raise_for_status()
    return r.text
