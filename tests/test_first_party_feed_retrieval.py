"""Configured RFC calendar feed retrieval, separately from municipal-page link discovery."""

import base64
from pathlib import Path
import json

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures/baseline"
CASE = next(c for c in json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
            if c["connector"] == "first-party")
CAPTURE = (ROOT / CASE["file"]).read_bytes()
SOURCE = Source("first-party", CASE["source_url"], input_format=CASE["input_format"])


class Feed:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert url == SOURCE.url
        assert kwargs["byte_limit"] >= len(CAPTURE)
        return Response(url, CAPTURE, "text/calendar; charset=utf-8")


def test_configured_feed_discover_and_fetch_keep_original_uid_identity_and_capture():
    transport = Feed()
    engine = create_engine(provider_transport=transport)
    saved = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format,
                             bounds=Bounds(max_records=10000))
    for operation in (engine.discover, engine.fetch):
        result = operation(SOURCE, bounds=Bounds(max_records=10000))
        assert result.status == "partial" and not result.errors, result.public_dict()
        assert len(result.data["records"]) == CASE["original_record_count"] == 1307
        for fetched, original in zip(result.data["records"], saved.data["records"], strict=True):
            for key in ("identity", "normalized", "original", "normalized_sha256", "text", "extensions"):
                assert fetched[key] == original[key]
        assert result.coverage.get("catalog_complete") is not True
        assert result.data["captures"][0]["sha256"] == CASE["sha256"]
        assert base64.b64decode(result.data["captures"][0]["content_base64"]) == CAPTURE
    assert transport.calls == [SOURCE.url, SOURCE.url]


def test_static_feed_resume_preserves_record_budget_without_repeating_identities():
    engine = create_engine(provider_transport=Feed())
    first = engine.discover(SOURCE, bounds=Bounds(max_records=2))
    assert first.status == "partial" and len(first.data["records"]) == 2
    cursor = first.coverage["checkpoint"]
    assert cursor
    second = engine.discover(SOURCE, bounds=Bounds(max_records=2, checkpoint=cursor))
    assert second.status == "partial" and len(second.data["records"]) == 2
    assert {r["identity"]["external_id"] for r in first.data["records"]}.isdisjoint(
        {r["identity"]["external_id"] for r in second.data["records"]})
    assert first.data["captures"][0]["sha256"] == second.data["captures"][0]["sha256"]


def test_switching_saved_normalization_to_fetch_is_an_unchanged_import(tmp_path):
    from quorumrelay.storage import SQLiteStorage
    engine = create_engine(storage=SQLiteStorage(tmp_path / "calendar.sqlite"), provider_transport=Feed())
    normalized = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format, bounds=Bounds(max_records=2))
    fetched = engine.fetch(SOURCE, bounds=Bounds(max_records=2))
    assert engine.execute("import_bundle", {"bundle": normalized.data, "persist": True}).status == "completed"
    imported = engine.execute("import_bundle", {"bundle": fetched.data, "persist": True})
    assert imported.status == "completed", imported.public_dict()
    assert {c["outcome"] for c in imported.data["changes"]} == {"unchanged"}
