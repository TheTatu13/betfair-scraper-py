"""Consistency test: the repository must have EXACTLY the 2 required topics.

Mirrors the JS template's tests/consistency/topics.test.js. Skips (rather
than fails) when GITHUB_REPOSITORY isn't set -- i.e. when run locally, not
in CI -- exactly like the JS version.
"""

from __future__ import annotations

import os

import pytest
import requests

REPO = os.environ.get("GITHUB_REPOSITORY")
TOKEN = os.environ.get("GITHUB_TOKEN")

REQUIRED_TOPICS = ["job-seeker-ro-spider", "peviitor-ro"]


def test_repository_has_exactly_the_required_topics():
    if not REPO:
        pytest.skip("GITHUB_REPOSITORY not set -- running locally, skipping API check")

    headers = {"Accept": "application/vnd.github.mercy-preview+json", "User-Agent": "pytest"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"

    res = requests.get(f"https://api.github.com/repos/{REPO}/topics", headers=headers, timeout=10)
    assert res.ok, f"GitHub API error: {res.status_code} - {res.text}"

    topics = sorted(t.lower() for t in res.json().get("names", []))
    assert len(topics) == 2, f"expected exactly 2 topics, got: {topics}"
    assert topics == sorted(REQUIRED_TOPICS)
