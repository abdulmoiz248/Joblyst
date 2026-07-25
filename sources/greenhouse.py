"""Greenhouse Job Board API client. Structured JSON, no HTML scraping needed."""
import logging

import requests
from dateutil import parser as dateparser

from normalize import normalizeJob

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def fetch_jobs(board_token, company_name):
    url = BASE_URL.format(board_token=board_token) + "?content=true"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            logging.warning(f"greenhouse[{company_name}] returned {response.status_code}")
            return []
        data = response.json()
    except Exception as e:
        logging.warning(f"greenhouse[{company_name}] error: {e}")
        return []

    jobs = []
    for raw in data.get("jobs", []):
        try:
            title = raw.get("title", "")
            location = (raw.get("location") or {}).get("name", "")
            description = raw.get("content", "")
            applyLink = raw.get("absolute_url", "")

            posted_date = None
            if raw.get("updated_at"):
                posted_date = dateparser.isoparse(raw["updated_at"]).date()

            job = normalizeJob(title, company_name, location, description, applyLink,
                                posted_date=posted_date)
            if job:
                jobs.append(job)
        except Exception as e:
            logging.debug(f"greenhouse[{company_name}] job parse error: {e}")
            continue

    logging.info(f"greenhouse[{company_name}] jobs found: {len(jobs)}")
    return jobs
