import json
import logging
import os
import re
import time
from datetime import datetime

from dotenv import load_dotenv

import freshness
import scoring
from job_history import JobHistory
from notifier import sendToDiscord
from sources import ashby, firecrawl_source, greenhouse, lever, linkedin

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.info("starting joblyst")

with open("cv.json", encoding="utf-8") as f:
    cv = json.load(f)

with open("companies.json", encoding="utf-8") as f:
    companies = json.load(f)["companies"]

with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

allowedRoles = [r.lower() for r in config["allowedRoles"]]
minScore = config.get("minScore", 40)
experienceMaxYears = config.get("experienceMaxYears", 2)
discordWebhook = os.getenv("DISCORD_WEBHOOK")

if not discordWebhook:
    raise ValueError("DISCORD_WEBHOOK environment variable not set")

cvSkills = scoring.extractCVSkills(cv)
cvText = scoring.extractCVText(cv)
logging.info(f"CV text extracted: {len(cvText)} chars")
cvEmbedding = scoring.getModel().encode(cvText)
logging.info(f"CV embedding generated: shape {cvEmbedding.shape}")

jobHistory = JobHistory(history_file="sent_jobs_history.json", retention_days=7)


def roleFilter(job):
    title = job["title"]
    desc = job["description"]
    combined = f"{title} {desc}"

    ok = any(r in combined for r in allowedRoles)

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


def experienceFilter(job):
    desc = job["description"]
    title = job["title"]
    combined = f"{title} {desc}"

    rejectPatterns = [
        "senior", "sr.", "sr ", "lead", "principal", "staff engineer", "director",
        "mid-level", "mid level", "intermediate", "experienced",
    ]
    for pattern in rejectPatterns:
        if pattern in combined:
            logging.debug(f"experience rejected -> {job['title']} (found: {pattern})")
            return False

    yearsMatches = re.findall(r'(\d+)\+?\s*(?:-\s*\d+\s*)?years?', combined)
    for match in yearsMatches:
        if int(match) > experienceMaxYears:
            logging.debug(f"experience rejected -> {job['title']} (requires {match}+ years)")
            return False

    freshPatterns = ["fresh", "junior", "entry", "graduate", "new grad", "intern", "trainee",
                      "0-1", "0-2", "1-2", "associate", "entry level", "entry-level"]
    if any(p in combined for p in freshPatterns):
        return True

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

    for tech in excludedTech:
        if tech in title:
            logging.debug(f"skills rejected -> {job['title']} (excluded tech in title: {tech})")
            return False

    for tech in excludedTech:
        if combined.count(tech) >= 2:
            logging.debug(f"skills rejected -> {job['title']} (excluded tech emphasis: {tech})")
            return False

    return True


def gatherJobs():
    jobs = []
    jobs.extend(linkedin.fetch_jobs())

    for c in companies:
        source = c.get("source")
        try:
            if source == "greenhouse":
                jobs.extend(greenhouse.fetch_jobs(c["id"], c["name"]))
            elif source == "lever":
                jobs.extend(lever.fetch_jobs(c["id"], c["name"]))
            elif source == "ashby":
                jobs.extend(ashby.fetch_jobs(c["id"], c["name"]))
            elif source == "firecrawl":
                jobs.extend(firecrawl_source.fetch_jobs(c["name"], c["careerPage"]))
            else:
                logging.warning(f"unknown source '{source}' for {c['name']}")
        except Exception as e:
            logging.warning(f"source error for {c['name']}: {e}")
            continue

    return jobs


def runJoblyst():
    logging.info("=" * 60)
    logging.info(f"JOBLYST RUN STARTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)

    removed_count = jobHistory.cleanup_old_entries()
    stats = jobHistory.get_stats()
    logging.info(f"Job history stats: {stats['total_jobs']} jobs tracked, {removed_count} old entries removed")

    allJobs = gatherJobs()
    logging.info(f"total jobs collected: {len(allJobs)}")

    if len(allJobs) == 0:
        logging.warning("No jobs found! Check your internet connection or if sites are blocking.")
        return

    matchedJobs = 0
    for job in allJobs:
        if jobHistory.is_sent(job["id"]):
            logging.debug(f"skipping already sent job: {job['title']}")
            continue

        freshness.enrich(job)
        if freshness.is_stale(job, config):
            continue

        if not roleFilter(job):
            continue
        if not experienceFilter(job):
            continue
        if not skillsExclusionFilter(job):
            continue

        score = scoring.scoreJobHybrid(job, cvEmbedding, cvSkills)
        if score >= minScore:
            sendToDiscord(job, score, discordWebhook)
            jobHistory.mark_as_sent(job["id"])
            matchedJobs += 1
            time.sleep(2)
        else:
            logging.info(f"score rejected -> {job['title']} = {score}%")

    logging.info("=" * 60)
    logging.info(f"JOBLYST RUN COMPLETED - Matched jobs sent: {matchedJobs}")
    logging.info("=" * 60)


if __name__ == "__main__":
    runJoblyst()
