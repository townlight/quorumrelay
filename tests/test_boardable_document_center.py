"""Captured Document Center contracts, synthetic Engine/SQLite acceptance."""

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

ROOT = Path(__file__).parents[1] / "docs/capabilities/evidence/boardable-document-center"
ORG = "https://app.boardable.com/quorumrelay-evaluation/"
URL = ORG + "documents/4456b3ae"
SOURCE = {"provider": "boardable", "url": ORG, "namespace": "boardable:46098"}
DATA = (ROOT / "quorumrelay-document-center-evaluation.txt").read_bytes()
FILENAME = "quorumrelay-document-center-evaluation.txt"
TITLE = "QuorumRelay Document Center Contract Verified"


class Vendor:
    mock = True

    def __init__(self):
        self.doc = json.loads((ROOT / "boardable-document-center-data.json").read_text(encoding="utf-8"))[
            "response"
        ]["body"]
        self.data = DATA
        self.calls = []
        self.posts = 0
        self.faults = set()
        self.context = None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        self.calls.append((method, url, headers, body))
        assert headers["Cookie"] == "boardable_session=secret-session"
        assert headers["X-XSRF-TOKEN"] == "secret-xsrf"
        assert url.startswith(ORG + "documents")
        if method == "POST":
            self.posts += 1
            if url == ORG + "documents":
                message = BytesParser(policy=default).parsebytes(
                    ("Content-Type: " + headers["Content-Type"] + "\r\n\r\n").encode() + body
                )
                fields = {}
                files = []
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    if part.get_filename():
                        files.append(
                            (
                                name,
                                part.get_filename(),
                                part.get_content_type(),
                                part.get_payload(decode=True),
                            )
                        )
                    else:
                        fields[name] = part.get_payload(decode=True).decode()
                assert fields == {"title": TITLE, "body": "", "disable_downloads": "false", "folder": "0"}
                assert files == [("file", FILENAME, "text/plain", DATA)]
                response = json.loads(
                    (ROOT / "boardable-document-center-create.json").read_text(encoding="utf-8")
                )["response"]["body"]
                self.doc["title"] = response["title"] = fields["title"]
                self.data = files[0][3]
                status = 201
            else:
                assert url == ORG + "documents/1270573"
                assert headers["Content-Type"] == "application/json"
                fields = json.loads(body)
                assert fields == {"title": TITLE}
                self.doc["title"] = fields["title"]
                response = deepcopy(self.doc)
                status = 200
            if "collateral" in self.faults:
                self.doc["body"] = "unrequested change"
            if "timeout" in self.faults:
                raise TimeoutError()
            if "cancel" in self.faults:
                self.context.cancellation.set()
            if "bad_response_id" in self.faults:
                response["id"] = "not-native"
            if "post_denied" in self.faults:
                status = 403
            return WriteResponse(status, json.dumps(response).encode())
        if url == URL + "/data":
            if "read_denied" in self.faults:
                return WriteResponse(403, json.dumps(self.doc).encode())
            doc = deepcopy(self.doc)
            if "foreign_org" in self.faults:
                doc["organization_id"] = 999
            if "evil_download" in self.faults:
                doc["downloadUrl"] = "https://evil.example/file"
            if "reflected_secret" in self.faults:
                doc["body"] = "secret-session"
            if "revoke" in self.faults:
                self.context.credentials["boardable"]["permissions"] = []
            return WriteResponse(200, json.dumps(doc).encode())
        if url == self.doc["downloadUrl"]:
            if "redirect_download" in self.faults:
                return WriteResponse(302, b"", headers={"Location": "https://evil.example/file"})
            return WriteResponse(200, b"changed" if "corrupt" in self.faults else self.data)
        raise AssertionError(url)


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(
        principal="editor",
        client_id="fixture",
        tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({SOURCE["namespace"]}),
        credentials={
            "boardable": {
                "tenant": "city",
                "current_document_center": True,
                "org_url": ORG,
                "organization_id": 46098,
                "owner_id": 403839,
                "allowed_namespaces": [SOURCE["namespace"]],
                "session_cookie": "boardable_session=secret-session",
                "xsrf_token": "secret-xsrf",
                "permissions": ["document:upload", "document:update"],
                "document_ids": ["1270573"],
                "document_urls": {"1270573": URL},
            }
        },
    )
    vendor.context = context
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def change(operation="update"):
    value = {"key": "document", "entity": "document", "operation": operation, "fields": {"title": TITLE}}
    if operation == "update":
        value["resource_id"] = "1270573"
    else:
        value["files"] = [
            {
                "part": "file",
                "filename": FILENAME,
                "content_type": "text/plain",
                "content_base64": base64.b64encode(DATA).decode(),
            }
        ]
    return value


def plan(engine, context, operation="update", **overrides):
    item = change(operation)
    item.update(overrides)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [item]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {k: result.data[k] for k in ["plan_id", "plan_hash"]}


@pytest.mark.parametrize("operation", ["upload", "update"])
def test_native_capture_roundtrip_original_bytes_and_durable_replay(tmp_path, operation):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, operation)
    assert vendor.posts == 0
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["resource_id"] == "1270573"
    assert vendor.doc["title"] == TITLE and vendor.data == DATA
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", prepared, context=context).status == "completed"
    assert vendor.posts == 1
    raw = (tmp_path / "write.sqlite").read_bytes()
    assert b"secret-session" not in raw and b"secret-xsrf" not in raw


def test_title_noop_has_no_send(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.doc["title"] = TITLE
    prepared = plan(engine, context)
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "completed" and result.data["items"][0]["no_send"] is True
    assert vendor.posts == 0


@pytest.mark.parametrize("field,value", [("body", "changed"), ("folder_id", 3), ("owner_id", 999)])
def test_changed_document_never_sends(tmp_path, field, value):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.doc[field] = value
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "failed" and vendor.posts == 0


@pytest.mark.parametrize(
    "fault",
    ["read_denied", "foreign_org", "evil_download", "reflected_secret", "redirect_download", "corrupt"],
)
def test_invalid_read_or_original_is_rejected_before_send(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change()]}, context=context)
    assert result.status == "failed" and vendor.posts == 0
    assert all("evil.example" not in call[1] for call in vendor.calls)


@pytest.mark.parametrize("operation", ["upload", "update"])
def test_cancel_after_send_retains_id_and_recovers_with_gets_only(tmp_path, operation):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, operation)
    vendor.faults.add("cancel")
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "partial", result.public_dict()
    assert result.data["items"][0]["resource_id"] == "1270573"
    context.cancellation.clear()
    count = len(vendor.calls)
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.posts == 1 and all(call[0] == "GET" for call in vendor.calls[count:])


@pytest.mark.parametrize("operation", ["upload", "update"])
def test_timeout_never_replays_upload_or_update(tmp_path, operation):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, operation)
    vendor.faults.add("timeout")
    first = engine.execute("commit_write", prepared, context=context)
    assert first.status == "partial"
    second = engine.execute("commit_write", prepared, context=context)
    assert second.status == ("partial" if operation == "upload" else "completed"), second.public_dict()
    assert vendor.posts == 1


def test_update_collateral_is_uncertain(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("collateral")
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "partial" and vendor.posts == 1


@pytest.mark.parametrize(
    "flag", ["current_agenda_builder", "current_meeting_form", "current_meeting_documents"]
)
def test_modes_cannot_be_combined(tmp_path, flag):
    engine, context, vendor = setup(tmp_path)
    context.credentials["boardable"][flag] = True
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change()]}, context=context)
    assert result.status == "failed" and not vendor.calls


def test_revocation_during_read_prevents_save(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("revoke")
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "failed" and vendor.posts == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"meeting_id": "1"},
        {"parent_id": 2},
        {"resource_id": "999"},
        {"fields": {"title": TITLE, "body": "not mapped"}},
        {"fields": {"title": "secret-xsrf"}},
    ],
)
def test_unmapped_or_unauthorized_changes_fail_closed(tmp_path, overrides):
    engine, context, vendor = setup(tmp_path)
    item = change()
    item.update(overrides)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [item]}, context=context)
    assert result.status == "failed" and not vendor.calls


@pytest.mark.parametrize("operation", ["upload", "update"])
def test_denied_post_remains_uncertain_and_is_not_replayed(tmp_path, operation):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, operation)
    vendor.faults.add("post_denied")
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "partial" and vendor.posts == 1
    engine.execute("commit_write", prepared, context=context)
    assert vendor.posts == 1


def test_page_budget_stops_before_original_download(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [change()], "bounds": {"max_pages": 1}}, context=context
    )
    assert result.status == "failed" and len(vendor.calls) == 1 and vendor.posts == 0


def test_revoked_application_grant_during_read_never_posts(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def revoke(url, **kwargs):
        result = send(url, **kwargs)
        context.authorization = frozenset({"write:plan"})
        return result

    vendor.send = revoke
    result = engine.execute("commit_write", prepared, context=context)
    assert result.status == "failed" and vendor.posts == 0


def test_duplicate_native_response_key_is_rejected(tmp_path):
    engine, context, vendor = setup(tmp_path)
    send = vendor.send

    def duplicate(url, **kwargs):
        response = send(url, **kwargs)
        return WriteResponse(200, b'{"id":1,"id":2}') if url == URL + "/data" else response

    vendor.send = duplicate
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change()]}, context=context)
    assert result.status == "failed" and vendor.posts == 0
