"""The canary must stop scraper.main.run() before any API write when a run
scrapes nothing (or nothing survives validation)."""

import pytest

from scraper import api, company as company_validation, job_validator, main
from scraper.validate import CanaryError


@pytest.fixture
def no_api(monkeypatch, tmp_path):
    """Stub the API/ANAF so a test never touches the network, record upserts,
    and run inside a throwaway directory (run() writes docs/jobs.md + company.json)."""
    monkeypatch.chdir(tmp_path)
    upserts = []
    monkeypatch.setattr(api, "query_solr", lambda cif: {"numFound": 0, "docs": []})
    monkeypatch.setattr(api, "upsert_jobs", lambda jobs: upserts.append(jobs))
    monkeypatch.setattr(
        job_validator, "validate_by_content",
        lambda url, **kw: {"url": url, "status": "active", "httpStatus": 200, "title": None, "error": None},
    )
    monkeypatch.setattr(
        company_validation,
        "validate_and_get_company",
        lambda: {"status": "active", "company": "EXAMPLE CO", "cif": "12345678", "address": ""},
    )
    return upserts


def test_zero_scraped_raises_canary_and_never_upserts(monkeypatch, no_api):
    monkeypatch.setattr(main, "scrape_careers", lambda: [])
    with pytest.raises(CanaryError):
        main.run()
    assert no_api == []


def test_all_jobs_invalid_also_raises_canary(monkeypatch, no_api):
    # scraped something, but every item is unpublishable -> still a canary
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "not-a-url", "title": ""},
        {"url": "", "title": "no url"},
    ])
    with pytest.raises(CanaryError):
        main.run()
    assert no_api == []


def test_valid_jobs_reach_upsert(monkeypatch, no_api):
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/widget-engineer/", "title": "Widget Engineer"},
    ])
    count = main.run()
    assert count == 1
    assert len(no_api) == 1 and no_api[0][0]["title"] == "Widget Engineer"


def test_dry_run_scrapes_and_validates_but_does_not_upsert(monkeypatch, no_api):
    monkeypatch.setattr(main, "scrape_careers", lambda: [
        {"url": "https://jobs.example.com/careers/x/", "title": "X"},
    ])
    main.run(dry_run=True)
    assert no_api == []
