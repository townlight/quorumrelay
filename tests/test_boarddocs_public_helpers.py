"""Pinned third-party BoardDocs reader mapping; synthetic inputs only."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from civic_data_connectors.models import Source
from civic_data_connectors.providers.boarddocs_public import (
    DETAIL_FORMAT,
    LISTING_FORMAT,
    detail_bundle,
    listing_bundle,
    parse_bundle,
    parse_listing,
    request_specs,
)


SOURCE = Source("boarddocs", "https://go.boarddocs.com/mi/grand/Board.nsf/Public",
                options={"boarddocs_committee_id": "C55TD0000001"})
LISTING = json.dumps([{"unique": "C55TD0000001", "numberdate": "11/12/2026", "unid": "A1B2"}],
                     separators=(",", ":")).encode()
DETAIL = b'''<div class="print-meeting-date">November 12, 2026</div>
<div class="print-meeting-name">Board of Trustees</div>
<div class="public-file"><a href="/mi/grand/Board.nsf/file.pdf">Agenda PDF</a></div>
<main>Call to order. Budget review.</main>'''


def test_listing_parser_preserves_observed_fields_and_accepts_empty_array():
    rows = parse_listing(SOURCE, LISTING)
    assert rows == [{"meeting_id": "C55TD0000001", "numberdate": "11/12/2026",
                     "unid": "A1B2", "original": {"unique": "C55TD0000001",
                     "numberdate": "11/12/2026", "unid": "A1B2"}}]
    assert parse_listing(SOURCE, b"[]") == []
    with pytest.raises(ValueError, match="repeated"):
        parse_listing(SOURCE, LISTING[:-1] + b',{"unique":"C55TD0000001"}]')
    with pytest.raises(ValueError, match="parser byte"):
        parse_listing(SOURCE, LISTING, parser_bytes=len(LISTING) - 1)


def test_listing_and_print_agenda_bundles_retain_raw_and_partial_fields():
    listing_row = parse_listing(SOURCE, LISTING)[0]
    listing = listing_bundle(SOURCE, "boarddocs:go.boarddocs.com/mi/grand", LISTING, [listing_row])
    record = listing["records"][0]
    assert record["identity"]["external_id"] == "C55TD0000001"
    assert record["normalized"]["title"] is None
    assert record["normalized"]["meeting_date"] == "2026-11-12"
    assert base64.b64decode(listing["capture"]["content_base64"]) == LISTING

    detail = detail_bundle(SOURCE, "boarddocs:go.boarddocs.com/mi/grand", DETAIL,
                           "C55TD0000001", listing_row)
    record = detail["records"][0]
    assert record["normalized"]["title"] == "Board of Trustees"
    assert record["normalized"]["meeting_date"] == "2026-11-12"
    assert record["normalized"]["source_public_file_links"] == ["/mi/grand/Board.nsf/file.pdf"]
    assert record["normalized"]["documents"] == []
    assert record["text"][0]["text"] == "November 12, 2026 Board of Trustees Agenda PDF Call to order. Budget review."
    assert record["text"][0]["completeness"] == "third_party_reader_rendered_text_partial"
    assert base64.b64decode(detail["capture"]["content_base64"]) == DETAIL


def test_saved_capture_parser_maps_listing_but_needs_listing_identity_for_detail():
    listing = parse_bundle(SOURCE, "boarddocs:go.boarddocs.com/mi/grand", LISTING, LISTING_FORMAT)
    assert len(listing["records"]) == 1
    detail = parse_bundle(SOURCE, "boarddocs:go.boarddocs.com/mi/grand", DETAIL, DETAIL_FORMAT)
    assert detail["records"] == []
    assert detail["extensions"]["detail_parse"]["record_identity_status"] == \
        "unavailable_without_the_selected_listing_meeting_id"


def test_request_specs_are_literal_guarded_posts_without_browser_identity():
    specs = request_specs(SOURCE, "C55TD0000001")
    listing, detail = specs["listing"], specs["detail"]
    assert (listing["method"], listing["url"]) == (
        "POST", "https://go.boarddocs.com/mi/grand/Board.nsf/BD-GetMeetingsList?open")
    assert parse_qs(listing["body"].decode()) == {"current_committee_id": ["C55TD0000001"]}
    assert (detail["method"], detail["url"]) == (
        "POST", "https://go.boarddocs.com/mi/grand/Board.nsf/PRINT-AgendaDetailed")
    assert parse_qs(detail["body"].decode()) == {
        "id": ["C55TD0000001"], "current_committee_id": ["C55TD0000001"]}
    for spec in (listing, detail):
        assert spec["allowed_origins"] == ("https://go.boarddocs.com",)
        assert spec["allow_redirects"] is False
        assert "user-agent" not in {key.casefold() for key in spec["headers"]}
        assert urlsplit(spec["url"]).hostname == "go.boarddocs.com"
    with pytest.raises(ValueError, match="safe listing-issued"):
        request_specs(SOURCE, "../other")


@pytest.mark.parametrize("url", [
    "https://go.boarddocs.com/mi/grand/Board.nsf/BD-GetMeetingsList?open",
    "https://example.com/mi/grand/Board.nsf/Public",
    "http://go.boarddocs.com/mi/grand/Board.nsf/Public",
    "https://go.boarddocs.com/mi/grand/Board.nsf/Public/",
])
def test_source_must_be_exact_public_root(url):
    source = Source("boarddocs", url, options={"boarddocs_committee_id": "C55TD0000001"})
    with pytest.raises(ValueError, match="exact HTTPS"):
        request_specs(source)


def test_unsafe_committee_configuration_is_rejected():
    bad = Source("boarddocs", SOURCE.url, options={"boarddocs_committee_id": "../admin"})
    with pytest.raises(ValueError, match="explicit safe"):
        request_specs(bad)


def test_compact_date_and_direct_public_anchors_preserve_declared_links_only():
    rows = parse_listing(SOURCE, b'[{"unique":"MEETING1","numberdate":"20261112"}]')
    bundle = listing_bundle(SOURCE, "boarddocs:test", b"[]", rows)
    assert bundle["records"][0]["normalized"]["meeting_date"] == "2026-11-12"
    html = DETAIL + b'''<a class="public-file" unique="FILE1" href="/public.pdf">Public</a>
<div class="public-file"><a class="private-file" href="/private.pdf">Private</a></div>
<div class="admin-files"><a class="public-file" href="/admin.pdf">Admin</a></div>
<template><div class="public-file"><a href="/template.pdf">Template</a></div></template>
<a class="file" href="/unclassified.pdf">Unclassified</a>
<a class="public-file" href="/public.pdf">Duplicate</a>'''
    detail = detail_bundle(SOURCE, "boarddocs:test", html, "MEETING1", rows[0])
    assert detail["records"][0]["normalized"]["source_public_file_links"] == [
        "/mi/grand/Board.nsf/file.pdf", "/public.pdf"]
    assert detail["records"][0]["normalized"]["documents"] == []
