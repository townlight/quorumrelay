"""Synthetic execution of pinned legacy Boardable edit-list/reorder contracts."""

from copy import deepcopy
import json
from urllib.parse import urlsplit

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

ROOT = "https://app.boardable.com/example/"
SOURCE = {"provider": "boardable", "url": ROOT, "namespace": "boardable:fixture"}
CHANGE = {"key": "reorder", "entity": "agenda_order", "operation": "update",
          "resource_id": "7", "meeting_id": "7", "fields": {"agenda_item_ids": [4, 1, 3, 2]}}


class Vendor:
    mock = True

    def __init__(self):
        self.tree = [{"id": 1, "text": "Public business", "parent_agenda_id": 0, "unknown": [False, None],
                      "agenda": [{"id": 2, "parent_agenda_id": 1, "agenda": None, "text": "Budget"},
                                 {"id": 3, "parent_agenda_id": 1, "agenda": [], "text": "Contract"}]},
                     {"id": 4, "parent_agenda_id": 0, "text": "Adjourn"}]
        self.calls = []
        self.timeout = False
        self.ignore = False
        self.denied = False
        self.echo = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert url.startswith(ROOT + "meetings/7/agenda/") and deadline_seconds > 0
        assert headers["Cookie"] == "boardable_session=secret-session"
        self.calls.append((method, url, body))
        if method == "POST":
            assert url.endswith("/agenda/reorder")
            assert headers["X-CSRF-TOKEN"] == "secret-csrf"
            rows = json.loads(body)["agenda"]
            assert rows == [{"id": 4, "parent_agenda_id": 0}, {"id": 1, "parent_agenda_id": 0},
                            {"id": 3, "parent_agenda_id": 1}, {"id": 2, "parent_agenda_id": 1}]
            if self.denied:
                return WriteResponse(403)
            if not self.ignore:
                self.tree.reverse()
                self.tree[1]["agenda"].reverse()
            if self.timeout:
                raise TimeoutError()
            return WriteResponse(200, b"saved")
        assert urlsplit(url).query == "list_type=nested&version=edit"
        value = deepcopy(self.tree)
        if self.echo:
            value[0]["echo"] = self.echo
        return WriteResponse(200, json.dumps(value).encode())


def setup(tmp_path, vendor=None):
    vendor = vendor or Vendor()
    context = OperationContext(principal="editor", client_id="fixture", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({SOURCE["namespace"]}),
        credentials={"boardable": {"tenant": "city", "org_url": ROOT, "legacy_agenda_editor": True,
            "allowed_namespaces": [SOURCE["namespace"]], "session_cookie": "boardable_session=secret-session",
            "csrf_token": "secret-csrf", "permissions": ["agenda_order:update"], "meeting_ids": ["7"],
            "meeting_urls": {"7": ROOT + "meetings/7"}}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def plan(engine, context, change=CHANGE):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


@pytest.mark.parametrize("timeout", [False, True])
def test_exact_nested_sibling_order_unknown_fields_and_restart_no_replay(tmp_path, timeout):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    assert len(vendor.calls) == 1 and vendor.calls[0][0] == "GET"  # No prepare-draft mutation.
    vendor.timeout = timeout
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == ("partial" if timeout else "completed"), result.public_dict()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    tree = result.data["items"][0]["readback"]
    assert [r["id"] for r in tree] == [4, 1]
    assert [r["id"] for r in tree[1]["agenda"]] == [3, 2]
    assert tree[1]["unknown"] == [False, None]
    assert sum(method == "POST" for method, _, _ in vendor.calls) == 1
    receipt = reopened.execute("receipt", {"plan_id": approval["plan_id"]}, context=context)
    assert "secret-" not in json.dumps(receipt.public_dict())


@pytest.mark.parametrize("fault", ["wrong_parent", "duplicate", "not_tree", "missing_id", "omit", "repeat", "move_child", "secret"])
def test_invalid_or_incomplete_trees_and_orders_do_not_mutate(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    if fault == "wrong_parent":
        vendor.tree[0]["agenda"][0]["parent_agenda_id"] = 999
    elif fault == "duplicate":
        vendor.tree[1]["id"] = 1
    elif fault == "not_tree":
        vendor.tree = {"agenda": vendor.tree}
    elif fault == "missing_id":
        vendor.tree[0].pop("id")
    elif fault == "secret":
        vendor.echo = "secret-session"
    else:
        change["fields"]["agenda_item_ids"] = {"omit": [4, 1, 3], "repeat": [4, 1, 3, 3], "move_child": [4, 3, 1, 2]}[fault]
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed" and not any(m == "POST" for m, _, _ in vendor.calls)
    assert "secret-" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("fault", ["tenant", "root", "editor", "permission", "meeting", "namespace", "url", "header"])
def test_current_configuration_binding_prevents_network(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    config = context.credentials["boardable"]
    if fault == "tenant":
        config["tenant"] = "other"
    elif fault == "root":
        config["org_url"] = "https://app.boardable.com/other/"
    elif fault == "editor":
        config["legacy_agenda_editor"] = False
    elif fault == "permission":
        config["permissions"] = []
    elif fault == "meeting":
        config["meeting_ids"] = []
    elif fault == "namespace":
        config["allowed_namespaces"] = []
    elif fault == "url":
        config["meeting_urls"]["7"] = ROOT + "meetings/8"
    else:
        config["session_cookie"] += "\r\nInjected: yes"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "failed" and not vendor.calls


@pytest.mark.parametrize("fault", ["conflict", "ignored", "revoked", "cancel", "denied"])
def test_commit_safety_and_unconfirmed_mutation_are_not_replayed(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    if fault == "conflict":
        vendor.tree[0]["text"] = "Changed"
    elif fault == "ignored":
        vendor.ignore = True
    elif fault == "revoked":
        context.credentials["boardable"]["meeting_ids"] = []
    elif fault == "cancel":
        context.cancellation.set()
    else:
        vendor.denied = True
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == {"conflict": "failed", "ignored": "partial", "revoked": "failed",
                             "cancel": "cancelled", "denied": "failed"}[fault], result.public_dict()
    if fault in {"ignored", "denied"}:
        engine.execute("commit_write", approval, context=context)
        assert sum(m == "POST" for m, _, _ in vendor.calls) == 1
    else:
        assert not any(m == "POST" for m, _, _ in vendor.calls)


def test_cancellation_during_plan_read_does_not_persist_plan(tmp_path):
    engine, context, vendor = setup(tmp_path)
    original = vendor.send

    def cancelled(*args, **kwargs):
        result = original(*args, **kwargs)
        context.cancellation.set()
        return result
    vendor.send = cancelled
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "cancelled", result.public_dict()
    assert not list(engine.storage.list("write_plans", scope=context.scope))


class ItemVendor(Vendor):
    def __init__(self):
        super().__init__()
        self.item = {"id": 2, "text": "Budget", "description": "Old description", "is_private": 0,
                     "duration": 15, "people_responsible": [{"id": 55, "unknown": "retained"}],
                     "uploads": [{"id": 88, "name": "Budget.pdf", "unknown": [None]}], "unknown": {"keep": True}}

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        if method == "GET" and url == ROOT + "agenda/2":
            self.calls.append((method, url, body))
            return WriteResponse(200, json.dumps({"agenda_item": self.item, "unknown_envelope": 0}).encode())
        if method == "POST":
            from email.parser import BytesParser
            from email.policy import default
            self.calls.append((method, url, body))
            assert url == ROOT + "meetings/7/agenda/update"
            assert headers["X-CSRF-TOKEN"] == "secret-csrf"
            message = BytesParser(policy=default).parsebytes(
                ("Content-Type: " + headers["Content-Type"] + "\r\n\r\n").encode() + body)
            fields = [(part.get_param("name", header="Content-Disposition"), part.get_payload(decode=True).decode())
                      for part in message.iter_parts()]
            assert fields == [("id", "2"), ("text", "Budget revised"), ("description", "Revised ✓\r\nSecond line"),
                              ("is_private", "0"), ("original_token", "null"), ("duration", "15"),
                              ("people_responsible[]", "55"), ("attachments[0][type]", "attachment"),
                              ("attachments[0][attachment_id]", "88")]
            if self.denied:
                return WriteResponse(403)
            if not self.ignore:
                values = dict(fields)
                self.item.update({key: values[key] for key in ("text", "description")})
                self.tree[0]["agenda"][0]["text"] = values["text"]
            if self.timeout:
                raise TimeoutError()
            return WriteResponse(200, json.dumps({"data": self.item, "uploads": self.item["uploads"]}).encode())
        return super().send(url, method=method, body=body, headers=headers, byte_limit=byte_limit,
                            deadline_seconds=deadline_seconds)


def item_setup(tmp_path):
    vendor = ItemVendor()
    engine, context, _ = setup(tmp_path, vendor)
    context.credentials["boardable"]["permissions"] = ["item:update"]
    context.credentials["boardable"]["onedrive_access_token"] = None
    change = {"key": "edit", "entity": "item", "operation": "update", "resource_id": "2", "meeting_id": "7",
              "fields": {"text": "Budget revised", "description": "Revised ✓\r\nSecond line"}}
    return engine, context, vendor, change


@pytest.mark.parametrize("fault", [None, "timeout", "ignored", "denied", "conflict", "revoked"])
def test_item_text_edit_preserves_fields_attachments_and_reconciles_without_replay(tmp_path, fault):
    engine, context, vendor, change = item_setup(tmp_path)
    approval = plan(engine, context, change)
    assert [m for m, _, _ in vendor.calls] == ["GET", "GET"]
    if fault == "conflict":
        vendor.item["uploads"].append({"id": 89})
    elif fault == "revoked":
        context.credentials["boardable"]["permissions"] = []
    elif fault:
        setattr(vendor, {"timeout": "timeout", "ignored": "ignore", "denied": "denied"}[fault], True)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == {None: "completed", "timeout": "partial", "ignored": "partial",
                             "denied": "failed", "conflict": "failed", "revoked": "failed"}[fault], result.public_dict()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=context)
    assert sum(m == "POST" for m, _, _ in vendor.calls) == (0 if fault in {"conflict", "revoked"} else 1)
    if fault in {None, "timeout"}:
        assert result.status == "completed", result.public_dict()
        item = result.data["items"][0]["readback"]["detail"]["agenda_item"]
        assert item["uploads"] == [{"id": 88, "name": "Budget.pdf", "unknown": [None]}]
        assert item["people_responsible"] == [{"id": 55, "unknown": "retained"}]
        assert item["unknown"] == {"keep": True}


@pytest.mark.parametrize("fault", ["unknown_field", "missing_snapshot", "wrong_item", "duplicate_attachment", "cloud_token", "empty_text"])
def test_incomplete_or_unmapped_item_edit_fails_without_mutation(tmp_path, fault):
    engine, context, vendor, change = item_setup(tmp_path)
    if fault == "unknown_field":
        change["fields"]["duration"] = 99
    elif fault == "empty_text":
        change["fields"]["text"] = " "
    elif fault == "missing_snapshot":
        vendor.item.pop("uploads")
    elif fault == "wrong_item":
        vendor.item["id"] = 9
    elif fault == "duplicate_attachment":
        vendor.item["uploads"].append({"id": 88})
    else:
        context.credentials["boardable"]["onedrive_access_token"] = "cloud-secret"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not any(m == "POST" for m, _, _ in vendor.calls)
