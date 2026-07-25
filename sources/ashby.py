"""Ashby Job Board API client. Structured JSON, no HTML scraping needed."""
import logging

import requests
from dateutil import parser as dateparser

from normalize import normalizeJob

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{org}"


def fetch_jobs(org_slug, company_name):
    url = BASE_URL.format(org=org_slug)
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            logging.warning(f"ashby[{company_name}] returned {response.status_code}")
            return []
        data = response.json()
    except Exception as e:
        logging.warning(f"ashby[{company_name}] error: {e}")
        return []

    jobs = []
    for raw in data.get("jobs", []):
        try:
            if raw.get("isListed") is False:
                continue

            title = raw.get("title", "")
            location = raw.get("location", "")
            description = raw.get("descriptionPlain") or raw.get("descriptionHtml", "")
            applyLink = raw.get("jobUrl") or raw.get("applyUrl", "")

            posted_date = None
            if raw.get("publishedAt"):
                posted_date = dateparser.isoparse(raw["publishedAt"]).date()

            job = normalizeJob(title, company_name, location, description, applyLink,
                                posted_date=posted_date)
            if job:
                jobs.append(job)
        except Exception as e:
            logging.debug(f"ashby[{company_name}] job parse error: {e}")
            continue

    logging.info(f"ashby[{company_name}] jobs found: {len(jobs)}")
    return jobs
