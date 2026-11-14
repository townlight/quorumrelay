"""Pinned legacy NewAgendaItem request and nested readback, synthetic execution."""

from copy import deepcopy
import json

import pytest

from quorumrelay import Engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from test_boardable_agenda_write import ROOT, SOURCE, Vendor, setup, plan

CHANGE = {"key": "new-item", "entity": "item", "operation": "create", "meeting_id": "7",
          "parent_id": 0, "fields": {"text": "Budget public discussion"}}


class CreateVendor(Vendor):
    def __init__(self):
        super().__init__()
        self.fault = None
        self.cancel = None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        if method == "GET":
            if self.fault == "readback_failure" and any(m == "POST" for m, _, _ in self.calls):
                raise TimeoutError()
            return super().send(url, method=method, body=body, headers=headers,
                                byte_limit=byte_limit, deadline_seconds=deadline_seconds)
        self.calls.append((method, url, body))
        assert method == "POST" and url == ROOT + "meetings/7/agenda"
        assert headers["Content-Type"] == "application/json" and headers["X-CSRF-TOKEN"] == "secret-csrf"
        assert headers["Cookie"] == "boardable_session=secret-session"
        data = json.loads(body)
        assert set(data) == {"text", "parent_id", "date"} and data["date"] == ""
        row = {"id": 99, "text": data["text"], "parent_agenda_id": data["parent_id"],
               "agenda": [], "unknown_server_default": [None, False]}
        if self.fault == "denied":
            return WriteResponse(403)
        if self.fault != "ignore":
            if data["parent_id"]:
                self.tree[0]["agenda"].append(row)
            else:
                self.tree.append(row)
        if self.fault == "collateral":
            self.tree[0]["unknown"] = ["changed"]
        if self.fault == "extra_child":
            row["agenda"] = [{"id": 100, "parent_agenda_id": 99, "text": "Unrequested"}]
        if self.fault == "wrong_parent":
            row["parent_agenda_id"] = 8
        if self.fault == "timeout":
            raise TimeoutError()
        if self.cancel:
            self.cancel.cancellation.set()
        if self.fault == "bad_reply":
            return WriteResponse(200, b'{"created":true}')
        return WriteResponse(200, json.dumps(row).encode())


def configured(tmp_path):
    engine, context, vendor = setup(tmp_path, CreateVendor())
    context.credentials["boardable"]["permissions"] = ["item:create"]
    return engine, context, vendor


@pytest.mark.parametrize("parent", [0, 1])
def test_exact_create_request_parent_identity_readback_and_restart_no_replay(tmp_path, parent):
    engine, context, vendor = configured(tmp_path)
    change = {**CHANGE, "parent_id": parent}
    approval = plan(engine, context, change)
    assert [m for m, _, _ in vendor.calls] == ["GET"]  # No draft preparation during planning.
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == "99" and item["state"] == "succeeded"
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1
    assert "secret-" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("fault", ["ignore", "collateral", "extra_child", "wrong_parent", "bad_reply", "timeout"])
def test_unconfirmed_creation_is_never_replayed_or_matched_by_title(tmp_path, fault):
    engine, context, vendor = configured(tmp_path)
    approval = plan(engine, context, CHANGE)
    vendor.fault = fault
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "partial" and result.data["items"][0]["state"] == "uncertain", result.public_dict()
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    second = reopened.execute("commit_write", approval, context=context)
    # A confirmed ID plus later correct readback may reconcile; lost IDs stay uncertain.
    if fault in {"timeout", "bad_reply"}:
        assert second.data["items"][0]["state"] == "uncertain"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1


@pytest.mark.parametrize("fault", ["text", "description", "resource_id", "parent", "parent_type", "parent_leaf", "permission", "file"])
def test_invalid_create_scope_cannot_send_mutation(tmp_path, fault):
    engine, context, vendor = configured(tmp_path)
    change = deepcopy(CHANGE)
    if fault == "text":
        change["fields"]["text"] = " "
    elif fault == "description":
        change["fields"]["description"] = "Unmapped"
    elif fault == "resource_id":
        change["resource_id"] = "99"
    elif fault == "parent":
        change["parent_id"] = 999
    elif fault == "parent_type":
        change["parent_id"] = True
    elif fault == "parent_leaf":
        change["parent_id"] = 2
    elif fault == "permission":
        context.credentials["boardable"]["permissions"] = ["item:update"]
    else:
        change["files"] = [{"name": "new.txt"}]
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not any(m == "POST" for m, _, _ in vendor.calls)


def test_changed_tree_after_plan_prevents_creation(tmp_path):
    engine, context, vendor = configured(tmp_path)
    approval = plan(engine, context, CHANGE)
    vendor.tree[0]["text"] = "Changed by another editor"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(m == "POST" for m, _, _ in vendor.calls)


@pytest.mark.parametrize("fault", ["readback_failure", "cancel"])
def test_known_created_id_survives_interrupted_readback_and_reconciles_without_post(tmp_path, fault):
    engine, context, vendor = configured(tmp_path)
    approval = plan(engine, context, CHANGE)
    if fault == "cancel":
        vendor.cancel = context
    else:
        vendor.fault = fault
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    assert result.data["items"][0]["resource_id"] == "99"
    context.cancellation.clear()
    vendor.cancel, vendor.fault = None, None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1


@pytest.mark.parametrize("fault", ["cancel", "revoked"])
def test_existing_reorder_interrupted_after_post_is_uncertain_until_readback(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    original_send = vendor.send

    def send(url, **kwargs):
        response = original_send(url, **kwargs)
        if kwargs["method"] == "POST":
            if fault == "cancel":
                context.cancellation.set()
            else:
                context.credentials["boardable"]["permissions"] = []
        return response

    vendor.send = send
    approval = plan(engine, context)
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    context.cancellation.clear()
    context.credentials["boardable"]["permissions"] = ["agenda_order:update"]
    assert engine.execute("commit_write", approval, context=context).status == "completed"
    assert sum(m == "POST" for m, _, _ in vendor.calls) == 1
