"""CV <-> job matching: hybrid semantic embedding + keyword scoring.

Model swapped from all-MiniLM-L6-v2 (22M params, weak retrieval quality) to
BAAI/bge-base-en-v1.5, which ranks far higher on MTEB retrieval/STS while still
being small enough to run on a GitHub Actions CPU runner in a daily job.
"""
import logging
import re

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-base-en-v1.5"

_model = None


def getModel():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
        logging.info(f"sentence transformer loaded: {MODEL_NAME}")
    return _model


def extractCVText(cv):
    """Extract comprehensive CV text for embedding."""
    parts = []

    if "basics" in cv:
        parts.append(cv["basics"].get("headline", ""))
        parts.append(cv["basics"].get("name", ""))

    if "summary" in cv:
        parts.append(cv["summary"])

    if "skills" in cv:
        if isinstance(cv["skills"], list):
            parts.extend(cv["skills"])
        else:
            for skill in cv["skills"].get("items", []):
                parts.append(skill.get("name", ""))

    if "experience" in cv:
        for exp in cv["experience"]:
            parts.append(exp.get("title", ""))
            parts.append(exp.get("company", ""))
            parts.append(exp.get("description", ""))
            techs = exp.get("technologies", [])
            if isinstance(techs, list):
                parts.extend(techs)

    if "education" in cv:
        for edu in cv["education"]:
            parts.append(edu.get("institution", ""))
            parts.append(edu.get("degree", ""))

    if "projects" in cv:
        for proj in cv["projects"]:
            parts.append(proj.get("title", ""))
            parts.append(proj.get("description", ""))
            parts.append(proj.get("fullDescription", ""))
            techs = proj.get("techStack", [])
            if isinstance(techs, list):
                parts.extend(techs)

    if "certifications" in cv:
        for cert in cv["certifications"]:
            parts.append(cert.get("name", ""))

    if "awards" in cv:
        parts.extend(cv["awards"])

    if "achievements" in cv:
        parts.extend(cv["achievements"])

    text = " ".join(str(p) for p in parts if p)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()


def extractCVSkills(cv):
    cvSkills = []
    if "skills" in cv:
        if isinstance(cv["skills"], list):
            cvSkills.extend([s.lower() for s in cv["skills"] if isinstance(s, str)])
        else:
            for skill in cv["skills"].get("items", []):
                cvSkills.append(skill.get("name", "").lower())
                keywords = skill.get("keywords", [])
                if isinstance(keywords, list):
                    cvSkills.extend([k.lower() for k in keywords])
    return cvSkills


def cosineSim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def computeKeywordScore(job, cvSkills):
    text = f"{job['title']} {job['description']}".lower()

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
        if skill_lower in text:
            matches += 1
        else:
            for key, syns in synonyms.items():
                if key in skill_lower or skill_lower in key:
                    if any(syn in text for syn in syns):
                        matches += 0.8
                        break

    total = len(cvSkills)
    return matches / total if total > 0 else 0


def scoreJobHybrid(job, cvEmbedding, cvSkills):
    """Score job using hybrid approach: semantic similarity + keyword matching."""
    model = getModel()
    jobText = f"{job['title']} {job['description']} {job['company']}"
    jobEmbedding = model.encode(jobText)

    cosineScore = cosineSim(cvEmbedding, jobEmbedding)
    cosineScore = max(0, cosineScore)

    keywordScore = computeKeywordScore(job, cvSkills)

    freshGradBoost = 0
    freshKeywords = ["fresh", "junior", "entry", "graduate", "intern", "trainee", "associate", "new grad"]
    if any(kw in job['title'].lower() or kw in job['description'].lower() for kw in freshKeywords):
        freshGradBoost = 0.15

    roleBoost = 0
    title_lower = job['title'].lower()
    desc_lower = job['description'].lower()
    combined = f"{title_lower} {desc_lower}"

    highPriorityRoles = [
        "mern", "mean", "full stack", "fullstack", "full-stack",
        "web developer", "react", "next.js", "nextjs", "node.js", "nodejs",
        "javascript developer", "typescript developer", "frontend", "backend"
    ]
    if any(role in combined for role in highPriorityRoles):
        roleBoost = 0.20
        logging.info("  → HIGH PRIORITY role boost applied: +20%")
    elif any(role in combined for role in ["software engineer", "software developer", "programmer"]):
        roleBoost = 0.10
    elif any(role in combined for role in ["ai engineer", "ml engineer", "data science", "machine learning"]):
        roleBoost = 0.05
        logging.info("  → Low priority AI/ML role: +5% only")

    baseScore = cosineScore * 0.70 + keywordScore * 0.30
    totalScore = int((baseScore + freshGradBoost + roleBoost) * 100)
    totalScore = min(100, totalScore)

    logging.info(
        f"score computed -> {job['title']} @ {job['company']} = {totalScore}% "
        f"(semantic {int(cosineScore*100)}%, keywords {int(keywordScore*100)}%)"
    )
    return totalScore
