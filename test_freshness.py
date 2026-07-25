"""Unit tests for freshness/deadline parsing and the staleness policy."""
from datetime import date, timedelta

import freshness


def test_extract_deadline_relative_closes_in():
    posted = date(2026, 7, 1)
    deadline = freshness.extract_deadline("Hurry, this posting closes in 5 days.", posted)
    assert deadline == posted + timedelta(days=5)


def test_extract_deadline_relative_no_longer_accepting():
    posted = date(2026, 7, 1)
    deadline = freshness.extract_deadline(
        "We will no longer be accepting applications after 4 days.", posted)
    assert deadline == posted + timedelta(days=4)


def test_extract_deadline_explicit_date():
    posted = date(2026, 7, 1)
    deadline = freshness.extract_deadline("Please apply by August 15, 2026.", posted)
    assert deadline == date(2026, 8, 15)


def test_extract_deadline_none_when_absent():
    assert freshness.extract_deadline("A totally normal job description.", date.today()) is None


def test_extract_posted_date_relative_text():
    parsed = freshness.extract_posted_date("Posted 3 days ago in Remote")
    assert parsed == date.today() - timedelta(days=3)


def test_is_stale_when_deadline_passed():
    job = {"title": "x", "deadline": date.today() - timedelta(days=1), "posted_date": None}
    assert freshness.is_stale(job, {}) is True


def test_is_stale_when_too_old_without_deadline():
    job = {"title": "x", "deadline": None, "posted_date": date.today() - timedelta(days=30)}
    assert freshness.is_stale(job, {"maxJobAgeDays": 21}) is True


def test_not_stale_when_fresh():
    job = {"title": "x", "deadline": date.today() + timedelta(days=5),
           "posted_date": date.today() - timedelta(days=2)}
    assert freshness.is_stale(job, {"maxJobAgeDays": 21}) is False


def test_not_stale_when_no_signals_available():
    job = {"title": "x", "deadline": None, "posted_date": None}
    assert freshness.is_stale(job, {"maxJobAgeDays": 21}) is False
