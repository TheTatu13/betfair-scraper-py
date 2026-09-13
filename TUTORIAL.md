# Operating this scraper

Day-to-day maintenance for `betfair-scraper-py` (BETFAIR ROMANIA DEVELOPMENT
SRL, CIF `22201773`). For how the scraping engine itself works, see
[`ai/AGENTS.md`](ai/AGENTS.md) and [`ai/SELF-HEALING.md`](ai/SELF-HEALING.md).

## Running a scrape manually

The `scrape.yml` workflow runs daily at 06:00 UTC and can also be triggered by
hand:

```bash
gh workflow run scrape.yml -f dry_run=false    # writes to peviitor
gh workflow run scrape.yml -f dry_run=true     # scrapes + validates only, no writes
```

Follow it and check the outcome:

```bash
gh run list --workflow=scrape.yml --limit=5
gh run view --log <run-id>
```

Locally, without touching the network write path:

```bash
pip install -e ".[dev]"
python -m scraper.main --dry-run
```

## When the site's markup changes

If `scrape.yml` starts logging fallback/rescue steps (or the canary fails
because zero jobs were scraped):

1. Check the run's log for which cascade level rescued each field — a
   `WARNING` there means the primary selector broke but a fallback caught it;
   an `ERROR`/canary failure means all fallbacks missed too.
2. Inspect the real page at
   [betfairromania.ro/jobs](https://www.betfairromania.ro/jobs) and update the
   selector lists in `config/scraper.json` (`selectors.jobArticle`,
   `selectors.jobTitle`, `selectors.jobMeta`) and, if the structure changed
   more deeply, `parse_listing` in `scraper/parse.py`.
3. Add/extend a test in `tests/test_parse.py` or `tests/test_self_healing.py`
   for the new markup shape, then `pytest -q`.

## Deep job-URL validation

`job-deep-validate.yml` (manual dispatch) runs `scraper/validate_jobs.py`
against every job currently in peviitor for this company — HEAD request,
content check, and (if the `browser` extra is installed) a headless-browser
check — to catch stale listings a plain HEAD wouldn't. Run it from the repo
locally with:

```bash
pip install -e ".[dev,browser]"
python -m scraper.validate_jobs
```

## Recovering `config/company.json` / `company.json`

If the committed ANAF snapshot (`company.json`) or `config/company.json` is
ever lost or corrupted, `job-recovery-from-disaster.yml` (manual dispatch,
`dry_run: true` by default) re-validates the company against ANAF and
regenerates them. Always run it with `dry_run: true` first and review the
diff before re-running with `dry_run: false`.

## Template drift

`automation-template-sync-check.yml` runs weekly, diffs this repo against the
upstream [Brewtality-3-16](https://github.com/TheTatu13/Brewtality-3-16)
template's `scraper-py/`, and opens an issue if the generic files
(`self_healing.py`, `validate.py`, `fetch.py`, `api.py`, …) have drifted from
the template in a way that looks unintentional.

## Tests

```bash
pytest -q            # unit + consistency (network-independent parts)
```

- **Unit** (`tests/test_*.py`, excluding the folders below) — no network, run
  on every push/PR via `tests.yml`.
- **`tests/integration/`**, **`tests/e2e/`** — hit the real careers site and
  peviitor API; self-skip without network access.
- **`tests/consistency/`** — repo metadata checks (public visibility, topics,
  workflow naming, changelog/version match); the GitHub-API ones self-skip
  without `GITHUB_REPOSITORY`/`GITHUB_TOKEN` (set automatically in CI).
