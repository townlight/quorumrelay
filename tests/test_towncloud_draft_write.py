"""Pinned client contract, synthetic requests/readback; no provider mutation."""

from copy import deepcopy
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register


ROOT = "https://towncloud.io/go/example"
SOURCE = {"provider": "towncloud", "url": ROOT, "namespace": "//towncloud.io/go/example"}
CHANGE = {"key": "draft", "entity": "item_draft", "operation": "update", "meeting_id": "7",
          "resource_id": "3", "fields": {"content_type": "Meetings::Item", "field_name": "text",
                                          "draft_content": "New draft café & text"}}


class Vendor:
    mock = True

    def __init__(self):
        self.calls, self.ignore, self.timeout, self.fault, self.cancel = [], False, False, None, None
        self.value = {"drafts": [
            {"content_type": "Meetings::Item", "content_id": 3, "field_name": "text", "draft_content": "Before",
             "expired": False, "updated_at": "2026-11-14T01:00:00Z", "extra": [None, False]},
            {"content_type": "Meetings::Item", "content_id": 4, "field_name": "heading", "draft_content": "Keep",
             "expired": False, "updated_at": "2026-11-14T01:00:00Z"}], "unknown": {"preserve": True}}

    def send(self, url, *, method, body, headers, **kwargs):
        self.calls.append((method, url, body))
        assert headers["Cookie"] == "towncloud_session=secret-session"
        if self.fault == "denied":
            return WriteResponse(403)
        if self.fault == "oversize":
            return WriteResponse(200, b"x" * (kwargs["byte_limit"] + 1))
        if method == "POST":
            assert url == ROOT + "/drafts"
            assert headers["X-CSRF-Token"] == "secret-csrf"
            fields = parse_qs(body.decode(), keep_blank_values=True)
            assert fields["draft[agenda_id]"] == ["7"]
            assert fields["draft[content_id]"] == ["3"]
            assert fields["draft[content_type]"] == [self.value["drafts"][0]["content_type"]]
            assert fields["draft[field_name]"] == [self.value["drafts"][0]["field_name"]]
            assert "client_timestamp" in fields
            if not self.ignore:
                self.value["drafts"][0]["draft_content"] = fields["draft[draft_content]"][0]
                self.value["drafts"][0]["updated_at"] = "2026-11-14T02:00:00Z"
            if self.timeout:
                raise TimeoutError()
            return WriteResponse(200, b"saved")
        assert method == "GET" and parse_qs(urlsplit(url).query) == {"agenda_id": ["7"]}
        if self.cancel:
            self.cancel.cancellation.set()
        if self.fault == "malformed":
            return WriteResponse(200, b"not json")
        return WriteResponse(200, json.dumps(self.value).encode())


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(principal="editor", client_id="fixture", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({SOURCE["namespace"]}),
        credentials={"towncloud": {"tenant": "city", "site_url": ROOT,
            "allowed_namespaces": [SOURCE["namespace"]], "permissions": ["item_draft:update"],
            "content_bindings": {"7": {"Meetings::Item": ["3"], "Meetings::SectionHeader": ["3"]}},
            "session_cookie": "towncloud_session=secret-session", "csrf_token": "secret-csrf"}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def plan(engine, context, change=None):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change or CHANGE]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


@pytest.mark.parametrize("timeout", [False, True])
def test_saved_unpublished_draft_exact_identity_unknown_fields_restart_and_no_replay(tmp_path, timeout):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    assert [call[0] for call in vendor.calls] == ["GET"]
    before_other = deepcopy(vendor.value["drafts"][1])
    vendor.timeout = timeout
    first = engine.execute("commit_write", approval, context=context)
    assert first.status == ("partial" if timeout else "completed"), first.public_dict()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["readback"]["drafts"][0]["draft_content"] == CHANGE["fields"]["draft_content"]
    assert item["readback"]["drafts"][1] == before_other
    assert item["readback"]["unknown"] == {"preserve": True}
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1
    receipt = reopened.execute("receipt", {"plan_id": approval["plan_id"]}, context=context)
    assert "secret-" not in json.dumps(receipt.public_dict())


@pytest.mark.parametrize("fault", ["missing", "expired", "ambiguous", "secret", "shape", "malformed", "oversize", "denied"])
def test_invalid_draft_snapshot_never_mutates(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    if fault == "missing":
        vendor.value["drafts"].pop(0)
    elif fault == "expired":
        vendor.value["drafts"][0]["expired"] = True
    elif fault == "ambiguous":
        vendor.value["drafts"].append(deepcopy(vendor.value["drafts"][0]))
    elif fault == "secret":
        vendor.value["echo"] = "secret-session"
    elif fault == "shape":
        vendor.value["drafts"] = None
    else:
        vendor.fault = fault
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert all(m == "GET" for m, _, _ in vendor.calls)
    assert "secret-" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("fault", ["content", "meeting", "permission", "scope", "tenant", "cookie", "field", "create", "files"])
def test_unmapped_or_out_of_policy_change_fails_before_network(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    if fault == "content":
        change["resource_id"] = "4"
    elif fault == "meeting":
        change["meeting_id"] = "8"
    elif fault == "permission":
        context.credentials["towncloud"]["permissions"] = []
    elif fault == "scope":
        context.allowed_namespaces = frozenset({"other"})
    elif fault == "tenant":
        context.tenant = "other"
    elif fault == "cookie":
        context.credentials["towncloud"]["session_cookie"] += "\r\nInjected: yes"
    elif fault == "field":
        change["fields"]["field_name"] = "is_published"
    elif fault == "create":
        change["operation"] = "create"
    elif fault == "files":
        change["files"] = [{"path": "not-allowed"}]
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


@pytest.mark.parametrize("fault", ["changed", "revoked", "ignored", "collateral"])
def test_commit_conflict_revocation_and_unconfirmed_readback(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    if fault == "changed":
        vendor.value["unknown"] = {"concurrent": True}
    elif fault == "revoked":
        context.credentials["towncloud"]["content_bindings"] = {}
    elif fault == "ignored":
        vendor.ignore = True
    elif fault == "collateral":
        original = vendor.send
        def send(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs["method"] == "POST":
                vendor.value["drafts"][1]["draft_content"] = "Unexpected"
            return result
        vendor.send = send
    result = engine.execute("commit_write", approval, context=context)
    assert result.status != "completed", result.public_dict()
    assert sum(m == "POST" for m, _, _ in vendor.calls) == (0 if fault in {"changed", "revoked"} else 1)


def test_cancel_after_planning_get_saves_no_plan(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.cancel = context
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "cancelled", result.public_dict()
    assert not list(engine.storage.list("write_plans", scope=context.scope))


@pytest.mark.parametrize("content_type,field", [
    ("Meetings::Item", "heading"), ("Meetings::Item", "subheading"),
    ("Meetings::Item", "text"), ("Meetings::Item", "minutes"),
    ("Meetings::SectionHeader", "heading"), ("Meetings::SectionHeader", "text"),
])
def test_each_declared_existing_field_and_empty_draft_text(tmp_path, content_type, field):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    change["fields"].update(content_type=content_type, field_name=field, draft_content="")
    vendor.value["drafts"][0].update(content_type=content_type, field_name=field)
    result = engine.execute("commit_write", plan(engine, context, change), context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"]["drafts"][0]["draft_content"] == ""
