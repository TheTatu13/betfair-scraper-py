import logging
import re
from datetime import datetime, timezone

from scraper.parse import iso_z, parse_deadline, parse_listing, slugify


def test_slugify_strips_diacritics():
    assert slugify("Key Account Manager – Vânzări Distribuitori") == "key-account-manager-vanzari-distribuitori"
    assert slugify("  Operator   exploatare și mentenanță  ") == "operator-exploatare-si-mentenanta"


def test_parse_deadline():
    assert parse_deadline("Apply by: 30.09.2026").startswith("2026-09-30T23:59:59")
    assert parse_deadline("2026-10-31").startswith("2026-10-31T00:00:00")
    assert parse_deadline("no deadline") is None
    assert parse_deadline(None) is None


# peviitor's Solr date fields parse only "...SSSZ" (millisecond precision,
# literal Z) -- the shape JS's Date.toISOString() emits natively. Python's own
# datetime.isoformat() instead emits microseconds + "+00:00", which Solr
# rejects with a 400. Both iso_z() and everything built on it must produce the
# Solr-safe shape, not Python's native one.
_ISO_Z_RX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_iso_z_matches_solr_date_format_not_pythons_native_isoformat():
    formatted = iso_z(datetime(2026, 9, 30, 23, 59, 59, 123456, tzinfo=timezone.utc))
    assert formatted == "2026-09-30T23:59:59.123Z"
    assert _ISO_Z_RX.match(formatted)


def test_parse_deadline_emits_solr_safe_z_format():
    assert _ISO_Z_RX.match(parse_deadline("Apply by: 30.09.2026"))
    assert _ISO_Z_RX.match(parse_deadline("2026-10-31"))


class TestParseListingHappyPath:
    def test_extracts_one_item_per_article(self, fixture_html, selectors):
        items = parse_listing(fixture_html("listing_ok.html"), selectors)
        assert [i["title"] for i in items] == ["Senior Widget Engineer – Platform", "Night Shift Operator"]

    def test_carries_deadline_when_present(self, fixture_html, selectors):
        items = parse_listing(fixture_html("listing_ok.html"), selectors)
        assert items[0]["expirationdate"].startswith("2026-09-30")
        assert items[1]["expirationdate"] is None

    def test_carries_the_real_scraped_url_not_a_guessed_slug(self, fixture_html, selectors):
        """The real href (which may carry an ID a title-slug guess could never
        reproduce, e.g. "/jobs/jr133930/software-architect/") must survive
        parse_listing untouched -- main.py resolves it against the listing
        page, it does not fall back to guessing when this is present."""
        items = parse_listing(fixture_html("listing_ok.html"), selectors)
        assert items[0]["url"] == "/careers/jr1/senior-widget-engineer/"
        assert items[1]["url"] == "/careers/jr2/night-shift-operator/"

    def test_empty_when_nothing_matches(self, selectors):
        assert parse_listing("<div>no jobs here</div>", selectors) == []

    def test_placeholder_config_does_not_crash(self):
        # default config ships .card-job — invalid CSS, must be skipped
        result = parse_listing("<main><div class='job'><h3 class='job__title'>X</h3></div></main>")
        assert isinstance(result, list)


class TestParseListingSelfHealing:
    def test_recovers_via_fallback_class_and_fallback_heading(self, fixture_html, selectors, caplog):
        with caplog.at_level(logging.INFO):
            items = parse_listing(fixture_html("listing_renamed_class.html"), selectors)
        titles = sorted(i["title"] for i in items)
        assert titles == ["Electrical Maintenance Technician", "QA Analyst"]
        qa = next(i for i in items if i["title"] == "QA Analyst")
        assert qa["expirationdate"].startswith("2026-11-15")

    def test_falls_back_to_json_ld(self, fixture_html, selectors):
        items = parse_listing(fixture_html("listing_jsonld_only.html"), selectors)
        assert sorted(i["title"] for i in items) == ["Field Sales Representative", "Product Manager"]
        rep = next(i for i in items if i["title"] == "Field Sales Representative")
        assert rep["expirationdate"].startswith("2026-10-31")

    def test_falls_back_to_regex_article_slicing(self, fixture_html, selectors):
        items = parse_listing(fixture_html("listing_regex_article.html"), selectors)
        assert len(items) == 1
        assert items[0]["title"] == "Duty Firefighter"
        assert items[0]["expirationdate"].startswith("2026-10-20")

    def test_unrecognisable_page_returns_empty_without_raising(self, fixture_html, selectors):
        # feeds the canary in main.run()
        assert parse_listing(fixture_html("listing_unrecognisable.html"), selectors) == []
