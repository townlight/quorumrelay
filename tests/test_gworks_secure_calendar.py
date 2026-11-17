"""Saved vendor-client calendar shape; synthetic responses, no account access."""

import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle

FORMAT = "gworks-secure-calendar-json"
URL = "https://api.gworks.cloud/cms/secure/city/meeting/list"
NS = "//files.frontdeskgworks.com/city/1311/cms/data.json"
SOURCE = Source("gworks", URL, namespace=NS, input_format=FORMAT, options={"gworks_city_id": "1311"})
ROW = {"cms_meeting.id": 5017, "cms_meeting.title": "Council safety hearing",
       "cms_meeting.meeting_ts": "2026-11-09T18:00:00", "cms_meeting.agenda_published_fl": False,
       "cms_meeting.minutes_published_fl": True, "unknown": {"keep": [None, False, "café"]}}


def content(rows=None):
    return json.dumps({"data": [deepcopy(ROW)] if rows is None else rows, "unknown_envelope": [None, 0]}).encode()


def test_native_identity_city_isolation_sqlite_reopen_search_and_original_zip(tmp_path):
    engine = create_engine(storage=SQLiteStorage(tmp_path / "saved.sqlite"))
    original = content()
    result = engine.normalize(SOURCE, original, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "5017" and record["identity"]["namespace"] == NS
    assert record["original"] == ROW
    normalized = record["normalized"]
    assert normalized["source_status"] == {"agenda_published_fl": False, "minutes_published_fl": True}
    assert normalized["scheduled_start"] == "2026-11-09T18:00:00"
    assert normalized["city_binding"] == "configured_city_not_asserted_by_response"
    assert normalized["documents"] == []  # A publication flag is not a locator.
    baseline = engine.normalize(Source("gworks", "https://files.frontdeskgworks.com/city/1311/cms/data.json"),
        (Path(__file__).parent / "fixtures/baseline/gworks-1311.response").read_bytes(),
        input_format="gworks-frontdesk-json")
    native = next(r for r in baseline.data["records"] if r["identity"]["external_id"] == "5017")
    assert all(native["identity"][k] == record["identity"][k]
               for k in ("provider", "namespace", "record_type", "external_id", "parent"))
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "saved.sqlite"))
    found = reopened.execute("search", {"query": {"terms": ["safety"]}})
    assert len(found.data["hits"]) == 1
    archive = reopened.execute("export", {"bundle": result.data, "format": "zip"})
    restored = read_bundle(base64.b64decode(archive.data["content_base64"]), format="zip")
    assert restored == result.data
    assert base64.b64decode(restored["capture"]["content_base64"]) == original
    denied = engine.normalize(SOURCE, original, input_format=FORMAT,
                              context=OperationContext(allowed_namespaces=frozenset({"other"})))
    assert denied.status == "failed"


@pytest.mark.parametrize("field,value", [
    ("cms_meeting.id", True), ("cms_meeting.id", "5017"), ("cms_meeting.id", 0),
    ("cms_meeting.title", ""), ("cms_meeting.title", None),
    ("cms_meeting.meeting_ts", True), ("cms_meeting.agenda_published_fl", "false"),
    ("cms_meeting.minutes_published_fl", 1),
])
def test_wrong_wire_types_fail_without_reinterpreting_public_listing_flags(field, value):
    row = deepcopy(ROW)
    row[field] = value
    assert create_engine().normalize(SOURCE, content([row]), input_format=FORMAT).status == "failed"


@pytest.mark.parametrize("raw", [b'[]', b'{"data":null}', b'{"meetings":[]}',
                                  content([ROW, ROW]), content([{"id": 5017, "title": "Wrong public shape"}])])
def test_wrong_envelope_duplicate_native_ids_and_static_shape_fail(raw):
    assert create_engine().normalize(SOURCE, raw, input_format=FORMAT).status == "failed"


@pytest.mark.parametrize("timestamp,day,start", [
    (1794250800000, None, None), ("unqualified vendor time", None, None),
    ("2026-11-09", "2026-11-09", None),
    ("2026-11-09T18:00:00-07:00", "2026-11-09", "2026-11-09T18:00:00-07:00"),
])
def test_time_is_preserved_without_numeric_unit_or_midnight_inference(timestamp, day, start):
    row = deepcopy(ROW)
    row["cms_meeting.meeting_ts"] = timestamp
    row.pop("cms_meeting.minutes_published_fl")
    result = create_engine().normalize(SOURCE, content([row]), input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    value = result.data["records"][0]["normalized"]
    assert (value["source_timestamp"], value["meeting_date"], value["scheduled_start"]) == (timestamp, day, start)
    assert value["source_status"]["minutes_published_fl"] is None


@pytest.mark.parametrize("change", [{"url": URL + "?city=1311"}, {"url": URL.replace("https:", "http:")},
                                   {"options": {}}, {"options": {"gworks_city_id": 1311}},
                                   {"options": {"gworks_city_id": "0"}}, {"namespace": "//wrong"}])
def test_exact_endpoint_explicit_city_and_matching_namespace_required(change):
    source = Source.from_dict({**SOURCE.public_dict(), **change})
    assert create_engine().normalize(source, content(), input_format=FORMAT).status == "failed"


def test_discovery_never_turns_saved_response_mapping_into_live_get_or_account_acquisition():
    class Transport:
        def request(self, *args, **kwargs):
            pytest.fail("Saved secure format must not issue a live request")
    engine = create_engine(provider_transport=Transport())
    result = engine.discover(SOURCE)
    assert result.status == "failed"
    saved = engine.execute("discover", {"source": SOURCE.public_dict()}, content=content())
    assert saved.status == "partial", saved.public_dict()
    assert not saved.errors and len(saved.data["records"]) == 1
    assert saved.coverage["catalog_complete"] is False
