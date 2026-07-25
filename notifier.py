"""Discord notification formatting/sending."""
import logging
import time
from datetime import datetime

import requests


def sendToDiscord(job, score, webhook_url):
    desc = job['description'][:400] + "..." if len(job['description']) > 400 else job['description']
    if not desc:
        desc = "No description available"

    color = 5763719 if score >= 70 else (16776960 if score >= 50 else 15105570)

    freshnessLine = ""
    if job.get("deadline"):
        freshnessLine = f"\n⏳ **Apply by:** {job['deadline'].strftime('%b %d, %Y')}"
    elif job.get("posted_date"):
        daysAgo = (datetime.now().date() - job["posted_date"]).days
        freshnessLine = f"\n📅 **Posted:** {daysAgo}d ago"

    payload = {
        "embeds": [{
            "title": f"🚀 {job['title'].title()}",
            "description": f"**Company:** {job['company']}\n**Location:** {job['location'].title()}\n**Match Score:** {score}%{freshnessLine}\n\n**Description:**\n{desc}",
            "url": job['applyLink'],
            "color": color,
            "footer": {"text": f"Found by Joblyst • {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
        }],
        "content": f"**New Job Match Found!**\n\n🔗 **Apply Here:** {job['applyLink']}"
    }

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        logging.info(f"discord embed sent -> {job['title']} @ {job['company']} | {res.status_code}")
        time.sleep(1)
    except Exception as e:
        logging.error(f"discord error -> {e}")
