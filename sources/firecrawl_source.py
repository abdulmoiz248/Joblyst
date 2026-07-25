"""Firecrawl-based extraction for career pages that aren't on a standard ATS
(custom in-house pages like Google/Microsoft/Amazon careers, Micro1's opportunities
page, and the existing custom Pakistani company career pages).

Replaces the old brittle `soup.select("div[class*='job']...")` CSS-selector guessing
with a schema-driven extraction call, so a career page redesign doesn't silently
break the source the way it used to.
"""
import logging
import os

import requests

from normalize import normalizeJob

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"

_JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "applyUrl": {"type": "string"},
                    "postedOrDeadlineText": {
                        "type": "string",
                        "description": "Any visible text indicating when this job was posted, "
                                        "or when applications close/expire (e.g. 'Posted 3 days ago', "
                                        "'Apply by March 5', 'Closes in 5 days')."
                    },
                },
                "required": ["title"],
            },
        }
    },
    "required": ["jobs"],
}


def fetch_jobs(company_name, career_page_url):
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        logging.warning(f"firecrawl[{company_name}] skipped: FIRECRAWL_API_KEY not set")
        return []

    payload = {
        "url": career_page_url,
        "formats": [{"type": "json", "schema": _JOB_SCHEMA}],
        "onlyMainContent": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(FIRECRAWL_SCRAPE_URL, json=payload, headers=headers, timeout=60)
        if response.status_code != 200:
            logging.warning(f"firecrawl[{company_name}] returned {response.status_code}: {response.text[:200]}")
            return []
        body = response.json()
    except Exception as e:
        logging.warning(f"firecrawl[{company_name}] error: {e}")
        return []

    data = body.get("data", {})
    # API contract for where structured JSON-mode output lands isn't fully pinned down
    # in Firecrawl's public docs at time of writing - check both known field names.
    extracted = data.get("json") or data.get("extract") or {}
    raw_jobs = extracted.get("jobs", []) if isinstance(extracted, dict) else []

    if not raw_jobs:
        logging.info(f"firecrawl[{company_name}] no jobs extracted")
        return []

    jobs = []
    for raw in raw_jobs:
        try:
            title = raw.get("title", "")
            location = raw.get("location", "")
            description = raw.get("description", "") or title
            postedOrDeadline = raw.get("postedOrDeadlineText", "")
            if postedOrDeadline:
                description = f"{description} {postedOrDeadline}"
            applyUrl = raw.get("applyUrl") or career_page_url

            job = normalizeJob(title, company_name, location, description, applyUrl)
            if job:
                jobs.append(job)
        except Exception as e:
            logging.debug(f"firecrawl[{company_name}] job parse error: {e}")
            continue

    logging.info(f"firecrawl[{company_name}] jobs found: {len(jobs)}")
    return jobs
