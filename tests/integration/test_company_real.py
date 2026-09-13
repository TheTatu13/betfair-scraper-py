"""Integration tests against the real ANAF/CUIScan and peviitor APIs.

Not part of the default `pytest -q` unit run's expectations in spirit -- they
self-skip (rather than fail) whenever either (a) the config is still the
template's own `{{PLACEHOLDER}}` values (nothing real to look up yet) or
(b) the network isn't reachable, so CI for the *template itself* stays green.
Once a company derives this template and fills in config/company.json, these
start doing real work -- mirrors the reference Python template's
tests/integration/test_company_real.py.
"""

from __future__ import annotations

import socket

import pytest

from scraper import anaf, api
from scraper.config import company as company_config

COMPANY_CIF = company_config["id"]
COMPANY_NAME = company_config["company"]


def _is_placeholder(value: str) -> bool:
    return isinstance(value, str) and value.startswith("{{")


def _reachable(host: str, port: int = 443, timeout: float = 3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
def _skip_until_derived():
    if _is_placeholder(COMPANY_CIF) or _is_placeholder(COMPANY_NAME):
        pytest.skip("template not yet derived -- config/company.json still has {{PLACEHOLDER}} values")


def test_anaf_returns_the_configured_company():
    if not (_reachable("demoanaf.ro") or _reachable("cuiscan.ro")):
        pytest.skip("neither demoanaf.ro nor cuiscan.ro reachable")
    data = anaf.get_company_from_anaf(COMPANY_CIF)
    if not data:
        pytest.skip("ANAF/CUIScan returned no data")
    assert str(data.get("cui")) == str(COMPANY_CIF)


def test_peviitor_solr_query_succeeds():
    host = api.API_BASE.split("://", 1)[1].split("/", 1)[0]
    if not _reachable(host):
        pytest.skip(f"{host} not reachable")
    result = api.query_solr(COMPANY_CIF)
    assert "numFound" in result
    assert "docs" in result
