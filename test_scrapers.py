"""Test script to debug job scrapers"""
import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def test_rozee_xhr():
    """Test Rozee XHR/AJAX endpoints"""
    print("=" * 60)
    print("TESTING ROZEE XHR ENDPOINTS")
    print("=" * 60)
    
    # Common XHR endpoints patterns
    xhr_urls = [
        "https://www.rozee.pk/job/ajaxsearch",
        "https://www.rozee.pk/ajax/job/search",
        "https://www.rozee.pk/job/jsearch/q/software%20engineer/fc/1/fpn/1/ajax/1",
        "https://www.rozee.pk/job/jsearch/q/software%20engineer/fc/1?ajax=1",
    ]
    
    for url in xhr_urls:
        print(f"\nTrying: {url}")
        try:
            xhr_headers = {
                **HEADERS,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
            r = requests.get(url, headers=xhr_headers, timeout=15)
            print(f"Status: {r.status_code}, Length: {len(r.text)}")
            if r.status_code == 200 and len(r.text) < 5000:
                print(f"Response: {r.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")


def test_jobsense():
    """Test JobSense.pk - another Pakistani job board"""
    print("\n" + "=" * 60)
    print("TESTING ALTERNATIVE: BAYROZGAR.COM")
    print("=" * 60)
    
    url = "https://www.bayrozgar.com/jobs/software-developer"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"Status: {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Look for job cards
        cards = soup.select("div.job-item, div.job-card, article, div.listing")
        print(f"Job cards found: {len(cards)}")
        
        # Look for job links
        job_links = soup.find_all("a", href=lambda x: x and "job" in x.lower())
        print(f"Job links: {len(job_links)}")
        for link in job_links[:5]:
            print(f"  - {link.get_text(strip=True)[:50]}")
    except Exception as e:
        print(f"Error: {e}")


def test_glassdoor():
    """Test Glassdoor Pakistan"""
    print("\n" + "=" * 60)
    print("TESTING GLASSDOOR PAKISTAN")
    print("=" * 60)
    
    url = "https://www.glassdoor.com/Job/lahore-software-engineer-jobs-SRCH_IL.0,6_IC3232781_KO7,24.htm"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            jobs = soup.select("li[data-test='jobListing'], div.job-listing")
            print(f"Job listings: {len(jobs)}")
    except Exception as e:
        print(f"Error: {e}")


def test_google_jobs():
    """Test Google Jobs search via SerpAPI alternative or direct"""
    print("\n" + "=" * 60)
    print("TESTING LINKEDIN API/DIRECT")
    print("=" * 60)
    
    # LinkedIn public job search
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=software%20engineer&location=Pakistan&start=0"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"Status: {r.status_code}")
        print(f"Content Length: {len(r.text)}")
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("div.base-card, li.result-card")
            print(f"LinkedIn job cards: {len(cards)}")
            
            for card in cards[:5]:
                title = card.select_one("h3.base-search-card__title")
                company = card.select_one("h4.base-search-card__subtitle")
                location = card.select_one("span.job-search-card__location")
                link = card.select_one("a.base-card__full-link")
                
                if title:
                    print(f"\nTitle: {title.get_text(strip=True)}")
                if company:
                    print(f"Company: {company.get_text(strip=True)}")
                if location:
                    print(f"Location: {location.get_text(strip=True)}")
                if link:
                    print(f"Link: {link.get('href', '')[:80]}")
    except Exception as e:
        print(f"Error: {e}")


def test_rozee_rss():
    """Test if Rozee has RSS feed"""
    print("\n" + "=" * 60)
    print("TESTING ROZEE RSS FEED")
    print("=" * 60)
    
    rss_urls = [
        "https://www.rozee.pk/rss/jobs",
        "https://www.rozee.pk/feed",
        "https://www.rozee.pk/jobs.rss",
        "https://www.rozee.pk/job/rss/q/software-engineer",
    ]
    
    for url in rss_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            print(f"{url}: {r.status_code}")
            if r.status_code == 200 and "xml" in r.headers.get("content-type", "").lower():
                print("  Found RSS!")
                print(f"  Sample: {r.text[:300]}")
        except:
            pass


def test_jobee():
    """Test Jobee.pk"""
    print("\n" + "=" * 60)
    print("TESTING JOBEE.PK")
    print("=" * 60)
    
    url = "https://www.jobee.pk/jobs/software-developer"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            jobs = soup.select("div.job, article.job, div.listing")
            print(f"Jobs found: {len(jobs)}")
    except Exception as e:
        print(f"Error: {e}")


def test_pasha_jobs():
    """Test Pakistan Software Houses Association jobs"""
    print("\n" + "=" * 60)
    print("TESTING PASHA JOBS (Pakistan IT Industry)")
    print("=" * 60)
    
    url = "https://pasha.org.pk/jobs/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Look for any job listings
            links = soup.find_all("a")
            job_links = [l for l in links if any(kw in l.get_text().lower() for kw in ["developer", "engineer", "software"])]
            print(f"Developer job links: {len(job_links)}")
            for l in job_links[:5]:
                print(f"  - {l.get_text(strip=True)[:50]}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_rozee_xhr()
    test_rozee_rss()
    test_google_jobs()  # This tests LinkedIn API
    test_jobee()
    test_pasha_jobs()
