"""Captured production contract, single-field isolation and durable readback."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from test_gworks_write import ROW, P

ROOT = "https://api.gworks.cloud/cms/secure/city/meeting/"
NS = "//api.gworks.cloud/city/1311/cms"
SOURCE = {"provider": "gworks", "url": ROOT, "namespace": NS, "options": {"gworks_city_id": "1311"}}
CHANGE = {"key": "rename", "entity": "meeting", "operation": "update", "resource_id": "7",
          "fields": {"title": "Changed hearing"}}
LOCATION_CHANGE = {**CHANGE, "key": "relocate", "fields": {"location": "Other room"}}
SCHEDULE_CHANGE = {**CHANGE, "key": "reschedule",
                   "fields": {"scheduled_start": "2026-11-18T18:45:00-07:00"}}

class Vendor:
    mock = True
    def __init__(self):
        self.row, self.calls, self.fault = deepcopy(ROW), [], None
        self.readback_timestamp = None
    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert url == ROOT + "7" and deadline_seconds > 0
        assert headers["Authorization"] == "Bearer synthetic-secret"
        self.calls.append((method, url, body))
        if self.fault == "denied":
            return WriteResponse(403)
        if method == "GET":
            value = deepcopy(self.row)
            if self.fault == "wrong_id":
                value[P+"id"] = 8
            return WriteResponse(200, json.dumps(value).encode())
        assert method == "PUT"
        data = json.loads(body)
        previous_timestamp = self.row[P+"meeting_ts"]
        assert not any(P+k in data for k in ("agenda_published_fl", "minutes_published_fl", "archived_fl"))
        for key in ("title", "location", "meeting_ts"):
            self.row[P+key] = data[P+key]
        for key in ("data", "files"):
            self.row[P+key] = json.loads(data[P+key])
        if self.readback_timestamp is not None:
            self.row[P+"meeting_ts"] = self.readback_timestamp
        if self.fault == "schedule_ignored":
            self.row[P+"meeting_ts"] = previous_timestamp
        self.row[P+"mod_ts"] = "revision-2"
        if self.fault == "collateral":
            self.row["unrecognized"] = "changed"
        if self.fault == "published":
            self.row[P+"agenda_published_fl"] = True
        if self.fault == "timeout":
            raise TimeoutError()
        return WriteResponse(200, json.dumps({P+"id": 7}).encode())

def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({NS}),
        credentials={"gworks": {"tenant": "city", "city_id": "1311", "origin": "https://api.gworks.cloud",
          "allowed_namespaces": [NS], "token": "synthetic-secret", "meeting_ids": ["7"],
          "permissions": ["meeting:update"]}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor

def plan(engine, context, change=CHANGE, source=SOURCE):
    return engine.execute("plan_write", {"source": source, "changes": [change]}, context=context)

def approval(result):
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}

@pytest.mark.parametrize("change", [CHANGE, LOCATION_CHANGE, SCHEDULE_CHANGE])
def test_single_field_preserves_complete_snapshot_draft_and_reopen_no_replay(tmp_path, change):
    engine, context, vendor = setup(tmp_path)
    before = deepcopy(vendor.row)
    planned = plan(engine, context, change)
    approved = approval(planned)
    assert all(method == "GET" for method, _, _ in vendor.calls)
    result = engine.execute("commit_write", approved, context=context)
    assert result.status == "completed", result.public_dict()
    field, value = next(iter(change["fields"].items()))
    if field != "scheduled_start":
        before[P+field] = value
    before[P+"mod_ts"] = "revision-2"
    before[P+"meeting_ts"] = ("2026-11-19T01:45:00Z" if field == "scheduled_start"
                              else "2026-11-18T01:30:00Z")
    assert vendor.row == before
    again = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(again, default_adapters(vendor))
    result = again.execute("commit_write", approved, context=context)
    assert result.status == "completed"
    assert sum(method == "PUT" for method, _, _ in vendor.calls) == 1

@pytest.mark.parametrize("fields,entity,operation", [
    ({"title": "New title", "location": "Other room"}, "meeting", "update"),
    ({"scheduled_start": "2026-11-18T18:45:00-07:00", "title": "New title"}, "meeting", "update"),
    ({"scheduled_start": "2026-11-18T18:45:00-07:00", "location": "Other room"}, "meeting", "update"),
    ({"scheduled_start": "2026-11-18T18:45:00-07:00", "publication": "agenda"}, "meeting", "update"),
    ({"location": "Other room", "publication": "agenda"}, "meeting", "update"),
    ({"title": "New title", "publication": "agenda"}, "meeting", "update"),
    ({"title": "New title", "sections": []}, "meeting", "update"),
    ({"title": "New title"}, "meeting", "create"),
    ({"title": "New title"}, "media", "upload"),
    ({"title": "New title"}, "meeting", "delete")])
def test_other_operations_rejected_before_transport(tmp_path, fields, entity, operation):
    engine, context, vendor = setup(tmp_path)
    change = {**CHANGE, "fields": fields, "entity": entity, "operation": operation}
    assert plan(engine, context, change).status != "completed"
    assert vendor.calls == []

@pytest.mark.parametrize("change", [CHANGE, LOCATION_CHANGE, SCHEDULE_CHANGE])
@pytest.mark.parametrize("field,value", [
    ("agenda_published_fl", True), ("minutes_published_fl", True), ("archived_fl", True),
    ("template_fl", True), ("agenda_published_fl", None),
    ("agenda_published_dt", "2026-11-17"), ("minutes_published_dt", "2026-11-17")])
def test_ambiguous_or_published_draft_rejected(tmp_path, field, value, change):
    engine, context, vendor = setup(tmp_path)
    vendor.row[P+field] = value
    assert plan(engine, context, change).status != "completed"
    assert all(m == "GET" for m, _, _ in vendor.calls)

@pytest.mark.parametrize("key,value", [
    ("origin", "https://api.dev.gworks.cloud"), ("tenant", "other"), ("city_id", "99"),
    ("allowed_namespaces", ["//api.dev.gworks.cloud/city/1311/cms"]),
    ("meeting_ids", ["7", "8"]), ("meeting_ids", ["8"]), ("permissions", [])])
def test_exact_production_policy_no_fallback(tmp_path, key, value):
    engine, context, vendor = setup(tmp_path)
    context.credentials["gworks"][key] = value
    assert plan(engine, context).status != "completed"
    assert vendor.calls == []

@pytest.mark.parametrize("url", [ROOT.replace("api.gworks.cloud", "api.dev.gworks.cloud"),
    ROOT+"7", ROOT+"?x=1", ROOT.replace("https://", "http://"),
    ROOT.replace("api.gworks.cloud", "api.gworks.cloud.evil.example")])
def test_source_boundaries_reject_before_transport(tmp_path, url):
    engine, context, vendor = setup(tmp_path)
    assert plan(engine, context, source={**SOURCE, "url": url}).status != "completed"
    assert vendor.calls == []

@pytest.mark.parametrize("change", [CHANGE, LOCATION_CHANGE, SCHEDULE_CHANGE])
@pytest.mark.parametrize("fault", ["timeout", "collateral", "published"])
def test_uncertain_save_reconciles_without_repeat_put(tmp_path, fault, change):
    engine, context, vendor = setup(tmp_path)
    approved = approval(plan(engine, context, change))
    vendor.fault = fault
    result = engine.execute("commit_write", approved, context=context)
    if fault == "timeout":
        assert result.status != "completed"
    vendor.fault = None
    engine.execute("commit_write", approved, context=context)
    assert sum(m == "PUT" for m, _, _ in vendor.calls) == 1
    if fault != "timeout":
        assert result.status != "completed"

@pytest.mark.parametrize("change", [CHANGE, LOCATION_CHANGE, SCHEDULE_CHANGE])
def test_conflict_during_preflight_blocks_save(tmp_path, change):
    engine, context, vendor = setup(tmp_path)
    approved = approval(plan(engine, context, change))
    vendor.row[P+"agenda_published_fl"] = True
    assert engine.execute("commit_write", approved, context=context).status != "completed"
    assert all(m == "GET" for m, _, _ in vendor.calls)

def test_wrong_identity_read_blocks_plan(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = "wrong_id"
    assert plan(engine, context).status != "completed"
    assert all(m == "GET" for m, _, _ in vendor.calls)


@pytest.mark.parametrize("location", [None, 42, "", "abc", " Other room", "Other room ", "x" * 257])
def test_invalid_location_never_sends_put(tmp_path, location):
    engine, context, vendor = setup(tmp_path)
    assert plan(engine, context, {**LOCATION_CHANGE, "fields": {"location": location}}).status != "completed"
    assert all(m == "GET" for m, _, _ in vendor.calls)


@pytest.mark.parametrize("timestamp", [
    None, 42, "2026-11-18", "2026-11-18T18:45:00", "2026-11-18T18:45:01-07:00",
    "2026-11-18T18:45:00.000-07:00", "2026-11-18T18:45:00-00:00",
    "2026-11-18T18:45:00+01:99", "2026-11-18T18:45:00+24:00",
    "2026-02-30T18:45:00Z", "1999-12-31T18:45:00Z", "2051-01-01T18:45:00Z",
    "2050-12-31T23:45:00-07:00", " 2026-11-18T18:45:00Z"])
def test_invalid_or_lossy_schedule_rejected_before_transport(tmp_path, timestamp):
    engine, context, vendor = setup(tmp_path)
    change = {**SCHEDULE_CHANGE, "fields": {"scheduled_start": timestamp}}
    assert plan(engine, context, change).status != "completed"
    assert vendor.calls == []


@pytest.mark.parametrize("timestamp,date,time,utc", [
    ("2026-11-18T18:45:00-07:00", "2026-11-18", "18:45", "2026-11-19T01:45:00Z"),
    ("2026-11-19T00:15:00+05:30", "2026-11-19", "00:15", "2026-11-18T18:45:00Z"),
    ("2026-11-19T01:45:00Z", "2026-11-19", "01:45", "2026-11-19T01:45:00Z")])
def test_schedule_native_projection_and_equivalent_offset_readback(tmp_path, timestamp, date, time, utc):
    engine, context, vendor = setup(tmp_path)
    approved = approval(plan(engine, context, {**SCHEDULE_CHANGE, "fields": {"scheduled_start": timestamp}}))
    vendor.readback_timestamp = timestamp
    result = engine.execute("commit_write", approved, context=context)
    assert result.status == "completed", result.public_dict()
    body = json.loads(next(body for method, _, body in vendor.calls if method == "PUT"))
    assert (body[P+"date"], body[P+"time"], body[P+"meeting_ts"]) == (date, time, utc)
    assert P+"scheduled_start" not in vendor.row
    assert vendor.row[P+"meeting_ts"] == timestamp
    assert sum(m == "GET" for m, _, _ in vendor.calls) == 3
    assert engine.execute("commit_write", approved, context=context).status == "completed"
    assert sum(m == "PUT" for m, _, _ in vendor.calls) == 1


def test_schedule_ignored_by_provider_remains_uncertain_without_repeat_put(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approved = approval(plan(engine, context, SCHEDULE_CHANGE))
    vendor.fault = "schedule_ignored"
    result = engine.execute("commit_write", approved, context=context)
    assert result.status != "completed"
    vendor.fault = None
    result = engine.execute("commit_write", approved, context=context)
    assert result.status != "completed"
    assert sum(m == "PUT" for m, _, _ in vendor.calls) == 1

def test_production_client_matches_captured_development_serialization():
    root = Path(__file__).parents[1] / "docs/capabilities/evidence"
    prod = root / "gworks-production-title"
    assert (prod / "meeting-editor.js").read_bytes() == (root / "gworks-development-editor/meeting-editor.js").read_bytes()
    editor = (prod / "agenda-editor.extract.html").read_text()
    assert "apiEndPoint:'https://api.gworks.cloud'" in editor
    assert 'name="cms_meeting.location" form-required="true"' in editor
    assert 'form-min-length="4" form-max-length="256"' in editor
    client = (prod / "meeting-editor.js").read_text()
    assert "getData('#gworks-evt-am-form', 'ALL')" in client
    assert "window.$gworks.api.putSecure(apiData)" in client
    assert "formData['cms_meeting.date'] + 'T' + formData['cms_meeting.time'] + ':00'" in client
    assert "moment(formData['cms_meeting.meeting_ts']).utc().format()" in client
    assert 'type="date" name="cms_meeting.date"' in editor
    assert 'max="2050-12-31" min="2000-01-01"' in editor
    assert 'type="time" name="cms_meeting.time"' in editor
    core = (prod / "gworks.core.extract.js").read_text()
    assert "params.data = JSON.stringify(options.data)" in core
    assert "Authorization: 'Bearer '" in core
