"""Central opaque input parity and bounded upload sessions, using synthetic bytes only."""

import base64
import hashlib
import io
import json
from dataclasses import replace

import pytest
from starlette.testclient import TestClient

from civic_data_connectors.cli import main
from civic_data_connectors.interchange import open_input
from civic_data_connectors.transports.files import CHUNK_BYTES, InputUploads
from civic_data_connectors.transports.http import create_app
from civic_data_connectors.transports.runtime import Principal, build_engine, execute
from test_interfaces import CAPTURE, DISCOVER, TOKEN_A, config


def test_cli_upload_restart_exact_metadata_bounds_and_scope(tmp_path):
    database, source = tmp_path / "inputs.sqlite", tmp_path / "capture.json"
    source.write_bytes(CAPTURE)
    args = ["upload", "--database", str(database), "--content", str(source),
            "--content-type", "application/json", "--file-root", str(tmp_path)]
    output = io.StringIO()
    assert main(args, stdout=output, stderr=io.StringIO()) == 0
    staged = json.loads(output.getvalue())
    assert staged["status"] == "completed"
    assert staged["data"] == {
        "file_handle": staged["data"]["file_handle"], "filename": source.name,
        "content_type": "application/json", "byte_length": len(CAPTURE),
        "sha256": hashlib.sha256(CAPTURE).hexdigest(),
    }
    owner, identity = build_engine(database=database), Principal()
    metadata, stream = open_input(owner, staged["data"]["file_handle"], context=identity.context())
    with stream:
        assert stream.read() == CAPTURE
    assert metadata == staged["data"]
    request = {key: value for key, value in DISCOVER.items() if key != "content_base64"}
    request["file_handle"] = metadata["file_handle"]
    result = execute(owner, identity, "discover", request)
    assert result.status == "partial" and len(result.data["records"]) == 1
    with pytest.raises(ValueError):
        open_input(owner, metadata["file_handle"], context=replace(identity, client_id="other").context())
    assert execute(owner, identity, "normalize", {**request, "bounds": {"parser_bytes": 8}}).status == "failed"
    for invalid in (
        ["upload", "--content", str(source), "--content-type", "application/json"],
        ["upload", "--database", str(database), "--content", str(source)],
        [*args, "--jsonl"],
        [*args, "--file-root", str(tmp_path / "absent")],
    ):
        assert main(invalid, stdout=io.StringIO(), stderr=io.StringIO()) == 64
    policy = tmp_path / "limits.json"
    policy.write_text(json.dumps({"service": {"transfer_bytes": len(CAPTURE)}}), encoding="utf-8")
    assert main([*args, "--config", str(policy)], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    source.write_bytes(CAPTURE + b"x")
    assert main([*args, "--config", str(policy)], stdout=io.StringIO(), stderr=io.StringIO()) == 64


def test_http_input_staging_core_metadata_and_top_level_write_rejection(tmp_path):
    owner, cfg = build_engine(database=tmp_path / "http-input.sqlite"), config(parser_bytes=1024)
    cfg.tokens[TOKEN_A] = replace(cfg.tokens[TOKEN_A], operations=frozenset({"plan_write", "fetch"}))
    auth = {"Authorization": "Bearer " + TOKEN_A}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        result = client.post("/v1/files", headers=auth,
                             files={"file": ("synthetic.mp4", b"x" * 20000, "video/mp4")})
        assert result.status_code == 200, result.text
        value = result.json()["data"]
        stored = owner.storage.get("service_files", value["file_handle"],
                                   scope=cfg.tokens[TOKEN_A].context().scope).value
        assert stored["purpose"] == "input" and "reference" not in stored
        assert stored["filename"] == "synthetic.mp4" and stored["content_type"] == "video/mp4"
        denied = client.post("/v1/operations/plan_write", headers=auth, json={"file_handle": value["file_handle"]})
        assert denied.status_code == 400
        assert "changes[].files[]" in denied.json()["errors"][0]["message"]
        assert "parser" not in denied.json()["errors"][0]["message"]
        assert client.get("/v1/files/" + value["file_handle"], headers=auth).content == b"x" * 20000
        cfg.tokens[TOKEN_A] = replace(cfg.tokens[TOKEN_A], operations=frozenset({"fetch"}))
        assert client.get("/v1/files/" + value["file_handle"], headers=auth).status_code == 200
        cfg.tokens[TOKEN_A] = replace(cfg.tokens[TOKEN_A], operations=frozenset({"providers", "fetch"}))
        stored["expires_at"] = 0
        item = owner.storage.get("service_files", value["file_handle"],
                                 scope=cfg.tokens[TOKEN_A].context().scope)
        owner.storage.put("service_files", value["file_handle"], stored,
                          scope=cfg.tokens[TOKEN_A].context().scope, expected_version=item.version)
        assert client.get("/v1/files/" + value["file_handle"], headers=auth).status_code == 404


def test_chunk_upload_exact_boundaries_retries_scope_expiry_abort_and_cleanup(tmp_path):
    owner, context = build_engine(database=tmp_path / "chunks.sqlite"), Principal().context()
    uploads = InputUploads(owner, max_bytes=2 * CHUNK_BYTES)
    data = b"x" * CHUNK_BYTES + b"y" * CHUNK_BYTES
    pending = uploads.begin(filename="bytes.bin", content_type="application/octet-stream",
                            byte_length=len(data), context=context)
    identifier = pending["upload_id"]
    first = base64.b64encode(data[:CHUNK_BYTES]).decode()
    assert uploads.chunk(identifier, offset=0, content_base64=first, context=context)["offset"] == CHUNK_BYTES
    assert uploads.chunk(identifier, offset=0, content_base64=first, context=context)["offset"] == CHUNK_BYTES
    for offset, chunk in ((0, b"wrong"), (CHUNK_BYTES + 1, b"x"), (CHUNK_BYTES, b"x" * (CHUNK_BYTES + 1))):
        with pytest.raises(ValueError):
            uploads.chunk(identifier, offset=offset, content_base64=base64.b64encode(chunk).decode(), context=context)
    with pytest.raises(ValueError):
        uploads.finish(identifier, context=context)
    with pytest.raises(ValueError):
        uploads.chunk(identifier, offset=CHUNK_BYTES, content_base64="eA==",
                      context=Principal(client_id="other").context())
    uploads.chunk(identifier, offset=CHUNK_BYTES, content_base64=base64.b64encode(data[CHUNK_BYTES:]).decode(),
                  context=context)
    staged = uploads.finish(identifier, context=context)
    assert staged["sha256"] == hashlib.sha256(data).hexdigest()
    _, stream = open_input(owner, staged["file_handle"], context=context)
    with stream:
        assert stream.read() == data
    for size in (-1, True, 2 * CHUNK_BYTES + 1):
        with pytest.raises(ValueError):
            uploads.begin(filename="x", content_type="application/octet-stream", byte_length=size, context=context)
    pending = uploads.begin(filename="empty", content_type="application/octet-stream", byte_length=0, context=context)
    item = uploads.values[(context.scope, pending["upload_id"])]
    item["expires_at"] = 0
    with pytest.raises(ValueError):
        uploads.finish(pending["upload_id"], context=context)
    assert item["stream"].closed
    pending = uploads.begin(filename="empty", content_type="application/octet-stream", byte_length=0, context=context)
    assert uploads.abort(pending["upload_id"], context=context)["aborted"]
    for _ in range(16):
        uploads.begin(filename="empty", content_type="application/octet-stream", byte_length=0, context=context)
    with pytest.raises(ValueError):
        uploads.begin(filename="empty", content_type="application/octet-stream", byte_length=0, context=context)
    streams = [item["stream"] for item in uploads.values.values()]
    uploads.close()
    assert not uploads.values and all(stream.closed for stream in streams)
