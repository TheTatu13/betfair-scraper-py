# betfair-scraper-py

Self-healing job scraper for **BETFAIR ROMANIA DEVELOPMENT SRL** (CIF
`22201773`), publishing to [peviitor.ro](https://peviitor.ro). Scrapes
[betfairromania.ro/jobs](https://www.betfairromania.ro/jobs) with `requests` +
BeautifulSoup (no browser), validates the company via ANAF, and keeps the
peviitor listing in sync (new jobs added, existing ones updated, jobs no
longer on the site removed).

Derived from the [Brewtality-3-16](https://github.com/TheTatu13/Brewtality-3-16)
Python template — see [`ai/AGENTS.md`](ai/AGENTS.md) and
[`ai/SELF-HEALING.md`](ai/SELF-HEALING.md) for how the scraping engine works.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate     # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest                                            # run the suite
python -m scraper.main --dry-run                  # run the pipeline without writing
```

Optional extras:

```bash
pip install -e ".[adaptive]"    # Scrapling adaptive selector fallback
pip install -e ".[browser]"     # Playwright, for scraper/job_validator.py
```

## Layout

| Path | Role |
|---|---|
| `config/company.json` | company identity (CIF, brand, careers URL, own-job-URL prefix) |
| `config/scraper.json` | source URLs, selector cascades, retry policy, delays |
| `scraper/parse.py` | `parse_listing` — this site's markup, on top of the generic cascade |
| `scraper/self_healing.py` | generic cascade: `first_match`, `locate_articles`, `json_ld_job_postings`, `scrapling_text` |
| `scraper/validate.py` | generic data validation + `assert_scrape_yielded_jobs` (canary) |
| `scraper/fetch.py` | `requests` + retry / full-jitter backoff |
| `scraper/api.py` | peviitor API client (search, upload, delete) |
| `scraper/anaf.py`, `scraper/company.py` | ANAF/CUIScan/CUIFirma company validation (own retry-free requests, by design) |
| `scraper/job_validator.py`, `scraper/validate_jobs.py` | deep per-job URL validation (HEAD/content/browser checks) + manual CLI |
| `scraper/markdown_generator.py` | renders `docs/jobs.md` |
| `scraper/main.py` | orchestration: scrape → validate → canary → upsert → diff → re-verify in SOLR |
| `docs/index.html` | GitHub Pages status page for this scraper |
| `ai/AGENTS.md` | rules for AI agents working in this repo |
| `ai/SELF-HEALING.md` | the cascade in depth, JS↔Python parity, Scrapling notes |

## The cascade in one paragraph

Every field is extracted by trying strategies top to bottom until one returns a
non-empty value: **primary CSS → fallback CSS → structural (itemprop / aria /
JSON-LD) → regex → (optional) Scrapling adaptive relocation**. Each step has its
own `try/except`; a failed or rescued step is logged immediately. If a whole
run scrapes nothing, the **canary** raises before any file or API write. Full
detail in [`ai/SELF-HEALING.md`](ai/SELF-HEALING.md).

## Running in production

`.github/workflows/scrape.yml` runs daily (06:00 UTC) and can be dispatched
manually (`dry_run: true` by default — set it to `false` to actually write to
peviitor). Other workflows: `tests.yml` (CI on every push/PR),
`job-deep-validate.yml` (manual deep URL validation),
`job-recovery-from-disaster.yml` (manual, dry-run-first restore of
`config/company.json` from ANAF if it's ever lost or corrupted),
`automation-template-sync-check.yml` (weekly check against the upstream
template, opens an issue if this repo has drifted).

## License

MIT.
