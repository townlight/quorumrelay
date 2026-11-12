"""Exercise large exports through actual entry points, and revocation at download time."""

import hashlib
import io
import json
import os
import zipfile
from dataclasses import replace

from starlette.testclient import TestClient

from civic_data_connectors.cli import main
from civic_data_connectors.interchange import stage_attachment
from civic_data_connectors.transports.http import create_app
from civic_data_connectors.transports.runtime import build_engine
from test_interfaces import TOKEN_A, TOKEN_B, config
from test_core import payload


def normalized(owner, context):
    result = owner.execute("normalize", {"source": {"provider": "legistar", "url": "https://example.org"}},
                           content=payload(), context=context)
    assert result.status == "completed"
    return result.data


def test_http_large_zip_scoped_stream_expiry_revocation_and_restart(tmp_path):
    database = tmp_path / "large.sqlite"
    owner, cfg = build_engine(database=database), config()
    identity = cfg.tokens[TOKEN_A]
    identity = replace(identity, authorization=frozenset({"export_attachments"}))
    cfg.tokens[TOKEN_A] = identity
    context = identity.context()
    bundle = normalized(owner, context)
    namespace = bundle["records"][0]["identity"]["namespace"]
    # Incompressible synthetic bytes keep the ZIP itself above the 16 MiB parser cap.
    raw = os.urandom(17 * 1024 * 1024)
    stage_attachment(owner, "document-1", io.BytesIO(raw), filename="packet.bin",
                     citation_url="https://example.org/packet", namespace=namespace, context=context)
    auth = {"Authorization": "Bearer " + TOKEN_A}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        result = client.post("/v1/operations/export", headers=auth, json={
            "bundle": bundle, "format": "zip", "stream": True, "attachment_ids": ["document-1"],
        }).json()
        assert result["status"] == "completed", result
        assert "content_base64" not in result["data"]
        handle = result["data"]["file_handle"]
        stream = client.get("/v1/files/" + handle, headers=auth)
        assert len(stream.content) > 16 * 1024 * 1024
        with zipfile.ZipFile(io.BytesIO(stream.content)) as archive:
            name = next(n for n in archive.namelist() if n.startswith("attachments/"))
            assert hashlib.sha256(archive.read(name)).digest() == hashlib.sha256(raw).digest()
        assert client.get("/v1/files/" + handle, headers={"Authorization": "Bearer " + TOKEN_B}).status_code == 404
        cfg.tokens[TOKEN_A] = replace(identity, allowed_namespaces=frozenset({"//different.example"}))
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 404
        cfg.tokens[TOKEN_A] = replace(identity, authorization=frozenset())
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 404
        cfg.tokens[TOKEN_A] = identity
    with TestClient(create_app(build_engine(database=database), cfg), base_url="http://127.0.0.1") as client:
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 200
        item = owner.storage.get("artifacts", handle, scope=context.scope)
        owner.storage.put("artifacts", handle, {**item.value, "expires_at": 0}, scope=context.scope,
                          expected_version=item.version)
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 404


def test_cli_output_stream_and_never_overwrite(tmp_path):
    owner = build_engine()
    bundle = normalized(owner, config().tokens[TOKEN_A].context())
    out, stderr = io.StringIO(), io.StringIO()
    target = tmp_path / "export.zip"
    request = json.dumps({"bundle": bundle, "format": "zip"})
    assert main(["export", "--output", str(target), "--file-root", str(tmp_path)],
                stdin=io.StringIO(request), stdout=out, stderr=stderr, engine=owner) == 0
    assert target.read_bytes().startswith(b"PK")
    metadata = json.loads(out.getvalue())
    assert "content_base64" not in metadata["data"]
    before = target.read_bytes()
    assert main(["export", "--output", str(target)], stdin=io.StringIO(request),
                stdout=io.StringIO(), stderr=stderr, engine=owner) == 64
    assert target.read_bytes() == before


def test_http_write_planner_can_stage_input_without_read_grants(tmp_path):
    owner, cfg = build_engine(database=tmp_path / "write-input.sqlite"), config()
    cfg.tokens[TOKEN_A] = replace(cfg.tokens[TOKEN_A], operations=frozenset({"plan_write"}))
    auth = {"Authorization": "Bearer " + TOKEN_A, "Content-Type": "application/octet-stream"}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        uploaded = client.post("/v1/files", headers=auth, content=b"authorized write attachment")
        assert uploaded.status_code == 200, uploaded.text
        handle = uploaded.json()["data"]["file_handle"]
        # Staging input is not an unrelated download or commit grant.
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 403
        cfg.tokens[TOKEN_A] = replace(cfg.tokens[TOKEN_A], operations=frozenset({"providers"}))
        assert client.post("/v1/files", headers=auth, content=b"denied").status_code == 403
