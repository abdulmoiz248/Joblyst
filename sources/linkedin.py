"""LinkedIn guest-API scraper. Broadened from Lahore-only to worldwide + remote."""
import logging
import time

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from normalize import normalizeJob, safeText

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SEARCH_TERMS = [
    "software engineer", "junior developer", "python developer", "frontend developer",
    "backend developer", "full stack developer", "web developer", "react developer",
    "node developer", "new grad software engineer", "graduate software engineer",
    "associate software engineer", "software engineer intern",
]

LOCATIONS = [
    "Worldwide", "Remote", "United States", "United Kingdom", "Canada", "Germany", "Pakistan",
]


def fetch_jobs():
    logging.info("scraping linkedin (guest API)")
    jobs = []

    for term in SEARCH_TERMS:
        for location in LOCATIONS:
            try:
                url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&location={quote_plus(location)}&f_TPR=r86400&start=0"
                response = requests.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    logging.warning(f"linkedin returned {response.status_code} for {term} in {location}")
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select("div.base-card, li.result-card, div.job-search-card")
                for card in cards:
                    try:
                        titleEl = card.select_one("h3.base-search-card__title")
                        companyEl = card.select_one("h4.base-search-card__subtitle")
                        locationEl = card.select_one("span.job-search-card__location")
                        linkEl = card.select_one("a.base-card__full-link")

                        title = safeText(titleEl)
                        company = safeText(companyEl)
                        loc = safeText(locationEl)
                        link = linkEl.get("href", "") if linkEl else ""

                        if title and company:
                            description = f"{title} position at {company}. Location: {loc}"
                            job = normalizeJob(title, company, loc, description, link)
                            if job and job["id"] not in [j["id"] for j in jobs]:
                                jobs.append(job)
                    except Exception as e:
                        logging.debug(f"Error parsing LinkedIn card: {e}")
                        continue
                time.sleep(1)
            except Exception as e:
                logging.warning(f"linkedin error for '{term}' in '{location}': {e}")
                continue

    unique_jobs = []
    seen_ids = set()
    for job in jobs:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            unique_jobs.append(job)
    logging.info(f"linkedin jobs found: {len(unique_jobs)}")
    return unique_jobs
