# Changelog

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
