"""scraper.main.run() orchestration: company validation, company upsert
(manageCompany), stale-job deletion (staleJobDeletion), and docs/ generation.

Network (ANAF, SOLR, peviitor) is always stubbed here -- these are pure
orchestration tests, not integration tests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import pytest

from scraper import api, company as company_validation, job_validator, main
from scraper.config import scraper


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """Run inside a throwaway CWD, and stub every network call."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "query_solr", lambda cif: {"numFound": 0, "docs": []})
    monkeypatch.setattr(api, "upsert_jobs", lambda jobs: None)
    # manageCompany now defaults to True (Category 1 audit -- it was off by an
    # unverified assumption), so every test must stub these two or a bare
    # main.run() would hit the real API.
    monkeypatch.setattr(api, "upsert_company", lambda doc: None)
    monkeypatch.setattr(api, "delete_job_by_url", lambda url: None)
    monkeypatch.setattr(
        job_validator, "validate_by_content",
        lambda url, **kw: {"url": url, "status": "active", "httpStatus": 200, "title": None, "error": None},
    )
    return tmp_path


def _active(**overrides):
    base = {"status": "active", "company": "EXAMPLE CO", "cif": "12345678", "address": "Cluj-Napoca"}
    base.update(overrides)
    return base


def test_inactive_company_deletes_only_own_jobs_and_skips_scrape(monkeypatch, isolated):
    monkeypatch.setattr(
        api,
        "query_solr",
        lambda cif: {
            "numFound": 2,
            "docs": [
                {"url": f"{scraper['ownJobUrlPrefix']}ours/"},
                {"url": "https://someone-elses-board.example/jobs/theirs/"},
            ],
        },
    )
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active(status="inactive"))
    deleted = []
    monkeypatch.setattr(api, "delete_job_by_url", lambda url: deleted.append(url))
    scrape_called = []
    monkeypatch.setattr(main, "scrape_careers", lambda: scrape_called.append(1) or [])

    result = main.run()

    assert result == 0
    assert deleted == [f"{scraper['ownJobUrlPrefix']}ours/"]  # never touches the other scraper's job
    assert scrape_called == []  # scraping is skipped entirely


def test_manage_company_true_calls_upsert_company(monkeypatch, isolated):
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/x/", "title": "X"},
    ])
    monkeypatch.setitem(scraper, "manageCompany", True)
    calls = []
    monkeypatch.setattr(api, "upsert_company", lambda doc: calls.append(doc))

    main.run()

    assert len(calls) == 1
    assert calls[0]["id"] == "12345678"
    assert calls[0]["company"] == "EXAMPLE CO"
    assert calls[0]["location"] == ["Cluj-Napoca"]


def test_manage_company_false_never_calls_upsert_company(monkeypatch, isolated):
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/x/", "title": "X"},
    ])
    monkeypatch.setitem(scraper, "manageCompany", False)
    called = []
    monkeypatch.setattr(api, "upsert_company", lambda doc: called.append(doc))

    main.run()

    assert called == []


def test_stale_job_deletion_true_deletes_gone_urls(monkeypatch, isolated):
    own_prefix = "https://jobs.example.com/careers/"
    monkeypatch.setattr(main, "OWN_URL_PREFIX", own_prefix)
    monkeypatch.setattr(
        api,
        "query_solr",
        lambda cif: {"numFound": 1, "docs": [{"url": f"{own_prefix}old-job/"}]},
    )
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": f"{own_prefix}new-job/", "title": "New Job"},
    ])
    monkeypatch.setitem(scraper, "staleJobDeletion", True)
    deleted = []
    monkeypatch.setattr(api, "delete_job_by_url", lambda url: deleted.append(url))

    try:
        main.run()
    finally:
        monkeypatch.setitem(scraper, "staleJobDeletion", False)

    assert deleted == [f"{own_prefix}old-job/"]


def test_stale_job_deletion_false_kept_by_default(monkeypatch, isolated):
    own_prefix = "https://jobs.example.com/careers/"
    monkeypatch.setattr(main, "OWN_URL_PREFIX", own_prefix)
    monkeypatch.setattr(
        api,
        "query_solr",
        lambda cif: {"numFound": 1, "docs": [{"url": f"{own_prefix}old-job/"}]},
    )
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": f"{own_prefix}new-job/", "title": "New Job"},
    ])
    deleted = []
    monkeypatch.setattr(api, "delete_job_by_url", lambda url: deleted.append(url))

    main.run()

    assert deleted == []


def test_successful_run_writes_docs_jobs_md_and_company_json(monkeypatch, isolated):
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/widget-engineer/", "title": "Widget Engineer"},
    ])

    main.run()

    jobs_md = Path("docs/jobs.md").read_text(encoding="utf-8")
    assert "EXAMPLE CO" in jobs_md
    assert "Widget Engineer" in jobs_md

    company_json = json.loads(Path("docs/company.json").read_text(encoding="utf-8"))
    assert "ownJobUrlPrefix" in company_json
    assert company_json["ownJobUrlPrefix"] == scraper["ownJobUrlPrefix"]


def test_summary_reflects_confirmed_post_upload_solr_state_not_local_estimate(monkeypatch, isolated, caplog):
    """The whole point of the re-query: if the real, confirmed SOLR count after
    the write differs from what we locally assumed we just upserted, the
    printed summary must show the confirmed number, not the optimistic one."""
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/widget-engineer/", "title": "Widget Engineer"},
    ])
    responses = iter([
        {"numFound": 0, "docs": []},   # Step 1: nothing in SOLR yet
        {"numFound": 5, "docs": []},   # final re-query: only 5 confirmed, not the 1 we scraped
    ])
    monkeypatch.setattr(api, "query_solr", lambda cif: next(responses))

    with caplog.at_level("INFO", logger="scraper.main"):
        main.run()

    assert "jobs in SOLR after scrape:    5" in caplog.text
    with pytest.raises(StopIteration):
        next(responses)  # exactly two query_solr calls were made, no more


def test_run_sleeps_before_the_final_reverification_query(monkeypatch, isolated):
    monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/widget-engineer/", "title": "Widget Engineer"},
    ])
    slept = []
    monkeypatch.setattr(main.time, "sleep", lambda secs: slept.append(secs))

    main.run()

    assert slept == [main._SOLR_SETTLE_DELAY_SEC]


def test_to_job_model_date_is_solr_safe_not_pythons_native_isoformat():
    """peviitor's Solr date field parses only "...SSSZ" (JS's toISOString()
    shape). Python's bare datetime.isoformat() instead emits microseconds and
    a "+00:00" offset, which Solr's date field rejects with a 400 -- this is
    what an unpadded 18-job upload from this scraper actually hit."""
    job = main._to_job_model({"url": "https://x/y/", "title": "T"}, "12345678", "EXAMPLE CO")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", job["date"])


class _FakeResp:
    def __init__(self, text=""):
        self.text = text

    def raise_for_status(self):
        pass


class TestScrapeCareersUrlSelection:
    """A real permalink whose ID a title-slug guess could never reproduce
    (e.g. "/jobs/jr133930/software-architect-fanduel-hybrid/") is exactly
    what silently reached peviitor as a 404 before parse_listing scraped
    real hrefs. The real URL must now win whenever it's present."""

    def test_prefers_the_real_scraped_url_over_a_guessed_slug(self, monkeypatch, isolated):
        monkeypatch.setattr(main.fetch, "get", lambda url, **kw: _FakeResp())
        monkeypatch.setattr(main, "parse_listing", lambda html: [
            {
                "title": "Software Architect - FanDuel, Hybrid",
                "expirationdate": None,
                "url": "/jobs/jr133930/software-architect-fanduel-hybrid/",
            },
        ])

        jobs = main.scrape_careers()

        assert jobs[0]["url"] == urljoin(
            scraper["sources"]["listing"], "/jobs/jr133930/software-architect-fanduel-hybrid/"
        )

    def test_falls_back_to_a_guessed_slug_when_nothing_was_scraped(self, monkeypatch, isolated):
        monkeypatch.setattr(main.fetch, "get", lambda url, **kw: _FakeResp())
        monkeypatch.setattr(main, "parse_listing", lambda html: [
            {"title": "Some Job", "expirationdate": None, "url": None},
        ])

        jobs = main.scrape_careers()

        assert jobs[0]["url"] == f'{scraper["sources"]["jobArchive"]}some-job/'


class TestDropDeadUrls:
    def test_keeps_active_and_drops_expired_or_erroring(self, monkeypatch):
        def fake_content_check(url, **kw):
            status = "active" if "good" in url else "expired"
            return {"url": url, "status": status, "httpStatus": 200 if status == "active" else 404, "title": None, "error": None}

        monkeypatch.setattr(job_validator, "validate_by_content", fake_content_check)

        jobs = [
            {"url": "https://x/good/", "title": "Good"},
            {"url": "https://x/bad/", "title": "Bad"},
        ]
        kept = main._drop_dead_urls(jobs)

        assert [j["title"] for j in kept] == ["Good"]

    def test_run_skips_upsert_when_every_job_fails_live_validation(self, monkeypatch, isolated):
        """404s must never reach peviitor -- and an empty array must never
        be sent to api.upsert_jobs (the API rejects it)."""
        monkeypatch.setattr(company_validation, "validate_and_get_company", lambda: _active())
        monkeypatch.setattr(main, "scrape_careers", lambda: [
            {"url": "https://jobs.example.com/careers/widget-engineer/", "title": "Widget Engineer"},
        ])
        monkeypatch.setattr(
            job_validator, "validate_by_content",
            lambda url, **kw: {"url": url, "status": "expired", "httpStatus": 404, "title": None, "error": None},
        )
        calls = []
        monkeypatch.setattr(api, "upsert_jobs", lambda jobs: calls.append(jobs))

        count = main.run()

        assert count == 0
        assert calls == []
