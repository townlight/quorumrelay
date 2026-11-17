"""Synthetic execution of the pinned vendor editor response and exact GET."""
import base64
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers import gworks_editor as editor

URL = editor.ORIGIN + "/cms/secure/city/meeting/5017"
NS = "//api.dev.gworks.cloud/city/1311/cms"
SOURCE = Source("gworks", URL, namespace=NS, input_format=editor.FORMAT,
                options={"gworks_city_id": "1311"})
ROW = {"cms_meeting.id": 5017, "cms_meeting.title": "Council hearing",
       "cms_meeting.meeting_ts": "2026-11-16T18:00:00-07:00",
       "cms_meeting.location": "Chambers", "cms_meeting.mod_ts": "unparsed vendor version",
       "cms_meeting.agenda_published_fl": True, "cms_meeting.minutes_published_fl": False,
       "cms_meeting.data": [{"type": "section", "title": "Public business", "items": [
           {"type": "agenda-item", "value": "Bridge repair", "minute": "Discussion postponed",
            "files": [{"filename": "private.pdf", "usetype": "official"}], "future": [None, False]}]}],
       "cms_meeting.files": [{"name": "packet.pdf", "unknown": True}],
       "unknown": {"preserve": "café"}}


def content(row=None):
    return json.dumps(ROW if row is None else row, ensure_ascii=False).encode()


def context():
    return OperationContext(tenant="test-client", allowed_namespaces=frozenset({NS}), credentials={
        "gworks": {"tenant": "test-client", "origin": editor.ORIGIN, "city_id": "1311",
                   "allowed_namespaces": [NS], "token": "synthetic-private-token"}})


class Server:
    def __init__(self):
        self.calls = []
        self.raw, self.url, self.mime, self.status = content(), URL, "application/json", 200
        self.after = lambda: None

    def request(self, url, **options):
        self.calls.append((url, options))
        self.after()
        return Response(self.url, self.raw, self.mime, self.status)


def test_sdk_read_identity_text_raw_persistence_and_all_exports(tmp_path):
    server, caller = Server(), context()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "editor.sqlite"), provider_transport=server)
    result = engine.fetch(SOURCE, context=caller)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["namespace"] == NS and record["identity"]["external_id"] == "5017"
    assert record["original"] == ROW
    normalized = record["normalized"]
    assert normalized["scheduled_start"] == "2026-11-16T18:00:00-07:00"
    assert normalized["source_updated"] == ROW["cms_meeting.mod_ts"]
    assert normalized["source_status"]["minutes_published_fl"] is False
    assert normalized["source_files"] == ROW["cms_meeting.files"]
    section, item = normalized["agenda_items"]
    assert item["parent_item_external_id"] == section["external_id"]
    assert item["minutes"] == "Discussion postponed" and item["native_item_id"] is None
    assert not normalized["documents"] and not item["documents"]
    assert item["source_files"][0]["usetype"] == "official"
    assert [entry["text"] for entry in record["text"]] == ["Bridge repair", "Discussion postponed"]
    assert base64.b64decode(result.data["capture"]["content_base64"]) == server.raw
    assert not result.coverage["catalog_complete"]
    assert "synthetic-private-token" not in json.dumps(result.public_dict())
    url, options = server.calls[0]
    assert url == URL and options["method"] == "GET"
    assert options["allowed_origins"] == (editor.ORIGIN,) and options["allow_redirects"] is False
    assert options["headers"]["Authorization"] == "Bearer synthetic-private-token"
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "editor.sqlite"))
    found = reopened.execute("search", {"query": {"terms": ["postponed"]}}, context=caller)
    assert len(found.data["hits"]) == 1, found.public_dict()
    for format in ("json", "jsonl", "zip"):
        exported = engine.execute("export", {"bundle": result.data, "format": format}, context=caller)
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("field,value", [
    ("cms_meeting.id", 5018), ("cms_meeting.id", True), ("cms_meeting.title", ""),
    ("cms_meeting.data", "[]"), ("cms_meeting.files", None),
    ("cms_meeting.data", [{"title": "x", "items": [{"value": "x", "minute": None, "files": []}]}]),
    ("cms_meeting.agenda_published_fl", 1),
])
def test_bad_identity_or_shape_cannot_succeed(field, value):
    row = deepcopy(ROW)
    row[field] = value
    result = create_engine().normalize(SOURCE, content(row), input_format=editor.FORMAT)
    assert result.status == "failed"


@pytest.mark.parametrize("field,value", [
    ("origin", "https://api.gworks.cloud"), ("tenant", "another"),
    ("city_id", "2"), ("allowed_namespaces", NS), ("allowed_namespaces", []),
    ("token", "x\r\nHeader:bad"),
])
def test_credentials_checked_before_network(field, value):
    server, caller = Server(), context()
    caller.credentials["gworks"][field] = value
    result = create_engine(provider_transport=server).fetch(SOURCE, context=caller)
    assert result.status == "failed" and not server.calls


@pytest.mark.parametrize("change", [
    {"url": URL.replace("api.dev.", "api.")}, {"url": URL + "?tenant=other"},
    {"url": URL + "/"}, {"namespace": "//files.frontdeskgworks.com/city/1311/cms/data.json"},
    {"options": {"gworks_city_id": 1311}}, {"options": {}},
])
def test_development_and_production_are_not_aliased(change):
    source = Source.from_dict({**SOURCE.public_dict(), **change})
    assert create_engine().normalize(source, content(), input_format=editor.FORMAT).status == "failed"


@pytest.mark.parametrize("case", ["401", "mime", "redirect", "bytes", "cancel", "deadline", "wrong_id"])
def test_response_boundaries(case, monkeypatch):
    server, caller, bounds = Server(), context(), Bounds()
    if case == "401":
        server.status = 401
    elif case == "mime":
        server.mime = "text/html"
    elif case == "redirect":
        server.url = URL.replace("api.dev.", "api.")
    elif case == "bytes":
        server.raw += b" " * 4096
        bounds = replace(bounds, transfer_bytes=4096)
    elif case == "cancel":
        server.after = caller.cancellation.set
    elif case == "wrong_id":
        server.raw = content({**ROW, "cms_meeting.id": 8})
    else:
        now = [100.0]
        monkeypatch.setattr(editor, "monotonic", lambda: now[0])
        server.after = lambda: now.__setitem__(0, 10000.0)
    result = create_engine(provider_transport=server).fetch(SOURCE, context=caller, bounds=bounds)
    assert result.status == ("cancelled" if case == "cancel" else "failed")


def test_saved_input_needs_no_credentials_and_discovery_never_calls_detail_as_catalog():
    server = Server()
    engine = create_engine(provider_transport=server)
    assert engine.normalize(SOURCE, content(), input_format=editor.FORMAT).status == "completed"
    saved = engine.execute("discover", {"source": SOURCE.public_dict()}, content=content())
    assert saved.status == "partial" and saved.coverage["catalog_complete"] is False
    assert engine.discover(SOURCE).status == "failed"
    assert not server.calls
    denied = engine.normalize(SOURCE, content(), input_format=editor.FORMAT,
                              context=OperationContext(allowed_namespaces=frozenset({"other"})))
    assert denied.status == "failed"


def test_unknown_time_and_native_string_id_preserved_without_epoch_guess():
    row = {**ROW, "cms_meeting.id": "5017", "cms_meeting.meeting_ts": 1794880800000}
    result = create_engine().normalize(SOURCE, content(row), input_format=editor.FORMAT)
    assert result.status == "completed"
    record = result.data["records"][0]
    assert record["normalized"]["scheduled_start"] is None
    assert record["normalized"]["source_timestamp"] == row["cms_meeting.meeting_ts"]
    assert record["original"] == row


def test_pinned_vendor_sources_and_request_shape():
    root = Path(__file__).parents[1] / "docs/capabilities/evidence/gworks-development-editor"
    manifest = json.loads((root / "source.json").read_text())
    for file in manifest["files"]:
        assert sha256((root / file["path"]).read_bytes()).hexdigest() == file["sha256"]
    client = (root / "meeting-editor.js").read_text(encoding="utf-8")
    assert "uri: `/cms/secure/city/meeting/${messId}`" in client
    assert "require('./data').set(data)" in client
    assert "for (const section of data['cms_meeting.data'])" in client

