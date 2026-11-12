from pathlib import Path

import pytest

from civic_data_connectors.models import Source
from civic_data_connectors.providers.utah_public import search_rows

FIXTURE = Path(__file__).parent / "fixtures" / "utah-public-search-redacted.html"
SOURCE = Source(provider="utah-public-notice", url="https://www.utah.gov/pmn/search.html")


def test_observed_search_result():
    rows = search_rows(SOURCE, FIXTURE.read_bytes())
    assert len(rows) == 1
    meeting, raw, kind = rows[0]
    assert kind == "meeting" and meeting["external_id"] == "1120627"
    assert meeting["meeting_date"] == "2026-11-11" and meeting["source_start"] == "2026-11-11T13:00:00"
    assert meeting["time_zone_status"] == "unknown"
    assert meeting["body"] == "Ridges Estates Infrastructure Financing District"
    assert meeting["documents"][0]["url"] == "https://www.utah.gov/pmn/files/1510929.pdf"
    assert len(raw["cells"]) == 5


def test_empty_table_and_missing_table():
    assert search_rows(SOURCE, b'<table id="browseResults-table"><tr><th>Title</th></tr></table>') == []
    with pytest.raises(ValueError, match="no Utah"):
        search_rows(SOURCE, b"<html>no table</html>")


def test_rejects_foreign_identity_and_attachment():
    html = FIXTURE.read_text(encoding="utf-8")
    bad_notice = html.replace('/pmn/sitemap/notice/1120627.html', 'https://example.org/pmn/sitemap/notice/1120627.html')
    with pytest.raises(ValueError, match="No Utah"):
        search_rows(SOURCE, bad_notice.encode())
    bad_document = html.replace('/pmn/files/1510929.pdf', 'https://example.org/pmn/files/1510929.pdf')
    assert search_rows(SOURCE, bad_document.encode())[0][0]["documents"] == []
