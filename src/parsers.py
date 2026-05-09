from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString


def parse_applicant_details(html: str) -> dict:
    """Extract full applicant profile from a ``/manage/apps/{id}`` HTML page.

    Args:
        html: Raw HTML string returned by the endpoint.

    Returns:
        Dict with keys: ``name``, ``email``, ``phone``, ``applied_date``,
        ``applied_via``, ``job_title``, ``job_location``, ``current_step``,
        ``hiring_steps``, ``is_duplicate``. Fields that cannot be found are
        ``None``; ``hiring_steps`` defaults to an empty list.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Name: first text node inside the name div (siblings are rating/tag widgets)
    name = None
    name_div = soup.select_one(".profile-show__applicant-name")
    if name_div:
        name = next(
            (t.strip() for t in name_div.children if isinstance(t, NavigableString) and t.strip()),
            None,
        )

    email_el = soup.select_one(".profile-show__email a")
    email = email_el.get_text(strip=True) if email_el else None

    phone_el = soup.select_one(".profile-show__phone a")
    phone = phone_el.get_text(strip=True) if phone_el else None

    # "Applied on MM/DD/YYYY via Source" → split on " via " once
    applied_date = applied_via = None
    activated_el = soup.select_one(".profile-show__job-activated")
    if activated_el:
        text = activated_el.get_text(strip=True)
        # strip leading "Applied on "
        if text.startswith("Applied on "):
            text = text[len("Applied on "):]
        if " via " in text:
            applied_date, applied_via = text.split(" via ", 1)
        else:
            applied_date = text

    # "Applied for: TITLE, LOCATION" → rsplit on ", " once so titles with commas survive
    job_title = job_location = None
    job_el = soup.select_one(".profile-show__job-name")
    if job_el:
        text = job_el.get_text(strip=True)
        if text.startswith("Applied for: "):
            text = text[len("Applied for: "):]
        if ", " in text:
            job_title, job_location = text.rsplit(", ", 1)
        else:
            job_title = text

    # Hiring steps: each row in #accordion has a status icon and a card-title
    hiring_steps = []
    current_step = None
    for row in soup.select("#accordion .d-flex.flex-row"):
        title_el = row.select_one(".overview-accordion__hiring-step .card-title")
        if not title_el:
            continue
        step_name = title_el.get_text(strip=True)
        icon = row.select_one(".overview-accordion__status i.fa-stack-2x")
        if icon:
            classes = icon.get("class", [])
            if "current" in classes:
                status = "current"
                current_step = step_name
            elif "future" in classes:
                status = "future"
            else:
                status = "completed"
        else:
            status = "completed"
        hiring_steps.append({"name": step_name, "status": status})

    # is_duplicate: data attribute on the deactivate drawer element
    is_duplicate = None
    dup_el = soup.select_one("[data-deactivate-drawer-duplicate]")
    if dup_el:
        is_duplicate = dup_el["data-deactivate-drawer-duplicate"].lower() == "true"

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "applied_date": applied_date,
        "applied_via": applied_via,
        "job_title": job_title,
        "job_location": job_location,
        "current_step": current_step,
        "hiring_steps": hiring_steps,
        "is_duplicate": is_duplicate,
    }


def parse_applicant_documents(html: str) -> list[dict]:
    """Extract uploaded documents from a ``/manage/apps/{id}?tab=documents`` page.

    Args:
        html: Raw HTML string returned by the endpoint.

    Returns:
        List of dicts with keys: ``name``, ``attachment_id``, ``download_url``,
        ``uploaded_date``. Empty list if no documents are present.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    container = soup.select_one("#profile-applicant-documents")
    if not container:
        return results
    for doc in container.select("[id^='profile-applicant-document-has_attachment_']"):
        name_el = doc.select_one(".profile-applicant-documents__title")
        download_el = doc.select_one(".profile-applicant-documents__download")
        date_el = doc.select_one(".form-text.text-muted")

        download_url = download_el["href"] if download_el else None
        attachment_id = None
        if download_url:
            try:
                attachment_id = int(download_url.rstrip("/").rsplit("/", 1)[-1])
            except (ValueError, IndexError):
                pass

        uploaded_date = None
        if date_el:
            text = date_el.get_text(strip=True)
            if text.startswith("Uploaded on "):
                uploaded_date = text[len("Uploaded on "):]
            else:
                uploaded_date = text

        results.append({
            "name": name_el.get_text(strip=True) if name_el else None,
            "attachment_id": attachment_id,
            "download_url": download_url,
            "uploaded_date": uploaded_date,
        })
    return results


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
