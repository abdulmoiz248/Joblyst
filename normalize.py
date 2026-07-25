"""Shared job-shape helpers used by every source module."""
import re


def safeText(el):
    return el.get_text(strip=True) if el else ""


def cleanHtml(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalizeJob(title, company, location, description, applyLink, email=None,
                  posted_date=None, deadline=None):
    """Build the canonical job dict every filter/scorer/notifier downstream expects.

    posted_date/deadline are `datetime.date` objects when known (used by freshness.py),
    left as None when a source can't supply them.
    """
    if not title or not company:
        return None
    title = cleanHtml(title).strip()
    company = cleanHtml(company).strip()
    location = cleanHtml(location).strip() if location else "unspecified"
    description = cleanHtml(description).strip()

    return {
        "title": title.lower(),
        "company": company,
        "location": location.lower(),
        "description": description.lower(),
        "applyLink": applyLink,
        "email": email,
        "id": f"{company.lower()[:30]}-{title.lower()[:40]}",
        "posted_date": posted_date,
        "deadline": deadline,
    }
