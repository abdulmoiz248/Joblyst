"""Unit tests for ATS/Firecrawl source modules, using mocked HTTP responses so
these run offline and don't depend on any live company's API staying up."""
import os
from datetime import date
from unittest.mock import Mock, patch

from sources import ashby, firecrawl_source, greenhouse, lever


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


@patch("sources.greenhouse.requests.get")
def test_greenhouse_fetch_jobs(mock_get):
    mock_get.return_value = FakeResponse(200, {
        "jobs": [{
            "title": "New Grad Software Engineer",
            "location": {"name": "Remote"},
            "content": "<p>Build things.</p>",
            "absolute_url": "https://example.com/apply/1",
            "updated_at": "2026-07-20T10:00:00-05:00",
        }]
    })

    jobs = greenhouse.fetch_jobs("acme", "Acme")
    assert len(jobs) == 1
    job = jobs[0]
    assert job["company"] == "Acme"
    assert job["title"] == "new grad software engineer"
    assert job["posted_date"] == date(2026, 7, 20)


@patch("sources.greenhouse.requests.get")
def test_greenhouse_handles_error_status(mock_get):
    mock_get.return_value = FakeResponse(404)
    assert greenhouse.fetch_jobs("nope", "Nope") == []


@patch("sources.lever.requests.get")
def test_lever_fetch_jobs(mock_get):
    mock_get.return_value = FakeResponse(200, json_data=[{
        "text": "Backend Developer",
        "categories": {"location": "New York"},
        "descriptionPlain": "Ship backend services.",
        "hostedUrl": "https://jobs.lever.co/acme/1",
        "createdAt": 1753000000000,
    }])

    jobs = lever.fetch_jobs("acme", "Acme")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "backend developer"
    assert jobs[0]["posted_date"] is not None


@patch("sources.ashby.requests.get")
def test_ashby_fetch_jobs_skips_unlisted(mock_get):
    mock_get.return_value = FakeResponse(200, {
        "jobs": [
            {
                "title": "Frontend Engineer",
                "location": "Remote - US",
                "descriptionPlain": "React all day.",
                "jobUrl": "https://jobs.ashbyhq.com/acme/1",
                "publishedAt": "2026-07-15T00:00:00.000Z",
                "isListed": True,
            },
            {
                "title": "Old Closed Role",
                "location": "Remote",
                "descriptionPlain": "n/a",
                "jobUrl": "https://jobs.ashbyhq.com/acme/2",
                "isListed": False,
            },
        ]
    })

    jobs = ashby.fetch_jobs("acme", "Acme")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "frontend engineer"


@patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test-key"})
@patch("sources.firecrawl_source.requests.post")
def test_firecrawl_extracts_jobs(mock_post):
    mock_post.return_value = FakeResponse(200, {
        "data": {
            "json": {
                "jobs": [{
                    "title": "Software Engineer",
                    "location": "Worldwide - Remote",
                    "description": "Work on cool stuff.",
                    "applyUrl": "https://micro1.ai/apply/1",
                    "postedOrDeadlineText": "Posted 2 days ago",
                }]
            }
        }
    })

    jobs = firecrawl_source.fetch_jobs("Micro1", "https://www.micro1.ai/experts/opportunities")
    assert len(jobs) == 1
    assert jobs[0]["company"] == "Micro1"
    assert "posted 2 days ago" in jobs[0]["description"]


def test_firecrawl_skips_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        assert firecrawl_source.fetch_jobs("Micro1", "https://example.com") == []
