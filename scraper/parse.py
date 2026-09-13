"""Parse the company's careers listing into job dicts.

The only site-specific module. Every field goes through the self-healing
cascade in ``scraper.self_healing`` driven by ``config/scraper.json``
(``{{PLACEHOLDER}}`` selectors in the template — tests pass their own).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

from .config import scraper
from .self_healing import (
    first_match,
    locate_articles,
    regex_text,
    scrapling_text,
    text_from_html,
)

log = logging.getLogger("scraper.parse")

_SEL = scraper["selectors"]

# Romanian ș/ț have no NFD decomposition, so map them explicitly.
_DIACRITICS = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t"})
_NONWORD = re.compile(r"[^a-z0-9]+")
_HN_RX = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.I | re.S)
_A_RX = re.compile(r"<a\b[^>]*>(.*?)</a>", re.I | re.S)
_DMY_RX = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_ISO_RX = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?")


def slugify(text: str) -> str:
    lowered = str(text).lower().translate(_DIACRITICS)
    stripped = "".join(c for c in unicodedata.normalize("NFD", lowered) if unicodedata.category(c) != "Mn")
    return _NONWORD.sub("-", stripped).strip("-")


def iso_z(dt: datetime) -> str:
    """UTC timestamp as ``2026-09-30T23:59:59.000Z`` -- millisecond precision,
    literal ``Z`` offset. Solr's date fields parse only this exact shape;
    Python's own ``datetime.isoformat()`` instead emits microseconds and a
    ``+00:00`` offset (e.g. ``...23:59:59.000000+00:00``), which Solr rejects
    with a 400. JS's ``Date.prototype.toISOString()`` always produces this
    shape natively, so this is what keeps the two in parity."""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_deadline(text: str | None) -> str | None:
    """'30.09.2026' -> '2026-09-30T23:59:59.000Z' (end of the closing day).
    Also accepts an ISO date (schema.org JobPosting ``validThrough``)."""
    if not text:
        return None
    s = str(text)

    m = _DMY_RX.search(s)
    if m:
        dd, mm, yyyy = (int(x) for x in m.groups())
        try:
            return iso_z(datetime(yyyy, mm, dd, 23, 59, 59, tzinfo=timezone.utc))
        except ValueError:
            return None

    m = _ISO_RX.search(s)
    if m:
        try:
            dt = datetime.fromisoformat(m.group(0).replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:  # a bare date means UTC, not the runner's local tz
            dt = dt.replace(tzinfo=timezone.utc)
        return iso_z(dt)

    return None


def _clean_title(raw: str | None) -> str | None:
    text = text_from_html(raw) if raw and "<" in str(raw) else (str(raw).strip() if raw else None)
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()[:200]
    return text or None


def parse_listing(html: str, selectors: dict | None = None) -> list[dict]:
    """Parse the open-positions page into ``{title, expirationdate}`` items,
    self-healing through the selector cascade (default: ``config/scraper.json``;
    tests pass ``selectors`` explicitly):

        article blocks:  CSS list -> JSON-LD JobPosting -> regex <article>
        title:           CSS list -> Scrapling (optional) -> regex <hN>/<a>
        deadline:        CSS list -> date regex over the whole block text
    """
    sel = selectors if selectors is not None else _SEL
    articles = locate_articles(html, sel["jobArticle"])
    items: list[dict] = []
    strategies: set[str] = set()
    seen: set[str] = set()  # a broad fallback selector can match nested blocks

    if articles.mode == "jsonld":
        for posting in articles.json_ld:
            title = _clean_title(posting.get("title"))
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            strategies.add("jsonld")
            items.append({"title": title, "expirationdate": parse_deadline(posting.get("validThrough"))})
        log.info("parse_listing: %d items via JSON-LD JobPosting", len(items))
        return items

    title_primary = sel["jobTitle"][0] if isinstance(sel["jobTitle"], list) else sel["jobTitle"]
    for i, scope in enumerate(articles.scopes):
        match = first_match(
            f"title[{i}]",
            [
                ("css-cascade", lambda scope=scope: scope.text(sel["jobTitle"]).value),
                scrapling_text(scope.raw(), title_primary),
                regex_text(scope.raw(), _HN_RX),
                regex_text(scope.raw(), _A_RX),
            ],
            silent=True,
        )
        title = _clean_title(match.value)
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        if match.strategy:
            strategies.add(match.strategy)

        meta = scope.text(sel["jobMeta"]).value
        deadline = parse_deadline(meta) or parse_deadline(scope.full_text())
        items.append({"title": title, "expirationdate": deadline})

    tag = f" [{', '.join(sorted(strategies))}]" if strategies else ""
    log.info("parse_listing: %d items via %s%s", len(items), articles.mode, tag)
    return items
