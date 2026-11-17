"""Synthetic native saves, exact approval, preservation and durable no-replay."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers import gworks_write as adapter

P = "cms_meeting."
ROOT = "https://api.dev.gworks.cloud/cms/secure/city/meeting/"
NS = "//api.dev.gworks.cloud/city/1311/cms"
SOURCE = {"provider": "gworks", "url": ROOT, "namespace": NS, "options": {"gworks_city_id": "1311"}}
SECTIONS = [{"title": "Public business", "items": [{"value": "Bridge repair", "minute": ""}]}]
CREATE = {"key": "new", "entity": "meeting", "operation": "create", "fields": {
    "title": "Council hearing", "location": "City chambers", "scheduled_start": "2026-11-17T18:30:00-07:00",
    "category_ref_type_id": "2", "sections": SECTIONS, "publication": "draft"}}
UPDATE = {"key": "edit", "entity": "meeting", "operation": "update", "resource_id": "7",
          "fields": {"title": "Changed hearing", "sections": [
              {"title": "Public business", "items": [{"value": "Bridge repaired", "minute": "Motion approved"}]}]}}
ROW = {P+"id": 7, P+"title": "Council hearing", P+"location": "City chambers",
       P+"meeting_ts": "2026-11-17T18:30:00-07:00", P+"category_ref_type_id": 2,
       P+"template_fl": False, P+"archived_fl": False, P+"agenda_published_fl": False,
       P+"minutes_published_fl": False, P+"agenda_published_dt": None, P+"minutes_published_dt": None,
       P+"data": [{"type": "section", "title": "Public business", "future": [False, None],
                    "items": [{"type": "agenda-item", "value": "Bridge repair", "minute": "",
                               "files": [{"filename": "private.pdf", "usetype": "official"}],
                               "extra": {"preserve": True}}]}],
       P+"files": [{"name": "packet.pdf", "id": "45", "type": "application/pdf", "size": "42"}],
       P+"mod_ts": "revision-1", "unrecognized": {"keep": "café"}}


class Vendor:
    mock = True

    def __init__(self):
        self.rows, self.calls, self.fault, self.after = {"7": deepcopy(ROW)}, [], None, lambda: None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert url.startswith(ROOT) and deadline_seconds > 0
        assert headers["Authorization"] == "Bearer synthetic-secret"
        self.calls.append((method, url, body))
        identity = url[len(ROOT):]
        if self.fault == "denied":
            return WriteResponse(403)
        if method == "GET":
            if self.fault == "readback_failure" and any(m in {"POST", "PUT"} for m, _, _ in self.calls):
                raise TimeoutError()
            return WriteResponse(200, json.dumps(self.rows[identity]).encode())
        assert headers["Content-Type"] == "application/json"
        request = json.loads(body)
        assert isinstance(request[P+"data"], str) and isinstance(request[P+"files"], str)
        assert P+"id" not in request and P+"mod_ts" not in request and "unrecognized" not in request
        assert request[P+"section_count"] == len(json.loads(request[P+"data"]))
        if method == "POST":
            assert url == ROOT
            identity = "99"
            row = {P+"id": 99, P+"template_fl": False, P+"data": [], P+"files": []}
        else:
            assert method == "PUT" and identity == "7"
            row = deepcopy(self.rows[identity])
        if self.fault != "ignore":
            for key, value in request.items():
                if key in {P+"date", P+"time", P+"section_count"}:
                    continue
                row[key] = (json.loads(value) if key in {P+"data", P+"files"} else
                            value == "true" if key == P+"template_fl" else value)
        row[P+"mod_ts"] = "revision-2"
        if self.fault == "collateral":
            row["unrecognized"] = "changed"
        if self.fault == "attachments":
            row[P+"files"] = []
        if self.fault == "wrong_publication":
            row[P+"minutes_published_fl"] = True
        self.rows[identity] = row
        self.after()
        if self.fault == "timeout":
            raise TimeoutError()
        if self.fault == "bad_reply":
            return WriteResponse(200, b'{"saved":true}')
        return WriteResponse(200, json.dumps({P+"id": int(identity), P+"mod_ts": "revision-2"}).encode())


def setup(tmp_path):
    vendor = Vendor()
    caller = OperationContext(principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({NS}),
        credentials={"gworks": {"tenant": "city", "city_id": "1311", "origin": adapter.gworks_editor.ORIGIN,
            "allowed_namespaces": [NS], "token": "synthetic-secret", "meeting_ids": ["7"],
            "permissions": ["meeting:create", "meeting:update", "meeting:publish_agenda", "meeting:publish_minutes"]}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, caller, vendor


def plan(engine, caller, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=caller)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


@pytest.mark.parametrize("publication", ["draft", "agenda"])
def test_create_exact_request_returned_id_approval_and_reopen_no_post_replay(tmp_path, publication):
    engine, caller, vendor = setup(tmp_path)
    change = deepcopy(CREATE)
    change["fields"]["publication"] = publication
    if publication == "agenda":
        change["fields"]["published_on"] = "2026-11-16"
    approval = plan(engine, caller, change)
    assert vendor.calls == []
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["resource_id"] == "99"
    body = json.loads(vendor.calls[0][2])
    assert body == {P+"title": "Council hearing", P+"location": "City chambers",
        P+"category_ref_type_id": "2", P+"date": "2026-11-17", P+"time": "18:30",
        P+"meeting_ts": "2026-11-18T01:30:00Z",
        P+"data": '[{"type":"section","title":"Public business","items":[{"type":"agenda-item","value":"Bridge repair","minute":"","files":[]}]}]',
        P+"files": "[]", P+"section_count": 1, P+"archived_fl": False,
        P+"agenda_published_fl": publication == "agenda", P+"minutes_published_fl": False,
        P+"agenda_published_dt": "2026-11-16" if publication == "agenda" else None,
        P+"minutes_published_dt": None}
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=caller).status == "completed"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1
    assert "synthetic-secret" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("publication", ["preserve", "agenda", "minutes"])
def test_update_preserves_files_unknown_fields_and_explicit_publication(tmp_path, publication):
    engine, caller, vendor = setup(tmp_path)
    change = deepcopy(UPDATE)
    if publication == "minutes":
        vendor.rows["7"][P+"agenda_published_fl"] = True
        vendor.rows["7"][P+"agenda_published_dt"] = "2026-11-15"
    change["fields"]["publication"] = publication
    if publication != "preserve":
        change["fields"]["published_on"] = "2026-11-16"
    before = deepcopy(vendor.rows["7"])
    approval = plan(engine, caller, change)
    assert [m for m, _, _ in vendor.calls] == ["GET"]
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    after = result.data["items"][0]["readback"]
    assert after[P+"files"] == before[P+"files"]
    assert after[P+"data"][0]["items"][0]["files"] == before[P+"data"][0]["items"][0]["files"]
    assert after[P+"data"][0]["future"] == [False, None]
    assert after["unrecognized"] == before["unrecognized"]
    assert after[P+"title"] == "Changed hearing"
    assert after[P+"data"][0]["items"][0]["minute"] == "Motion approved"
    body = json.loads(next(b for m, _, b in vendor.calls if m == "PUT"))
    assert P+"agenda_published_fl" not in body if publication != "agenda" else body[P+"agenda_published_fl"]
    assert P+"minutes_published_fl" not in body if publication != "minutes" else body[P+"minutes_published_fl"]


def test_append_sections_and_items_preserves_existing_metadata(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    change = deepcopy(UPDATE)
    change["fields"]["sections"][0]["items"].append({"value": "New business", "minute": ""})
    change["fields"]["sections"].append({"title": "Adjourn", "items": []})
    result = engine.execute("commit_write", plan(engine, caller, change), context=caller)
    assert result.status == "completed"
    data = vendor.rows["7"][P+"data"]
    assert len(data) == 2 and len(data[0]["items"]) == 2
    assert data[0]["items"][0]["extra"] == {"preserve": True}


@pytest.mark.parametrize("fault", ["timeout", "bad_reply", "readback_failure", "wrong_publication"])
def test_uncertain_create_never_replays_after_restart(tmp_path, fault):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, CREATE)
    vendor.fault = fault
    result = engine.execute("commit_write", approval, context=caller)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=caller)
    if fault in {"timeout", "bad_reply"}:
        assert again.data["items"][0]["state"] == "uncertain"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1


@pytest.mark.parametrize("fault", ["ignore", "collateral", "attachments", "timeout"])
def test_update_checks_preservation_and_reconciles_without_put_replay(tmp_path, fault):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, UPDATE)
    vendor.fault = fault
    result = engine.execute("commit_write", approval, context=caller)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    vendor.fault = None
    result = engine.execute("commit_write", approval, context=caller)
    assert result.data["items"][0]["state"] == ("succeeded" if fault == "timeout" else "uncertain")
    assert sum(m == "PUT" for m, _, _ in vendor.calls) == 1


@pytest.mark.parametrize("operation", ["create", "update"])
def test_cancel_after_send_keeps_id_then_reconciles(tmp_path, operation):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, CREATE if operation == "create" else UPDATE)
    vendor.after = caller.cancellation.set
    result = engine.execute("commit_write", approval, context=caller)
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == ("99" if operation == "create" else "7")
    caller.cancellation.clear()
    vendor.after = lambda: None
    assert engine.execute("commit_write", approval, context=caller).status == "completed"
    assert sum(m in {"POST", "PUT"} for m, _, _ in vendor.calls) == 1


@pytest.mark.parametrize("field,value", [
    ("origin", "https://api.gworks.cloud"), ("tenant", "other"), ("city_id", "99"),
    ("allowed_namespaces", NS), ("allowed_namespaces", []), ("token", "bad\nsecret"),
    ("permissions", []), ("meeting_ids", []),
])
def test_binding_failures_prevent_network(tmp_path, field, value):
    engine, caller, vendor = setup(tmp_path)
    caller.credentials["gworks"][field] = value
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=caller)
    assert result.status == "failed" and not vendor.calls


@pytest.mark.parametrize("fields", [
    {"sections": []}, {"sections": [{"title": "x", "items": []}]},
    {"title": " x "}, {"scheduled_start": "2026-11-17T18:30:00"}, {"arbitrary": "bad"},
    {"publication": "minutes", "published_on": "2026-11-16"}, {"publication": "archive"},
    {"publication": "agenda"}, {"published_on": "2026-11-16"},
])
def test_invalid_edits_never_mutate(tmp_path, fields):
    engine, caller, vendor = setup(tmp_path)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [{**UPDATE, "fields": fields}]}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert all(m == "GET" for m, _, _ in vendor.calls)


@pytest.mark.parametrize("fault", ["conflict", "revoke", "approval", "hash", "cancel"])
def test_commit_preconditions_prevent_mutation(tmp_path, fault):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, UPDATE)
    if fault == "conflict":
        vendor.rows["7"]["unrecognized"] = "other editor"
    elif fault == "revoke":
        caller.credentials["gworks"]["permissions"] = []
    elif fault == "approval":
        engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
        register(engine, default_adapters(vendor), approval=lambda *args: False)
    elif fault == "hash":
        approval["plan_hash"] = "bad"
    else:
        caller.cancellation.set()
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status != "completed"
    assert all(m == "GET" for m, _, _ in vendor.calls)


def test_pinned_form_getdata_does_not_emit_unknown_server_fields():
    root = Path(__file__).parents[1] / "docs/capabilities/evidence/gworks-development-editor"
    core = (root / "gworks.core.js").read_text(encoding="utf-8")
    client = (root / "meeting-editor.js").read_text(encoding="utf-8")
    assert "find('input, textarea, select')" in core
    assert "formData['cms_meeting.data'] = JSON.stringify" in client
    assert "window.$gworks.api.putSecure(apiData)" in client
    assert "window.$gworks.api.postSecure(apiData)" in client

@pytest.mark.parametrize("fault", ["oversize", "malformed", "wrong_id", "secret", "deadline", "revoked_after_send"])
def test_native_response_and_post_send_boundaries(tmp_path, fault, monkeypatch):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, CREATE)
    original_send = vendor.send

    def send(url, **kwargs):
        response = original_send(url, **kwargs)
        if kwargs["method"] == "POST":
            if fault == "oversize":
                return WriteResponse(200, b"x" * (kwargs["byte_limit"] + 1))
            if fault == "malformed":
                return WriteResponse(200, b"not json")
            if fault == "secret":
                return WriteResponse(200, json.dumps({P+"id": 99, "echo": "synthetic-secret"}).encode())
            if fault == "deadline":
                monkeypatch.setattr(adapter, "monotonic", lambda: 10**15)
            if fault == "revoked_after_send":
                caller.credentials["gworks"]["permissions"] = []
        if kwargs["method"] == "GET" and fault == "wrong_id":
            value = json.loads(response.content)
            value[P+"id"] = 8
            return WriteResponse(200, json.dumps(value).encode())
        return response

    vendor.send = send
    result = engine.execute("commit_write", approval, context=caller)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    assert "synthetic-secret" not in json.dumps(result.public_dict())
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1


