import json
import requests
import numpy as np
import logging
import re
import time
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from urllib.parse import quote_plus, urljoin
from dotenv import load_dotenv
from job_history import JobHistory

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.info("starting joblyst")

# Load model
model = SentenceTransformer("all-MiniLM-L6-v2")
logging.info("sentence transformer loaded")

# Load config files
with open("cv.json", encoding="utf-8") as f:
    cv = json.load(f)

with open("companies.json", encoding="utf-8") as f:
    companies = json.load(f)["companies"]

with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

allowedRoles = [r.lower() for r in config["allowedRoles"]]
allowedLocations = [l.lower() for l in config["allowedLocations"]]
minScore = config.get("minScore", 40)
discordWebhook = os.getenv("DISCORD_WEBHOOK")

if not discordWebhook:
    raise ValueError("DISCORD_WEBHOOK environment variable not set")

# Prepare CV skills list once - handle both formats
cvSkills = []
if "skills" in cv:
    if isinstance(cv["skills"], list):
        # New format: direct list of skill strings
        cvSkills.extend([s.lower() for s in cv["skills"] if isinstance(s, str)])
    else:
        # Old format: dict with items
        for skill in cv["skills"].get("items", []):
            cvSkills.append(skill.get("name", "").lower())
            keywords = skill.get("keywords", [])
            if isinstance(keywords, list):
                cvSkills.extend([k.lower() for k in keywords])

# Initialize job history tracker (stores jobs for 7 days)
jobHistory = JobHistory(history_file="sent_jobs_history.json", retention_days=7)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def extractCVText():
    """Extract comprehensive CV text for embedding."""
    parts = []
    
    # Basics
    if "basics" in cv:
        parts.append(cv["basics"].get("headline", ""))
        parts.append(cv["basics"].get("name", ""))
    
    # Summary
    if "summary" in cv:
        parts.append(cv["summary"])
    
    # Skills - handle both formats
    if "skills" in cv:
        if isinstance(cv["skills"], list):
            parts.extend(cv["skills"])
        else:
            for skill in cv["skills"].get("items", []):
                parts.append(skill.get("name", ""))
    
    # Experience
    if "experience" in cv:
        for exp in cv["experience"]:
            parts.append(exp.get("title", ""))
            parts.append(exp.get("company", ""))
            parts.append(exp.get("description", ""))
            techs = exp.get("technologies", [])
            if isinstance(techs, list):
                parts.extend(techs)
    
    # Education
    if "education" in cv:
        for edu in cv["education"]:
            parts.append(edu.get("institution", ""))
            parts.append(edu.get("degree", ""))
    
    # Projects
    if "projects" in cv:
        for proj in cv["projects"]:
            parts.append(proj.get("title", ""))
            parts.append(proj.get("description", ""))
            parts.append(proj.get("fullDescription", ""))
            techs = proj.get("techStack", [])
            if isinstance(techs, list):
                parts.extend(techs)
    
    # Certifications
    if "certifications" in cv:
        for cert in cv["certifications"]:
            parts.append(cert.get("name", ""))
    
    # Awards
    if "awards" in cv:
        parts.extend(cv["awards"])
    
    # Achievements
    if "achievements" in cv:
        parts.extend(cv["achievements"])
    
    # Clean and combine
    text = " ".join(str(p) for p in parts if p)
    text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags if any
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text.lower()

cvText = extractCVText()
logging.info(f"CV text extracted: {len(cvText)} chars")
logging.debug(f"CV embedding input sample: {cvText[:200]}...")
cvEmbedding = model.encode(cvText)
logging.info(f"CV embedding generated: shape {cvEmbedding.shape}")

def cosineSim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def safeText(el):
    return el.get_text(strip=True) if el else ""

def cleanHtml(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', ' ', str(text)).strip()

def normalizeJob(title, company, location, description, applyLink, email=None):
    if not title or not company:
        return None
    title = cleanHtml(title).strip()
    company = cleanHtml(company).strip()
    location = cleanHtml(location).strip() if location else "pakistan"
    description = cleanHtml(description).strip()
    
    return {
        "title": title.lower(),
        "company": company,
        "location": location.lower(),
        "description": description.lower(),
        "applyLink": applyLink,
        "email": email,
        "id": f"{company.lower()[:30]}-{title.lower()[:40]}"
    }

def roleFilter(job):
    title = job["title"]
    desc = job["description"]
    combined = f"{title} {desc}"
    
    # Must match allowed roles from config
    ok = any(r in combined for r in allowedRoles)
    
    # OR must match user's actual tech stack
    myTechStack = [
        "python", "javascript", "typescript", "react", "next", "nextjs", 
        "node", "nodejs", "nest", "nestjs",
        "full stack", "fullstack", "full-stack",
        "frontend", "backend", "web developer",
        "ai", "ml", "machine learning", "artificial intelligence",
        "mern", "mean", "mongodb", "database",
        "fastapi", "software engineer"
    ]
    
    if not ok:
        ok = any(k in combined for k in myTechStack)
    
    if not ok:
        logging.debug(f"role rejected -> {job['title']}")
    return ok

def locationFilter(job):
    loc = job["location"]
    ok = (any(l in loc for l in allowedLocations) or "remote" in loc)
    if not ok:
        logging.debug(f"location rejected -> {job['title']} | {job['location']}")
    return ok

def experienceFilter(job):
    desc = job["description"]
    title = job["title"]
    combined = f"{title} {desc}"
    
    # Strict rejection patterns - these should NEVER pass
    rejectPatterns = [
        "senior", "sr.", "sr ", "lead", "principal", "staff engineer", "director",
        "5+ year", "6+ year", "7+ year", "8+ year", "10+ year",
        "5 year", "6 year", "7 year", "8 year",
        "mid-level", "mid level", "intermediate", "experienced",
        "3+ year", "4+ year", "3 year", "4 year"
    ]
    
    # If ANY reject pattern is found, block it immediately
    for pattern in rejectPatterns:
        if pattern in combined:
            logging.debug(f"experience rejected -> {job['title']} (found: {pattern})")
            return False
    
    # Only allow fresh graduate positions
    freshPatterns = ["fresh", "junior", "entry", "graduate", "intern", "trainee", 
                     "0-1", "0-2", "1-2", "associate", "entry level", "entry-level"]
    has_fresh = any(p in combined for p in freshPatterns)
    
    # If it mentions fresh keywords, allow it
    if has_fresh:
        return True
    
    # If no fresh keywords but also no reject patterns, be cautious - allow only if title suggests entry level
    entryLevelTitles = ["developer", "engineer", "programmer"]
    if any(t in title for t in entryLevelTitles) and "senior" not in title and "lead" not in title:
        return True
    
    logging.debug(f"experience rejected -> {job['title']} (no fresh keywords)")
    return False

def skillsExclusionFilter(job):
    """Block jobs requiring technologies NOT in CV."""
    title = job["title"].lower()
    desc = job["description"].lower()
    combined = f"{title} {desc}"
    
    # Technologies you DON'T have and should be filtered out
    excludedTech = [
        "flutter", "swift", "kotlin", "ios", "android",
        "angular", "vue", "vue.js",
        ".net", "c#", "csharp", "asp.net",
        "laravel", "php", "symfony",
        "ruby", "rails", "ruby on rails",
        "golang", "go developer",
        "salesforce", "sap", "oracle",
        "shopify", "wordpress", "drupal",
        "unity", "unreal", "game dev",
        "devops", "sre", "infrastructure", "network engineer",
        "qa", "test", "quality assurance", "sdet"
    ]
    
    # Check if job is PRIMARILY about excluded tech (mentioned in title)
    for tech in excludedTech:
        if tech in title:
            logging.debug(f"skills rejected -> {job['title']} (excluded tech in title: {tech})")
            return False
    
    # If excluded tech is mentioned multiple times in description, it's likely required
    for tech in excludedTech:
        if combined.count(tech) >= 2:
            logging.debug(f"skills rejected -> {job['title']} (excluded tech emphasis: {tech})")
            return False
    
    return True

def computeKeywordScore(job, cvSkills):
    text = f"{job['title']} {job['description']}".lower()
    
    # Keyword synonyms and related tech
    synonyms = {
        "next.js": ["nextjs", "next js", "react framework"],
        "nest.js": ["nestjs", "nest js"],
        "react": ["reactjs", "react.js"],
        "node": ["nodejs", "node.js"],
        "mongodb": ["mongo", "nosql", "database"],
        "typescript": ["ts", "javascript"],
        "python": ["py"],
        "fastapi": ["fast api", "python backend"],
        "ai": ["artificial intelligence", "machine learning", "ml"],
        "full stack": ["fullstack", "full-stack", "frontend", "backend"],
    }
    
    matches = 0
    for skill in cvSkills:
        skill_lower = skill.lower()
        # Direct match
        if skill_lower in text:
            matches += 1
        # Synonym match
        else:
            for key, syns in synonyms.items():
                if key in skill_lower or skill_lower in key:
                    if any(syn in text for syn in syns):
                        matches += 0.8  # Partial credit for synonym match
                        break
    
    total = len(cvSkills)
    return matches / total if total > 0 else 0

def scoreJobHybrid(job, cvEmbedding, cvSkills):
    """Score job using hybrid approach: semantic similarity + keyword matching."""
    jobText = f"{job['title']} {job['description']} {job['company']}"
    jobEmbedding = model.encode(jobText)
    
    # Normalize cosine similarity to 0-1 range (from -1 to 1)
    cosineScore = float(np.dot(cvEmbedding, jobEmbedding) / (np.linalg.norm(cvEmbedding) * np.linalg.norm(jobEmbedding)))
    cosineScore = max(0, cosineScore)  # Ensure non-negative
    
    # Keyword matching score
    keywordScore = computeKeywordScore(job, cvSkills)
    
    # Fresh graduate boost
    freshGradBoost = 0
    freshKeywords = ["fresh", "junior", "entry", "graduate", "intern", "trainee", "associate"]
    if any(kw in job['title'].lower() or kw in job['description'].lower() for kw in freshKeywords):
        freshGradBoost = 0.15  # 15% boost for fresh graduate positions
    
    # Role preference boost - prioritize MERN/Full Stack over AI
    roleBoost = 0
    title_lower = job['title'].lower()
    desc_lower = job['description'].lower()
    combined = f"{title_lower} {desc_lower}"
    
    # HIGH PRIORITY: MERN/Full Stack/Web Development (20% boost)
    highPriorityRoles = [
        "mern", "mean", "full stack", "fullstack", "full-stack",
        "web developer", "react", "next.js", "nextjs", "node.js", "nodejs",
        "javascript developer", "typescript developer", "frontend", "backend"
    ]
    if any(role in combined for role in highPriorityRoles):
        roleBoost = 0.20
        logging.info(f"  → HIGH PRIORITY role boost applied: +20%")
    
    # MEDIUM PRIORITY: General Software Engineering (10% boost)
    elif any(role in combined for role in ["software engineer", "software developer", "programmer"]):
        roleBoost = 0.10
    
    # LOW PRIORITY: AI/ML/Data (5% boost only)
    elif any(role in combined for role in ["ai engineer", "ml engineer", "data science", "machine learning"]):
        roleBoost = 0.05
        logging.info(f"  → Low priority AI/ML role: +5% only")
    
    # Weighted combination: 70% semantic + 30% keyword + boosts
    baseScore = cosineScore * 0.70 + keywordScore * 0.30
    totalScore = int((baseScore + freshGradBoost + roleBoost) * 100)
    totalScore = min(100, totalScore)  # Cap at 100%
    
    logging.info(
        f"score computed -> {job['title']} @ {job['company']} = {totalScore}% "
        f"(semantic {int(cosineScore*100)}%, keywords {int(keywordScore*100)}%)"
    )
    return totalScore


def sendToDiscord(job, score):
    if jobHistory.is_sent(job["id"]):
        logging.info(f"already sent -> {job['title']} (within {jobHistory.retention_days} days)")
        return
    
    jobHistory.mark_as_sent(job["id"])
    desc = job['description'][:400] + "..." if len(job['description']) > 400 else job['description']
    if not desc:
        desc = "No description available"
    
    color = 5763719 if score >= 70 else (16776960 if score >= 50 else 15105570)
    
    payload = {
        "embeds": [{
            "title": f"🚀 {job['title'].title()}",
            "description": f"**Company:** {job['company']}\n**Location:** {job['location'].title()}\n**Match Score:** {score}%\n\n**Description:**\n{desc}",
            "url": job['applyLink'],
            "color": color,
            "footer": {"text": f"Found by Joblyst • {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
        }],
        "content": f"**New Job Match Found!**\n\n🔗 **Apply Here:** {job['applyLink']}"
    }
    
    try:
        res = requests.post(discordWebhook, json=payload, timeout=10)
        logging.info(f"discord embed sent -> {job['title']} @ {job['company']} | {res.status_code}")
        time.sleep(1)
       
      
    except Exception as e:
        logging.error(f"discord error -> {e}")

def scrapeLinkedIn():
    logging.info("scraping linkedin (guest API)")
    jobs = []
    searchTerms = [
        "software engineer", "junior developer", "python developer", "frontend developer",
        "backend developer", "full stack developer", "web developer", "react developer",
        "node developer", "fresh graduate software", "associate software engineer",
        "software engineer intern",
    ]
    locations = ["Pakistan", "Lahore", "Karachi", "Islamabad"]
    
    
    for term in searchTerms:
        for location in locations[:2]:
            try:
                # Add f_TPR parameter for time posted range: past 24 hours (r86400)
                url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&location={quote_plus(location)}&f_TPR=r86400&start=0"
                response = requests.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    logging.warning(f"linkedin returned {response.status_code} for {term}")
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

def scrapeCompanyPages():
    logging.info("scraping company career pages")
    jobs = []
    for c in companies:
        try:
            response = requests.get(c["careerPage"], headers=HEADERS, timeout=15, verify=False)
            soup = BeautifulSoup(response.text, "html.parser")
            
            jobLinks = soup.select("a[href*='job'], a[href*='career'], a[href*='position'], a[href*='opening'], a[href*='apply'], a[href*='vacanc']")
            for a in jobLinks:
                text = safeText(a).lower()
                href = a.get("href", "")
                if len(text) < 5 or text in ["careers", "jobs", "apply", "view all", "see all"]:
                    continue
                relevantKeywords = allowedRoles + ["software", "developer", "engineer", "python", 
                                                   "javascript", "frontend", "backend", "fullstack",
                                                   "web", "react", "node", "ai", "ml", "data",
                                                   "mern", "mean", "django", "intern"]
                if any(r in text for r in relevantKeywords):
                    link = href
                    if link and not link.startswith("http"):
                        link = urljoin(c["careerPage"], href)
                    job = normalizeJob(text, c["name"], "lahore", text, link)
                    if job and job["id"] not in [j["id"] for j in jobs]:
                        jobs.append(job)
            
            jobCards = soup.select("div[class*='job'], div[class*='position'], article[class*='career'], li[class*='opening'], div[class*='vacancy'], div[class*='listing']")
            for card in jobCards:
                titleEl = card.select_one("h2, h3, h4, a[class*='title'], span[class*='title'], a")
                title = safeText(titleEl)
                if title and len(title) > 5 and len(title) < 100:
                    relevantKeywords = allowedRoles + ["software", "developer", "engineer"]
                    if any(r in title.lower() for r in relevantKeywords):
                        linkEl = card.select_one("a[href]")
                        link = c["careerPage"]
                        if linkEl and linkEl.get("href"):
                            link = linkEl["href"]
                            if not link.startswith("http"):
                                link = urljoin(c["careerPage"], link)
                        descEl = card.select_one("p, div[class*='desc'], span[class*='desc']")
                        description = safeText(descEl) if descEl else title
                        job = normalizeJob(title, c["name"], "lahore", description, link)
                        if job and job["id"] not in [j["id"] for j in jobs]:
                            jobs.append(job)
        except Exception as e:
            logging.warning(f"error scraping {c['name']}: {str(e)[:50]}")
            continue
    logging.info(f"company career jobs found: {len(jobs)}")
    return jobs

def runJoblyst():
    logging.info("=" * 60)
    logging.info(f"JOBLYST RUN STARTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)
    
    # Clean up old job entries (older than retention period)
    removed_count = jobHistory.cleanup_old_entries()
    stats = jobHistory.get_stats()
    logging.info(f"Job history stats: {stats['total_jobs']} jobs tracked, {removed_count} old entries removed")
    
    allJobs = []
    allJobs.extend(scrapeLinkedIn())
    allJobs.extend(scrapeCompanyPages())
    logging.info(f"total jobs collected: {len(allJobs)}")
    
    if len(allJobs) == 0:
        logging.warning("No jobs found! Check your internet connection or if sites are blocking.")
        return
    
    matchedJobs = 0
    for job in allJobs:
        if jobHistory.is_sent(job["id"]):
            logging.debug(f"skipping already sent job: {job['title']}")
            continue
        
        # Apply all filters BEFORE scoring to save computation
        if not roleFilter(job):
            continue
        if not locationFilter(job):
            continue
        if not experienceFilter(job):
            continue
        if not skillsExclusionFilter(job):
            continue
        
        # Compute hybrid score only for pre-filtered jobs
        score = scoreJobHybrid(job, cvEmbedding, cvSkills)
        if score >= minScore:
            sendToDiscord(job, score)
            matchedJobs += 1
            time.sleep(2)
        else:
            logging.info(f"score rejected -> {job['title']} = {score}%")
    
    logging.info("=" * 60)
    logging.info(f"JOBLYST RUN COMPLETED - Matched jobs sent: {matchedJobs}")
    logging.info("=" * 60)

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    runJoblyst()
