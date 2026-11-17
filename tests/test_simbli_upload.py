"""Pinned native upload fields through Engine/SQLite, including interrupted saves."""

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from test_simbli_item_write import Vendor, SOURCE, NAMESPACE, URL, SAVE, _node, approval, safe, bounds as base_bounds

def bounds(max_pages=20):
    return {**base_bounds(max_pages), "deadline_seconds": 20}


UPLOAD = "/services/api/FileUpload/UploadFile"
DATA = b"%PDF-1.5\nIndependent original test document.\n"


class UploadVendor(Vendor):
    def __init__(self):
        super().__init__()
        self.upload_count = 0
        self.download_count = 0
        self.uploaded = None
        self.original = DATA
        self.details["ItemContents"][1]["Attachments"][0].update(Order=1, Id=1)

    def page(self, logged="True"):
        return super().page(logged).replace("</script>", "var encrModuleID = 'module-control-secret';</script>")

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        if method == "POST" and parsed.path == UPLOAD:
            self.calls.append((method, url, headers, body))
            self.upload_count += 1
            assert headers["Cookie"] == "simbli_session=secret-cookie"
            assert headers["Authorization"] == "Bearer secret-jwt-token"
            assert parse_qs(parsed.query) == {
                "sct": ["secret-token"], "enportaluid": ["enc-user-secret"],
                "endid": ["enc-did-secret"], "enentitytypeid": ["module-control-secret"],
                "enentityid": ["enc-meeting-secret"], "enitemid": [self.selected_id()],
                "attachmentId": ["0"], "id": ["0"],
            }
            message = BytesParser(policy=default).parsebytes(
                ("Content-Type: " + headers["Content-Type"] + "\r\n\r\n").encode() + body)
            parts = list(message.iter_parts())
            assert len(parts) == 1 and parts[0].get_param("name", header="content-disposition") == "file"
            assert parts[0].get_filename() == "new.pdf"
            assert parts[0].get_content_type() == "application/pdf"
            assert parts[0].get_payload(decode=True) == self.original
            self.uploaded = {
                "TempFileName": "native-temp-file.pdf", "FileName": "new.pdf", "AttachmentID": 0,
                "SaveFileName": "native-storage-file.pdf", "OrigFileName": "new.pdf", "IsDeleted": False,
                "Operation": 1, "ContentType": "application/pdf", "FileExtension": "pdf",
                "Title": "new", "OrigTitle": "new", "FileSize": len(self.original),
            }
            if "upload_timeout" in self.faults:
                raise TimeoutError()
            if "cancel_upload" in self.faults:
                self.context.cancellation.set()
            if "revoke_upload" in self.faults:
                self.context.credentials["simbli"]["permissions"] = ["agenda_item:update"]
            value = deepcopy(self.uploaded)
            if "bad_filename" in self.faults:
                value["OrigFileName"] = "wrong.pdf"
            if "bad_size" in self.faults:
                value["FileSize"] += 1
            if "secret_upload" in self.faults:
                value["TempFileName"] = "native-secret-token"
            if "assigned_upload_id" in self.faults:
                value["AttachmentID"] = 444444
            return WriteResponse(200, json.dumps({"Data": {"isSuccess": True, "FileDetail": value}}).encode())
        if method == "POST" and parsed.path == SAVE:
            answer = super().send(url, method=method, body=body, headers=headers,
                                  byte_limit=byte_limit, deadline_seconds=deadline_seconds)
            self.details["ItemContents"] = deepcopy(json.loads(body)["itemContentDTO"])
            field = self.details["ItemContents"][1]
            field["HasData"] = True
            field["Attachments"][0].update(AttachmentID=987654, SchoolID="42", EnitityID=123,
                                            TempFileName="", Operation=4)
            _node(self.tree, 176766)["HasAttachment"] = True
            if "upload_save_timeout" in self.faults:
                raise TimeoutError()
            if "extra_attachment" in self.faults:
                extra = deepcopy(field["Attachments"][0])
                extra.update(AttachmentID=987655, Order=3)
                field["Attachments"].append(extra)
            if "old_attachment_changed" in self.faults:
                field["Attachments"][1]["Title"] = "changed"
            if "foreign_attachment" in self.faults:
                field["Attachments"][0]["SchoolID"] = "99"
            if "changed_field_visibility" in self.faults:
                field["FieldVisibility"] = 2
            if "deleted_new" in self.faults:
                field["Attachments"][0]["IsDeleted"] = True
            if "wrong_new_order" in self.faults:
                field["Attachments"][0]["Order"] = 99
            if "revoke_after_save" in self.faults:
                self.context.allowed_namespaces = frozenset()
            return answer
        if method == "GET" and parsed.path == "/Meetings/Attachment.aspx":
            self.calls.append((method, url, headers, body))
            self.download_count += 1
            assert parse_qs(parsed.query) == {"S": ["42"], "AID": ["987654"], "MID": ["123"]}
            if "download_redirect" in self.faults:
                return WriteResponse(302, b"")
            if "download_html" in self.faults:
                return WriteResponse(200, b"<html>security challenge</html>", {"Content-Type": "text/html"})
            if "corrupt_original" in self.faults:
                return WriteResponse(200, self.original + b"changed", {"Content-Type": "application/pdf"})
            return WriteResponse(200, self.original, {"Content-Type": "application/pdf"})
        return super().send(url, method=method, body=body, headers=headers,
                            byte_limit=byte_limit, deadline_seconds=deadline_seconds)


def setup(tmp_path):
    vendor = UploadVendor()
    context = OperationContext(principal="editor", client_id="fixture", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({NAMESPACE}),
        credentials={"simbli": {"tenant": "city", "site_url": URL, "site_id": "42", "meeting_id": "123",
            "allowed_namespaces": [NAMESPACE], "item_ids": ["176766"], "supporting_fields": ["fileAttachment"],
            "permissions": ["agenda_item:update", "agenda_item_attachment:upload"],
            "encrypted_user_id": "enc-user-secret", "lock_user_id": "lock-user",
            "session_cookie": "simbli_session=secret-cookie", "token": "secret-jwt-token"}})
    vendor.context = context
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def change(data=DATA):
    return {"key": "supporting", "entity": "agenda_item_attachment", "operation": "upload",
            "parent_id": "176766", "meeting_id": "123", "fields": {"field_name": "fileAttachment"},
            "files": [{"part": "file", "filename": "new.pdf", "content_type": "application/pdf",
                       "content_base64": base64.b64encode(data).decode()}]}


def plan(engine, context, value=None, limits=None):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [value or change()],
                            "bounds": limits or bounds()}, context=context)
    assert result.status == "completed", result.public_dict()
    return result


def test_upload_native_wire_original_hash_and_preservation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    before = deepcopy(vendor.details)
    prepared = plan(engine, context)
    assert not vendor.upload_count and not vendor.lock_count
    assert "module-control-secret" not in safe(prepared.data)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == "987654" and item["original_bytes_verified"] is True
    assert vendor.upload_count == vendor.save_count == vendor.release_count == vendor.download_count == 1
    assert vendor.save_bodies[0]["itemDetailsDTO"] == before["ItemDetails"]
    old = deepcopy(before["ItemContents"][1]["Attachments"][0])
    old["Order"] = 2
    assert vendor.details["ItemContents"][1]["Attachments"][1] == old
    assert vendor.details["ItemContents"][0]["UnknownField"] == before["ItemContents"][0]["UnknownField"]
    assert "module-control-secret" not in safe(result.data)


@pytest.mark.parametrize("fault", ["bad_filename", "bad_size", "secret_upload", "upload_timeout", "cancel_upload", "revoke_upload"])
def test_upload_failure_never_saves_or_replays(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add(fault)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial", result.public_dict()
    assert vendor.upload_count == vendor.release_count == 1 and vendor.save_count == 0
    if fault == "revoke_upload":
        context.credentials["simbli"]["permissions"].append("agenda_item_attachment:upload")
    context.cancellation.clear()
    again = engine.execute("commit_write", approval(prepared), context=context)
    assert again.status == "partial" and vendor.upload_count == 1 and vendor.save_count == 0


@pytest.mark.parametrize("fault", ["extra_attachment", "old_attachment_changed", "foreign_attachment",
                                  "changed_field_visibility", "collateral", "download_redirect", "download_html", "corrupt_original",
                                  "deleted_new", "wrong_new_order", "assigned_upload_id", "revoke_after_save"])
def test_save_or_original_mismatch_remains_uncertain(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add(fault)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial", result.public_dict()
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.upload_count == vendor.save_count == vendor.release_count == 1


def test_save_timeout_restart_reads_only_and_verifies_original(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("upload_save_timeout")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert result.data["items"][0]["uploaded_descriptor"]["TempFileName"] == "native-temp-file.pdf"
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    count = len(vendor.calls)
    recovered = reopened.execute("commit_write", approval(prepared), context=context)
    assert recovered.status == "completed", recovered.public_dict()
    assert all(call[0] == "GET" for call in vendor.calls[count:])
    assert vendor.upload_count == vendor.save_count == vendor.release_count == 1


@pytest.mark.parametrize("mutation", ["parent", "field", "permission", "module", "source", "duplicate_filename", "order"])
def test_invalid_target_or_contract_fails_before_post(tmp_path, mutation):
    engine, context, vendor = setup(tmp_path)
    value = change()
    source = deepcopy(SOURCE)
    if mutation == "parent":
        value["parent_id"] = "999"
    elif mutation == "field":
        value["fields"]["field_name"] = "abstract"
    elif mutation == "permission":
        context.credentials["simbli"]["permissions"].pop()
    elif mutation == "module":
        vendor.page = lambda: Vendor.page(vendor)
    elif mutation == "source":
        source["options"] = {"override": "x"}
    elif mutation == "duplicate_filename":
        vendor.details["ItemContents"][1]["Attachments"][0]["OrigFileName"] = "new.pdf"
    else:
        vendor.details["ItemContents"][1]["Attachments"][0]["Order"] = False
    result = engine.execute("plan_write", {"source": source, "changes": [value], "bounds": bounds()}, context=context)
    assert result.status == "failed", result.public_dict()
    assert vendor.upload_count == vendor.lock_count == 0


def test_large_file_uses_transfer_bound_not_metadata_parser_bound(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.original = DATA + b"a" * 30000
    limits = {**bounds(), "parser_bytes": 20000, "transfer_bytes": 250000}
    prepared = plan(engine, context, change(vendor.original), limits)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()


def test_changed_before_and_insufficient_commit_budget_send_no_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, limits=bounds(12))
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed" and vendor.lock_count == vendor.upload_count == 0


def test_native_lock_denial(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("lock_false")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed" and vendor.upload_count == 0 and vendor.release_count == 1


@pytest.mark.parametrize("empty", [None, []])
@pytest.mark.parametrize("visibility", [0, 1, 2])
def test_empty_supporting_field_preserves_visibility(tmp_path, empty, visibility):
    engine, context, vendor = setup(tmp_path)
    field = vendor.details["ItemContents"][1]
    field.update(Attachments=empty, HasData=False, FieldVisibility=visibility)
    prepared = plan(engine, context)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.details["ItemContents"][1]["Attachments"][0]["VisibilityMode"] == visibility


def test_existing_attachment_token_rebinds_after_insertion(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.details["ItemContents"][1]["Attachments"][0]["SecurityToken"] = "old-attachment-secret"
    prepared = plan(engine, context)
    vendor.details["ItemContents"][1]["Attachments"][0]["SecurityToken"] = "rotated-attachment-secret"
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.save_bodies[0]["itemContentDTO"][1]["Attachments"][1]["SecurityToken"] == "rotated-attachment-secret"
    assert "rotated-attachment-secret" not in json.dumps(result.data)
    assert "old-attachment-secret" not in json.dumps(prepared.data)


def test_release_failure_retains_verified_upload_result(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("release_fail")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["lock_release_error"] is True
    assert result.data["items"][0]["original_bytes_verified"] is True


def test_cancel_while_locking_sends_no_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("cancel_on_lock")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "cancelled", result.public_dict()
    assert vendor.upload_count == vendor.save_count == 0 and vendor.release_count == 1


def test_changed_item_conflicts_before_lock_or_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.details["ItemDetails"]["WIPComment"] = "concurrent edit"
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed" and vendor.lock_count == vendor.upload_count == 0


def test_cancel_after_save_can_recover_original_without_posts(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("cancel_after_save")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert vendor.upload_count == vendor.save_count == vendor.release_count == 1
    context.cancellation.clear()
    count = len(vendor.calls)
    recovered = engine.execute("commit_write", approval(prepared), context=context)
    assert recovered.status == "completed", recovered.public_dict()
    assert all(call[0] == "GET" for call in vendor.calls[count:])


def test_transfer_budget_requires_upload_and_original_readback(tmp_path):
    engine, context, vendor = setup(tmp_path)
    data = DATA + b"a" * 30000
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change(data)],
        "bounds": {**bounds(), "transfer_bytes": 50000}}, context=context)
    assert result.status == "failed"
    assert vendor.upload_count == vendor.lock_count == 0


def test_cancel_during_lock_intent_persistence_never_acquires_or_releases(tmp_path, monkeypatch):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    original = engine.storage.put

    def persist(bucket, key, value, **kwargs):
        result = original(bucket, key, value, **kwargs)
        if bucket == "receipts" and value.get("items", [{}])[0].get("lock_attempted"):
            context.cancellation.set()
        return result

    monkeypatch.setattr(engine.storage, "put", persist)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "cancelled", result.public_dict()
    assert vendor.upload_count == vendor.lock_count == vendor.release_count == 0


@pytest.mark.parametrize("filename", ["unsafe.EXE", "page.html", "shortcut.lnk"])
def test_native_restricted_extensions_fail_before_network(tmp_path, filename):
    engine, context, vendor = setup(tmp_path)
    value = change()
    value["files"][0]["filename"] = filename
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [value], "bounds": bounds()}, context=context)
    assert result.status == "failed" and not vendor.calls
