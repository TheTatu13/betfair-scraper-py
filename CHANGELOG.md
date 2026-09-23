# Changelog

## [0.3.0] - 2026-09-23

### Added
- `search_anofm()` in `scraper/main.py`: pulls supplementary postings for
  this CIF from ANOFM (the state employment agency), same as the JS
  template's `searchANOFM` — this Python port shipped without it since it
  was first written, even though the README always documented both
  variants as targeting "a Romanian company's own careers site + ANOFM".
  These are additive only (never touch `ownJobUrlPrefix` stale-job
  deletion, since they live under `mediere.anofm.ro`).
- `_drop_dead_urls()`: GET-checks every job URL before upload and drops
  the ones that don't resolve. `validate.py` only checked URL *shape*; a
  URL-construction bug could previously reach peviitor undetected. Uses
  `validate_by_content` (GET) rather than HEAD, since at least one real
  careers site answers every HEAD request with a generic 404 regardless
  of whether the resource exists.
- `company upsert` payload now includes `scraperFile`.

_Note: this work was written before today's Faza 2/3 audit but only
committed today, bundled with an unrelated CI commit
("ci: add weekly health-summary reusable-workflow caller") because it
had been left staged when a real merge conflict came up mid-audit. The
code and its tests (149 passing) were not touched or altered — this
entry documents what actually shipped and when._

## [0.2.0] - 2026-09-23

### Fixed
- `scrape.yml`/`tests.yml`: `GITHUB_TOKEN` now passed to pre-scrape tests
  (was hitting GitHub's unauthenticated rate limit intermittently).
- `autoheal` job: `gh` calls now pass `-R "${{ github.repository }}"`.
- `scrape.yml`: dry-run gate now checks `event_name == 'workflow_dispatch'`
  before reading `inputs.dry_run` — a `schedule` run has no `inputs`
  context, so the previous check silently forced every cron run into
  dry-run forever and this scraper never wrote real data.
- `tests/integration/test_company_real.py`: live ANAF/CUIScan and peViitor
  Solr calls now retry (3 attempts) and `pytest.skip()` instead of failing
  the build on transient upstream flakiness.

### Changed
- `scrape.yml` / `tests.yml` now call the Brewtality-3-16 template's
  reusable workflows (`scrape-reusable.yml` / `tests-reusable.yml` @v1)
  instead of carrying the logic locally — pulled in from template v0.2.0.

## [0.1.0] - 2026-09-10

### Added
- Initial skeleton — the Python half of the Brewtality-3-16 template. All
  company identity is `{{PLACEHOLDER}}` in `config/*.json`.
- `scraper/self_healing.py` — generic selector cascade: `first_match`,
  `locate_articles` (CSS → JSON-LD → regex `<article>` → none),
  `json_ld_job_postings`, `css_text`/`structural_text`/`regex_text`.
- `scraper/self_healing.py::scrapling_text` — **optional** adaptive layer
  (`adaptive=True, auto_save=True`); a no-op when `scrapling` is not installed.
- `scraper/validate.py` — `validate_job`, `filter_valid_jobs`,
  `assert_scrape_yielded_jobs` (0-result canary).
- `scraper/fetch.py` — `requests` + retry / full-jitter exponential backoff,
  honours `Retry-After`.
- `scraper/parse.py`, `scraper/api.py`, `scraper/main.py` (scrape → validate →
  canary → upsert → diff summary).
- 53 pytest tests: each cascade level in isolation, all-fail logging, JSON-LD,
  `locate_articles` modes, parse fallbacks (renamed class / JSON-LD-only /
  regex `<article>` / unrecognisable page), validation rules, retry/backoff,
  main-level canary.
- `ai/AGENTS.md`, `ai/SELF-HEALING.md` (cascade in depth + JS↔Python parity).
- GitHub Actions: `tests.yml` (pytest on 3.10 / 3.12, plus an allowed-to-fail
  run with Scrapling), `scrape.yml` (daily + `autoheal` issue on failure).
