"""Exact native chunk fields and caller-declared whole-content outcome, synthetic only."""
import base64
from dataclasses import replace
from hashlib import sha256
import json
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.escribe_write import EscribeWriteAdapter
from civic_data_connectors.write_transport import WriteResponse
from test_escribe_publishing import Server, SendOnly, response, setup

ORIGINAL, CHUNK = b"ABCDEF", b"RESULT"


class UploadServer(Server):
    def __init__(self):
        super().__init__("Document")
        self.content = ORIGINAL
        self.behavior = "replace"
        self.cancel_after_send = None

    def send(self, url, **options):
        envelope = ET.fromstring(options["body"])
        node = envelope.find("{" + soap.SOAP + "}Body")[0]
        method = node.tag.split("}")[1]
        if method not in {"DocumentGetContent", "DocumentUpload"}:
            return super().send(url, **options)
        self.calls.append(method)
        relation = envelope.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        if method == "DocumentGetContent":
            value = base64.b64encode(self.content).decode()
        else:
            parameters = node.find("{" + soap.NS + "}Parameters")
            assert [n.tag.split("}")[1] for n in parameters] == [
                "Chunk", "DocumentId", "IsPrivate", "length", "offset"]
            fields = {n.tag.split("}")[1]: n.text for n in parameters}
            assert fields["DocumentId"] == "23" and fields["IsPrivate"] == "true"
            chunk = base64.b64decode(fields["Chunk"], validate=True)
            assert int(fields["length"]) == len(chunk)
            offset = int(fields["offset"])
            if self.behavior == "replace":
                self.content = chunk
            elif self.behavior == "append":
                self.content += chunk
            else:
                self.content = self.content[:offset] + chunk + self.content[offset + len(chunk):]
            self.value["FileSize"] = len(self.content)
            self.mutations += 1
            if self.cancel_after_send:
                self.cancel_after_send.set()
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("Synthetic upload response lost")
            value = "VOID"
        return WriteResponse(200, response(method, value, relation=relation),
                             {"content-type": "application/soap+xml"})


def fixture(tmp_path):
    _, _, source, context, _ = setup(tmp_path, "Document")
    server = UploadServer()
    context.credentials["escribe"]["permissions"] = ["document:upload"]
    owner = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                          write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    change = {"key": "chunk", "entity": "document", "operation": "upload", "resource_id": "23",
        "fields": {"offset": 0, "length": len(CHUNK), "IsPrivate": True,
                   "expected_document_sha256": sha256(CHUNK).hexdigest()},
        "files": [{"part": "Chunk", "filename": "source.bin", "content_type": "application/octet-stream",
                   "content_base64": base64.b64encode(CHUNK).decode()}]}
    return owner, server, source, context, change


def approval(owner, source, context, change, **extra):
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change], **extra},
                           context=context)
    assert result.status == "completed", result.public_dict()
    plan = result.data["plan"]
    prepared, = plan["changes"]
    assert prepared["native"]["body"]["Parameters"]["Chunk"]["file_reference"]
    assert base64.b64encode(CHUNK).decode() not in json.dumps(plan)
    with owner.storage.open_capture(prepared["before_content_reference"], scope=context.scope) as stream:
        assert stream.read() == ORIGINAL
    return {"plan_id": result.data["plan_id"], "plan_hash": result.data["plan_hash"]}


@pytest.mark.parametrize("loss", [False, True])
def test_single_chunk_hash_verified_recovery_capture_and_restart_no_replay(tmp_path, loss):
    owner, server, source, context, change = fixture(tmp_path)
    selected = approval(owner, source, context, change)
    assert server.mutations == 0
    server.lose_response = loss
    result = owner.execute("commit_write", selected, context=context)
    assert result.status == ("partial" if loss else "completed"), result.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    result = reopened.execute("commit_write", selected, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"]["content_sha256"] == sha256(CHUNK).hexdigest()
    assert server.mutations == 1 and server.content == CHUNK


def test_different_server_chunk_semantics_remain_uncertain_without_replay(tmp_path):
    owner, server, source, context, change = fixture(tmp_path)
    selected = approval(owner, source, context, change)
    server.behavior = "append"
    for _ in range(2):
        result = owner.execute("commit_write", selected, context=context)
        assert result.status == "partial" and result.data["items"][0]["state"] == "uncertain"
    assert server.mutations == 1 and server.content == ORIGINAL + CHUNK


def test_caller_selected_offset_and_expected_full_hash_are_not_inferred(tmp_path):
    owner, server, source, context, change = fixture(tmp_path)
    server.behavior = "splice"
    chunk = b"xy"
    change["fields"].update(offset=2, length=2, expected_document_sha256=sha256(b"ABxyEF").hexdigest())
    change["files"][0]["content_base64"] = base64.b64encode(chunk).decode()
    planned = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    assert planned.status == "completed", planned.public_dict()
    selected = {"plan_id": planned.data["plan_id"], "plan_hash": planned.data["plan_hash"]}
    result = owner.execute("commit_write", selected, context=context)
    assert result.status == "completed" and server.content == b"ABxyEF"


def test_concurrent_content_change_rejects_even_when_metadata_is_identical(tmp_path):
    owner, server, source, context, change = fixture(tmp_path)
    selected = approval(owner, source, context, change)
    server.content = b"OTHER!"
    assert owner.execute("commit_write", selected, context=context).status == "failed"
    assert server.mutations == 0


def test_post_send_cancel_retains_uncertainty_then_read_only_reconciles(tmp_path):
    owner, server, source, context, change = fixture(tmp_path)
    selected = approval(owner, source, context, change)
    server.cancel_after_send = context.cancellation
    assert owner.execute("commit_write", selected, context=context).status == "partial"
    fresh = replace(context, cancellation=OperationContext().cancellation)
    assert owner.execute("commit_write", selected, context=fresh).status == "completed"
    assert server.mutations == 1


@pytest.mark.parametrize("case", ["length", "offset", "hash", "privacy", "permission", "pages", "unknown", "resource"])
def test_invalid_or_unbound_upload_rejects_before_send(tmp_path, case):
    owner, server, source, context, change = fixture(tmp_path)
    extra = {}
    if case == "length":
        change["fields"]["length"] = 5
    elif case == "offset":
        change["fields"]["offset"] = -1
    elif case == "hash":
        change["fields"]["expected_document_sha256"] = "unknown"
    elif case == "privacy":
        change["fields"]["IsPrivate"] = False
    elif case == "permission":
        context.credentials["escribe"]["permissions"] = []
    elif case == "pages":
        extra["bounds"] = {"max_pages": 4}
    elif case == "unknown":
        change["fields"]["Finalize"] = True
    else:
        change["resource_id"] = 23.5
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change], **extra},
                           context=context)
    assert result.status == "failed" and server.mutations == 0, result.public_dict()
    if case != "privacy":
        assert not server.calls
