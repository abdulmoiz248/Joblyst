"""Rotates through Firecrawl-sourced companies a few at a time per run.

Firecrawl charges credits per scrape, unlike the free ATS APIs - scraping all
Firecrawl-sourced companies on every daily run burns through credits fast for no
benefit (a custom career page doesn't change hour to hour). Instead we persist a
rotation index across runs and only scrape a small batch each time, cycling through
the full list over several days.
"""
import json
import logging
import os


def loadIndex(state_file):
    if not os.path.exists(state_file):
        return 0
    try:
        with open(state_file, encoding="utf-8") as f:
            return json.load(f).get("index", 0)
    except Exception as e:
        logging.warning(f"firecrawl rotation state read error: {e}")
        return 0


def saveIndex(state_file, index):
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"index": index}, f)
    except Exception as e:
        logging.warning(f"firecrawl rotation state write error: {e}")


def nextBatch(companies, state_file, batch_size):
    """Return a rotating slice of `companies` of size `batch_size`, advancing and
    persisting the rotation index (wraps around once the end of the list is hit)."""
    if not companies or batch_size <= 0:
        return []

    index = loadIndex(state_file) % len(companies)
    batchSize = min(batch_size, len(companies))
    batch = [companies[(index + i) % len(companies)] for i in range(batchSize)]
    saveIndex(state_file, (index + batchSize) % len(companies))
    return batch
