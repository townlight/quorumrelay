"""Retained readers through actual shared persistence, search and interchange; no network."""

import base64
import json
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.storage import SQLiteStorage


@pytest.mark.parametrize("provider,host,fixture,input_format,external_id,title_field", [
    ("cablecast", "reflect-cityofloveland-co.cablecast.tv", "cablecast/show-746.json",
     "cablecast-show-json", "746", "title"),
    ("civicweb", "cilovelandco.civicweb.net", "civicweb-listing/loveland-meetings.json",
     "civicweb-meetings-json", "18421", "Name"),
])
def test_saved_reader_records_persist_search_reopen_and_roundtrip(
        tmp_path, provider, host, fixture, input_format, external_id, title_field):
    raw = (Path(__file__).parent / "fixtures" / fixture).read_bytes()
    payload = json.loads(raw)
    source_row = payload["show"] if provider == "cablecast" else next(
        row for row in payload if str(row["Id"]) == external_id)
    title = source_row[title_field]
    database = tmp_path / "records.sqlite"
    owner = create_engine(storage=SQLiteStorage(database))
    normalized = owner.normalize(Source(provider, f"https://{host}/"), raw, input_format=input_format)
    assert normalized.status == "completed", normalized.public_dict()
    request = {"result": normalized.public_dict(), "persist": True}
    imported = owner.execute("import_bundle", request)
    assert imported.status == "completed", imported.public_dict()
    repeated = owner.execute("import_bundle", request)
    assert all(change["outcome"] == "unchanged" for change in repeated.data["changes"])

    reopened = create_engine(storage=SQLiteStorage(database))
    found = reopened.execute("search", {"query": {"phrases": [title], "record_types": ["meeting"]}})
    # These readers supply metadata, not complete document/caption text.
    assert found.status == "partial" and found.coverage["incomplete_text"], found.public_dict()
    hits = [hit for hit in found.data["hits"] if hit["identity"]["external_id"] == external_id]
    assert len(hits) == 1 and hits[0]["identity"]["provider"] == provider
    assert hits[0]["capture_sha256"] == normalized.data["capture"]["sha256"]
    assert hits[0]["citation_urls"]

    exported = reopened.execute("export", {"bundle": normalized.data, "format": "zip"})
    assert exported.status == "completed", exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / "destination.sqlite"))
    restored = destination.execute("import_bundle", {"format": "zip", "persist": True},
                                   content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    again = destination.execute("search", {"query": {"phrases": [title]}})
    assert {json.dumps(h["identity"], sort_keys=True) for h in again.data["hits"]} == {
        json.dumps(h["identity"], sort_keys=True) for h in found.data["hits"]}
