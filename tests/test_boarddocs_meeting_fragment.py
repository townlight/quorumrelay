"""Archived vendor fragments from a pinned third-party repository; no live claim."""

import base64
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle

FORMAT = "boarddocs-public-meeting-html"
SOURCE = Source("boarddocs", "https://go.boarddocs.com/mi/grand/Board.nsf/Public",
                input_format=FORMAT, options={"boarddocs_committee_id": "explicit-committee"})
FIXTURES = Path(__file__).parent / "fixtures/boarddocs-public"


@pytest.mark.parametrize("file,identifier,day,term", [
    ("grand-detail-20240522.html", "D5CSV7744EBE", "2024-05-22", "Multipurpose"),
    ("grand-detail-20260701.html", "DVDHLR490E4B", "2026-07-01", "scholar"),
])
def test_archived_native_fragment_sqlite_retry_reopen_search_and_exact_zip(tmp_path, file, identifier, day, term):
    raw = (FIXTURES / file).read_bytes()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "saved.sqlite"))
    result = engine.normalize(SOURCE, raw, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    bundle = result.data
    record = bundle["records"][0]
    normalized = record["normalized"]
    assert record["identity"]["external_id"] == identifier
    listing = engine.normalize(SOURCE, (FIXTURES / "grand-list.json").read_bytes(),
                               input_format="boarddocs-public-meetings-json")
    assert listing.status == "completed", listing.public_dict()
    previous = next(r for r in listing.data["records"] if r["identity"]["external_id"] == identifier)
    assert record["identity"] == previous["identity"]
    assert normalized["meeting_date"] == day and normalized["time_zone_status"] == "unknown"
    assert "scheduled_at" not in normalized  # Time embedded in title is not a structured instant.
    assert normalized["documents"] == normalized["recordings"] == normalized["agenda_items"] == []
    assert record["text"][0]["text"] == normalized["description"]
    assert "View the Agenda" not in record["text"][0]["text"]
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "saved.sqlite"))
    found = reopened.execute("search", {"query": {"terms": [term]}})
    assert len(found.data["hits"]) == 1
    archive = reopened.execute("export", {"bundle": bundle, "format": "zip"})
    restored = read_bundle(base64.b64decode(archive.data["content_base64"]), format="zip")
    assert restored == bundle
    assert base64.b64decode(restored["capture"]["content_base64"]) == raw


@pytest.mark.parametrize("old,new", [
    (b'data-clipboard-text=', b'data-removed='),
    (b'base="DVDHLR490E4B"', b'base="OTHER"'),
    (b'/mi/grand/Board.nsf/goto', b'/mi/other/Board.nsf/goto'),
    (b'goto?open&id=DVDHLR490E4B', b'goto?open&id=DVDHLR490E4B&extra=1'),
    (b'class="meeting-name"', b'class="absent-name"'),
    (b'class="meeting-date"', b'class="absent-date"'),
    (b'class="meeting-description"', b'class="absent-description"'),
    (b'id="view-meeting"', b'id="absent-view"'),
])
def test_changed_or_mismatched_native_fields_fail_without_guessing(old, new):
    raw = (FIXTURES / "grand-detail-20260701.html").read_bytes()
    assert old in raw
    result = create_engine().normalize(SOURCE, raw.replace(old, new), input_format=FORMAT)
    assert result.status == "failed"


def test_unmapped_date_stays_literal_and_hidden_script_is_not_meeting_text():
    raw = (FIXTURES / "grand-detail-20260701.html").read_bytes()
    raw = raw.replace(b"Wednesday, July 1, 2026</div>", b"Vendor date unknown<script>invented()</script></div>")
    result = create_engine().normalize(SOURCE, raw, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    row = result.data["records"][0]
    assert row["normalized"]["meeting_date"] is None
    assert row["normalized"]["source_date"] == "Vendor date unknown"
    assert "invented" not in str(row["text"])


def test_saved_parser_honors_size_and_scope_without_network():
    raw = (FIXTURES / "grand-detail-20260701.html").read_bytes()
    engine = create_engine()
    assert engine.normalize(SOURCE, raw, input_format=FORMAT, bounds=Bounds(parser_bytes=100)).status == "failed"
    context = OperationContext(allowed_namespaces=frozenset({"other"}))
    assert engine.normalize(SOURCE, raw, input_format=FORMAT, context=context).status == "failed"
