"""Previously unattributed public dispatches against pinned vendor fixture contracts."""
import base64
import json

from test_write_providers import make_engine, run


def test_legistar_public_upload_exact_binary_and_replay(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "legistar", ["matter_attachment:upload"])
    content = b"synthetic linked meeting document"
    result, approval = run(engine, context, source, {
        "key": "attachment", "entity": "matter_attachment", "operation": "upload", "parent_id": 9,
        "meeting_id": "9", "fields": {"MatterAttachmentName": "Packet", "MatterAttachmentIsHyperlink": False,
                                     "MatterAttachmentBinary": base64.b64encode(content).decode()}})
    assert result.status == "completed", result.public_dict()
    assert list(network.files.values()) == [content]
    assert any(method == "GET" and path.endswith("/File") for method, path in network.calls)
    calls = list(network.calls)
    assert engine.execute("commit_write", approval, context=context).status == "completed"
    assert network.calls == calls


def test_wistia_modern_import_url_pending_then_exact_job_resource_readback(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media_import:create"])
    url = "https://example.org/supplied-recording.mp4"
    result, approval = run(engine, context, source, {
        "key": "import", "entity": "media_import", "operation": "create", "meeting_id": "meeting1",
        "fields": {"url": url}})
    assert result.status == "partial" and result.data["items"][0]["state"] == "pending"
    assert sum(method == "POST" and path == "/modern/medias/import_url" for method, path in network.calls) == 1
    network.rows["imported1"] = {"hashed_id": "imported1", "name": "Imported", "status": "processing"}
    network.job.update(status="finished", object={"type": "bulk_operation",
        "summary": {"total": 1, "succeeded": 1, "failed": 0},
        "results": [{"position": 0, "status": "succeeded", "operation": "create",
                     "resource_type": "media", "id": "imported1"}]})
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"]["hashed_id"] == "imported1"
    assert result.data["items"][0]["readback"]["status"] == "processing"
    assert sum(method == "POST" for method, _ in network.calls) == 1
    assert "synthetic-token" not in json.dumps(result.public_dict())


def test_laserfiche_public_document_create_exact_file_readback(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "laserfiche", ["document:create"])
    content = b"synthetic new meeting packet"
    result, approval = run(engine, context, source, {
        "key": "create", "entity": "document", "operation": "create", "parent_id": 9,
        "meeting_id": "meeting1", "fields": {"name": "packet.pdf"}, "files": [{
            "part": "file", "filename": "packet.pdf", "content_type": "application/pdf",
            "content_base64": base64.b64encode(content).decode()}]})
    assert result.status == "completed", result.public_dict()
    assert network.files["1"] == content
    assert result.data["items"][0]["readback"]["_file_sha256"]
    assert any(method == "POST" and path.endswith("/9/Folder/Import") for method, path in network.calls)
    calls = list(network.calls)
    assert engine.execute("commit_write", approval, context=context).status == "completed"
    assert network.calls == calls


def test_laserfiche_existing_document_multipart_update_exact_target_and_file(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "laserfiche", ["document_large:update"])
    network.rows["1"] = {"id": 1, "name": "packet.pdf", "pageCount": 0,
                         "lastModifiedTime": "2026-11-11T00:00:00Z"}
    network.files["1"] = b"prior packet"
    content = b"synthetic replacement meeting packet"
    result, approval = run(engine, context, source, {
        "key": "replace", "entity": "document_large", "operation": "update", "resource_id": 1,
        "meeting_id": "meeting1", "fields": {"name": "packet.pdf"}, "files": [{
            "part": "file", "filename": "packet.pdf", "content_type": "application/pdf",
            "content_base64": base64.b64encode(content).decode()}]})
    assert result.status == "partial" and result.data["items"][0]["state"] == "pending"
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert network.files["1"] == content
    assert result.data["items"][0]["readback"]["_file_sha256"]
    assert sum(method == "POST" and path.endswith("/1/Document/UpdateUploadedParts")
               for method, path in network.calls) == 1
    assert not any(path.endswith("/Folder/ImportUploadedParts") for _, path in network.calls)
    assert "synthetic-signed-secret" not in json.dumps(result.public_dict())
