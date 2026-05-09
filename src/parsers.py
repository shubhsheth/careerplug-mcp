from bs4 import BeautifulSoup


def parse_jobs(html: str) -> list[dict]:
    """Extract job records from a ``/manage/jobs/list`` HTML response.

    Args:
        html: Raw HTML string returned by the endpoint.

    Returns:
        List of dicts with keys: ``id``, ``title``, ``job_url``, ``status``,
        ``location``, ``applicant_count``, ``posted_date``. Fields that cannot
        be found in the markup are ``None`` rather than raising an error.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select("tr.job.index-item"):
        id_input = row.select_one("td.text-center input[data-id]")
        a_title = row.select_one("td.max-width a.name")
        badge = row.select_one("td.max-width span.badge")
        location = row.select_one("td.location")
        # Both applicant count and location use td.text-capitalize; the
        # :not(.location) exclusion disambiguates them.
        count_td = row.select_one("td.text-capitalize:not(.location)")
        # The jobs table has two min-width columns; posted date is consistently
        # the second (index 1).
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


def parse_applicants(html: str) -> list[dict]:
    """Extract applicant records from a ``/manage/apps/list`` HTML response.

    Args:
        html: Raw HTML string returned by the endpoint.

    Returns:
        List of dicts with keys: ``id``, ``name``, ``profile_url``,
        ``job_title``, ``job_url``, ``location``, ``current_step``. Fields
        that cannot be found in the markup are ``None``.
    """
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
