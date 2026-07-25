"""Lever Postings API client. Kept as an available source even though none of our
default seed companies landed on Lever (many well-known Lever users publish huge,
slow-to-transfer payloads) - add a company here once you find a working slug."""
import logging
from datetime import datetime

import requests

from normalize import normalizeJob

BASE_URL = "https://api.lever.co/v0/postings/{company}"


def fetch_jobs(company_slug, company_name):
    url = BASE_URL.format(company=company_slug) + "?mode=json"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logging.warning(f"lever[{company_name}] returned {response.status_code}")
            return []
        data = response.json()
    except Exception as e:
        logging.warning(f"lever[{company_name}] error: {e}")
        return []

    jobs = []
    for raw in data:
        try:
            title = raw.get("text", "")
            location = (raw.get("categories") or {}).get("location", "")
            description = raw.get("descriptionPlain") or raw.get("description", "")
            applyLink = raw.get("hostedUrl", "") or raw.get("applyUrl", "")

            posted_date = None
            if raw.get("createdAt"):
                posted_date = datetime.fromtimestamp(raw["createdAt"] / 1000).date()

            job = normalizeJob(title, company_name, location, description, applyLink,
                                posted_date=posted_date)
            if job:
                jobs.append(job)
        except Exception as e:
            logging.debug(f"lever[{company_name}] job parse error: {e}")
            continue

    logging.info(f"lever[{company_name}] jobs found: {len(jobs)}")
    return jobs
