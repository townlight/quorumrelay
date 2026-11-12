"""Actual coordinator MediaVault chunk/registration paths, pinned literal WSDL expectations."""

import base64
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from test_granicus_write import MediaNetwork, SOAP, setup, plan
from civic_data_connectors.providers.granicus_vault import NAMESPACE
from civic_data_connectors.write_files import stage_write_file
from civic_data_connectors.write_transport import WriteResponse

BUCKET = "df23e2ab-c655-49ea-9c24-8593212b3a86"
CLIP_UID = "83c3b8e1-496c-4aba-b37d-59866426fb47"
WSDL = ET.fromstring((Path(__file__).parents[1] / "docs/capabilities/evidence/granicus-platform/SDK.asmx.wsdl").read_bytes())
XSD = "http://www.w3.org/2001/XMLSchema"


class ChunkNetwork(MediaNetwork):
    def __init__(self, assignment=False):
        super().__init__()
        self.chunks = bytearray()
        self.vault_calls = []
        self.loss = "none"
        self.cancel_after_chunk = None
        if assignment:
            self.uploaded = b"old supplied bytes"
            self.values.update(ID=19, UID=CLIP_UID)

    def send(self, url, **kwargs):
        root = ET.fromstring(kwargs["body"])
        request = list(root.find(f"{{{SOAP}}}Body"))[0]
        method = request.tag.rsplit("}", 1)[-1]
        if method not in {"StartUpload", "SendChunk", "FinishUpload", "RegisterUploadedFile", "AssignUploadedFile"}:
            if method == "GetClip" and self.loss == "readback" and "RegisterUploadedFile" in self.vault_calls:
                self.loss = "none"
                raise TimeoutError("Synthetic registered clip readback loss")
            return super().send(url, **kwargs)
        self.vault_calls.append(method)
        assert url == "https://synthetic-media.granicus.com/MediaVault/SDK.asmx"
        assert "Cookie" not in kwargs["headers"]
        schema = WSDL.find(f'.//{{{XSD}}}element[@name="{method}"]/{{{XSD}}}complexType/{{{XSD}}}sequence')
        assert [child.tag for child in request] == [f'{{{NAMESPACE}}}{field.get("name")}' for field in (list(schema) if schema is not None else [])]
        def get(key):
            return request.findtext(f"{{{NAMESPACE}}}{key}")
        if method != "StartUpload":
            assert get("GUID") == BUCKET
        if method == "StartUpload":
            value = BUCKET
        elif method == "SendChunk":
            assert int(get("ChunkPosition")) == len(self.chunks)
            self.chunks.extend(base64.b64decode(get("bytes"), validate=True))
            value = "received"
            if self.cancel_after_chunk:
                self.cancel_after_chunk()
        elif method == "FinishUpload":
            value = "17"  # SDK promises a long checksum, not a SHA algorithm.
        elif method == "RegisterUploadedFile":
            assert get("FolderID") == "11" and get("Name") == "Approved clip" and get("Extension") == "mp4"
            self.uploaded = bytes(self.chunks)
            self.values.update(ID=19, UID=CLIP_UID, Name=get("Name"), Status="Pending")
            value = "19"
        else:
            assert get("ClipUID") == CLIP_UID and get("Extension") == "mp4"
            self.uploaded = bytes(self.chunks)
            value = None
        if self.loss == method:
            self.loss = "none"
            raise TimeoutError("Synthetic MediaVault stage response loss")
        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        response = ET.SubElement(ET.SubElement(envelope, f"{{{SOAP}}}Body"), f"{{{NAMESPACE}}}{method}Response")
        if value is not None:
            ET.SubElement(response, f"{{{NAMESPACE}}}{method}Result").text = value
        return WriteResponse(200, ET.tostring(envelope))


def chunk_setup(tmp_path, assignment=False):
    network = ChunkNetwork(assignment)
    engine, _, context, change = setup(tmp_path, network)
    context.credentials["granicus"].update(permissions=["chunked_recording:upload", "chunked_recording:update"],
        folder_ids=["11"], resource_ids=["19"], meeting_ids=["7"], media_origin="https://synthetic-media.granicus.com")
    data = b"synthetic whole media input"
    handle = stage_write_file(engine, io.BytesIO(data), context=context, filename="input.mp4", content_type="video/mp4")
    change.update(entity="chunked_recording", operation="update" if assignment else "upload",
        resource_id="19" if assignment else None, meeting_id="7",
        fields={"FolderID": 11, "Extension": "mp4", "ChunkBytes": 5,
                **({"ClipUID": CLIP_UID} if assignment else {"Name": "Approved clip"})},
        files=[{"part": "bytes", "filename": "input.mp4", "content_type": "video/mp4", "file_handle": handle}])
    return engine, network, context, change, data


@pytest.mark.parametrize("loss", ["none", "StartUpload", "SendChunk", "FinishUpload", "RegisterUploadedFile", "readback"])
def test_chunked_registration_private_durable_state_and_uncertain_no_replay(tmp_path, loss):
    engine, network, context, change, data = chunk_setup(tmp_path)
    request = plan(engine, context, change)
    network.loss = loss
    first = engine.execute("commit_write", request, context=context)
    assert first.status == ("completed" if loss == "none" else "partial"), first.errors
    count = len(network.vault_calls)
    result = engine.execute("commit_write", request, context=context)
    assert result.status == ("completed" if loss in {"none", "readback"} else "partial"), result.errors
    assert len(network.vault_calls) == count  # No Start/Chunk/Finish/Register replay.
    assert BUCKET not in json.dumps(result.public_dict())
    stored = engine.storage.get("write_plans", request["plan_id"], scope=context.scope).value
    assert BUCKET not in json.dumps(stored)
    private = engine.storage.list("private_provider_uploads", scope=context.scope)
    assert len(private) == 1 and private[0].value["binding"]
    if loss != "StartUpload":
        assert private[0].value["bucket_guid"] == BUCKET
    if loss in {"none", "readback"}:
        assert network.uploaded == data
        item = result.data["items"][0]
        assert item["provider_checksum"] == 17 and item["checksum_algorithm"] == "vendor_unspecified"
        assert item["playable_media_verified"] is False and item["publication_requested"] is False


@pytest.mark.parametrize("loss", ["none", "AssignUploadedFile"])
def test_chunked_assignment_exact_existing_clip_and_no_uncertain_replay(tmp_path, loss):
    engine, network, context, change, data = chunk_setup(tmp_path, True)
    request = plan(engine, context, change)
    network.loss = loss
    first = engine.execute("commit_write", request, context=context)
    assert first.status == ("completed" if loss == "none" else "partial"), first.errors
    count = len(network.vault_calls)
    result = engine.execute("commit_write", request, context=context)
    assert result.status == first.status and len(network.vault_calls) == count
    assert network.uploaded == data and BUCKET not in json.dumps(result.public_dict())


def test_chunk_cancellation_stops_after_acknowledged_chunk_without_restarting(tmp_path):
    engine, network, context, change, _ = chunk_setup(tmp_path)
    request = plan(engine, context, change)
    def cancel():
        state = engine.storage.get("operations", request["plan_id"], scope=context.scope)
        engine.storage.put("operations", request["plan_id"], {**state.value, "cancel_requested": True},
                           scope=context.scope, expected_version=state.version)
    network.cancel_after_chunk = cancel
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "partial" and network.vault_calls == ["StartUpload", "SendChunk"]
    assert engine.execute("commit_write", request, context=context).status == "partial"
    assert network.vault_calls == ["StartUpload", "SendChunk"]


def test_chunk_private_state_binding_and_reflected_bucket_never_become_receipt(tmp_path):
    engine, network, context, change, _ = chunk_setup(tmp_path)
    request = plan(engine, context, change)
    network.loss = "readback"
    assert engine.execute("commit_write", request, context=context).status == "partial"
    row = engine.storage.list("private_provider_uploads", scope=context.scope)[0]
    engine.storage.put("private_provider_uploads", row.key, {**row.value, "binding": "different-plan"},
        scope=context.scope, expected_version=row.version)
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "partial" and BUCKET not in json.dumps(result.public_dict())
    row = engine.storage.get("private_provider_uploads", row.key, scope=context.scope)
    stored_plan = engine.storage.get("write_plans", request["plan_id"], scope=context.scope).value["plan"]
    from civic_data_connectors.engine import canonical_hash
    # Use the actual public Source representation from the immutable plan.
    binding = canonical_hash({"prepared": stored_plan["changes"][0], "source": stored_plan["source"], "scope": context.scope})
    engine.storage.put("private_provider_uploads", row.key, {**row.value, "binding": binding},
        scope=context.scope, expected_version=row.version)
    network.values["Name"] = BUCKET  # A hostile provider must not reflect the private control GUID.
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "partial" and BUCKET not in json.dumps(result.public_dict())
