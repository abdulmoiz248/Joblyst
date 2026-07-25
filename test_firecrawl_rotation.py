"""Unit tests for the Firecrawl company rotation, so a daily cron doesn't
scrape every custom career page (and burn credits) on every single run."""
import json
import os
import tempfile

import firecrawl_rotation

COMPANIES = [{"name": f"Company{i}"} for i in range(7)]


def _tmp_state_path():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)
    return path


def test_first_batch_starts_at_zero():
    state = _tmp_state_path()
    batch = firecrawl_rotation.nextBatch(COMPANIES, state, 3)
    assert [c["name"] for c in batch] == ["Company0", "Company1", "Company2"]
    os.remove(state)


def test_batch_advances_across_calls():
    state = _tmp_state_path()
    first = firecrawl_rotation.nextBatch(COMPANIES, state, 3)
    second = firecrawl_rotation.nextBatch(COMPANIES, state, 3)
    assert [c["name"] for c in first] == ["Company0", "Company1", "Company2"]
    assert [c["name"] for c in second] == ["Company3", "Company4", "Company5"]
    os.remove(state)


def test_batch_wraps_around():
    state = _tmp_state_path()
    with open(state, "w") as f:
        json.dump({"index": 6}, f)
    batch = firecrawl_rotation.nextBatch(COMPANIES, state, 3)
    assert [c["name"] for c in batch] == ["Company6", "Company0", "Company1"]
    os.remove(state)


def test_batch_size_larger_than_list_returns_all_once():
    state = _tmp_state_path()
    batch = firecrawl_rotation.nextBatch(COMPANIES, state, 100)
    assert len(batch) == len(COMPANIES)
    os.remove(state)


def test_empty_company_list_returns_empty():
    state = _tmp_state_path()
    assert firecrawl_rotation.nextBatch([], state, 5) == []


def test_state_persists_across_module_reloads():
    state = _tmp_state_path()
    firecrawl_rotation.nextBatch(COMPANIES, state, 2)
    assert firecrawl_rotation.loadIndex(state) == 2
    os.remove(state)
