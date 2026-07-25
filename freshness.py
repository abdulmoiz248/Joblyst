"""
Freshness checks so Joblyst never surfaces a job that's already dead or about to be.

Two independent signals feed into staleness:
  - posted_date: when the ATS/source says the job went live (structured field when
    available, best-effort "posted N days ago" text otherwise).
  - deadline: an explicit or relative "apply by" date parsed out of the description.

A job is stale if its deadline has passed, or (absent a deadline) if it's older than
config["maxJobAgeDays"].
"""
import logging
import re
from datetime import date, datetime, timedelta

from dateutil import parser as dateparser

_RELATIVE_DEADLINE_PATTERNS = [
    r'(?:closes?|expires?|closing)\s+in\s+(\d+)\s+days?',
    r'(\d+)\s+days?\s+(?:left|remaining)\s+to\s+apply',
    r'no longer (?:be )?accept(?:ing)? applications after\s+(\d+)\s+days?',
    r'this (?:posting|job|position|listing) will (?:expire|close)\s+in\s+(\d+)\s+days?',
    r'apply within\s+(\d+)\s+days?',
]

_EXPLICIT_DEADLINE_PATTERNS = [
    r'apply by[:\s]+([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)',
    r'applications? clos(?:e|ing)(?: on)?[:\s]+([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)',
    r'deadline(?: to apply)?[:\s]+([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)',
    r'closing date[:\s]+([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)',
]

_POSTED_RELATIVE_PATTERN = r'posted\s+(\d+)\s+days?\s+ago'


def extract_posted_date(description, fallback=None):
    """Best-effort 'posted N days ago' text parse, for sources with no structured date."""
    if not description:
        return fallback
    match = re.search(_POSTED_RELATIVE_PATTERN, description, re.IGNORECASE)
    if match:
        return date.today() - timedelta(days=int(match.group(1)))
    return fallback


def extract_deadline(description, posted_date=None):
    """Parse an explicit or relative application deadline out of free-text description."""
    if not description:
        return None

    for pattern in _RELATIVE_DEADLINE_PATTERNS:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            anchor = posted_date or date.today()
            return anchor + timedelta(days=int(match.group(1)))

    reference = posted_date or date.today()
    referenceDatetime = datetime.combine(reference, datetime.min.time())
    for pattern in _EXPLICIT_DEADLINE_PATTERNS:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            try:
                parsed = dateparser.parse(match.group(1), default=referenceDatetime, fuzzy=False)
            except (ValueError, OverflowError):
                continue
            parsed_date = parsed.date()
            # Guard against garbage parses (e.g. a stray number matched as a day).
            if abs((parsed_date - reference).days) > 400:
                continue
            return parsed_date

    return None


def enrich(job):
    """Fill in job['posted_date']/job['deadline'] from description text when a source
    didn't already supply them as structured fields."""
    job["posted_date"] = job.get("posted_date") or extract_posted_date(job.get("description"))
    job["deadline"] = job.get("deadline") or extract_deadline(job.get("description"), job.get("posted_date"))
    return job


def is_stale(job, config):
    today = date.today()
    deadline = job.get("deadline")
    if deadline and deadline < today:
        logging.debug(f"stale (deadline passed) -> {job['title']} (deadline {deadline})")
        return True

    posted = job.get("posted_date")
    max_age = config.get("maxJobAgeDays", 21)
    if posted and (today - posted).days > max_age:
        logging.debug(f"stale (too old) -> {job['title']} (posted {posted})")
        return True

    return False
