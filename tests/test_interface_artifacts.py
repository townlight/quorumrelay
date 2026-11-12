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


def test_cli_write_file_bound_exact_part_and_scope(tmp_path):
    from test_write_providers import make_engine
    owner, context, network, source = make_engine(tmp_path, "wistia", ["media:upload"])
    cfg = tmp_path / "trusted.json"
    cfg.write_text(json.dumps({"principal": {"principal": context.principal, "client_id": context.client_id,
        "tenant": context.tenant, "operations": ["plan_write", "commit_write", "receipt"],
        "authorization": sorted(context.authorization), "allowed_namespaces": sorted(context.allowed_namespaces),
        "credentials": context.credentials}}), encoding="utf-8")
    target = tmp_path / "synthetic.mp4"
    target.write_bytes(b"x" * 20000)
    request = {"source": source, "bounds": {"parser_bytes": 1024, "transfer_bytes": 65536},
        "changes": [{"key": "media", "entity": "media", "operation": "upload", "meeting_id": "meeting1",
            "fields": {"name": "Synthetic"}, "files": [{"part": "file", "filename": "synthetic.mp4",
                                                          "content_type": "video/mp4"}]}]}
    output = io.StringIO()
    args = ["plan_write", "--config", str(cfg), "--file-root", str(tmp_path),
            "--write-file", "media", "file", str(target)]
    assert main(args, stdin=io.StringIO(json.dumps(request)), stdout=output,
                stderr=io.StringIO(), engine=owner) == 0
    plan = json.loads(output.getvalue())["data"]
    commit_output = io.StringIO()
    assert main(["commit_write", "--config", str(cfg)],
                stdin=io.StringIO(json.dumps({key: plan[key] for key in ("plan_id", "plan_hash")})),
                stdout=commit_output, stderr=io.StringIO(), engine=owner) == 0
    committed = json.loads(commit_output.getvalue())
    assert network.last_request is not None
    assert committed["data"]["mock"] is True
    receipt_output = io.StringIO()
    assert main(["receipt", "--config", str(cfg)], stdin=io.StringIO(json.dumps({"plan_id": plan["plan_id"]})),
                stdout=receipt_output, stderr=io.StringIO(), engine=owner) == 0
    assert json.loads(receipt_output.getvalue())["data"] == committed["data"]
    missing = [*args[:-3], "media", "absent", str(target)]
    assert main(missing, stdin=io.StringIO(json.dumps(request)), stdout=io.StringIO(),
                stderr=io.StringIO(), engine=owner) == 64


def test_large_neutral_input_uses_transfer_bound_in_http_cli_and_mcp_staging(tmp_path):
    from civic_data_connectors.interchange import Attachment, write_bundle
    from civic_data_connectors.models import Bounds
    from civic_data_connectors.transports.files import InputUploads
    from test_storage_search_imports import sample
    import base64

    bundle = sample()
    raw = os.urandom(17 * 1024 * 1024)
    archive = tmp_path / "large-input.zip"
    bounds = Bounds(parser_bytes=4096, transfer_bytes=40 * 1024 * 1024)
    with archive.open("wb") as target:
        write_bundle(bundle, target, bounds=bounds,
                     attachments=[Attachment("doc", io.BytesIO(raw), "doc.bin", "https://example.org/doc")],
                     authorized_attachments=frozenset({"doc"}))
    owner, cfg = build_engine(database=tmp_path / "input.sqlite"), config(
        parser_bytes=bounds.parser_bytes, transfer_bytes=bounds.transfer_bytes)
    auth = {"Authorization": "Bearer " + TOKEN_A}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        with archive.open("rb") as source:
            uploaded = client.post("/v1/files", headers=auth, files={"file": source}).json()
        assert uploaded["status"] == "completed", uploaded
        request = {"format": "zip", "file_handle": uploaded["data"]["file_handle"]}
        result = client.post("/v1/operations/import_preview", headers=auth, json=request).json()
        assert result["status"] == "completed", result
        assert result["data"]["bundle"]["records"] == bundle["records"]
        denied = client.post("/v1/operations/import_preview", json=request,
                             headers={"Authorization": "Bearer " + TOKEN_B}).json()
        assert denied["status"] == "failed"
    out = io.StringIO()
    assert main(["import_preview", "--content", str(archive), "--file-root", str(tmp_path)],
                stdin=io.StringIO(json.dumps({"format": "zip", "bounds": {"parser_bytes": 4096}})),
                stdout=out, stderr=io.StringIO()) == 0
    assert json.loads(out.getvalue())["data"]["bundle"]["records"] == bundle["records"]
    # The exact MCP upload manager stages the same opaque core input contract.
    uploads = InputUploads(owner)
    context = cfg.tokens[TOKEN_A].context()
    pending = uploads.begin(filename="large.zip", content_type="application/zip",
                            byte_length=archive.stat().st_size, context=context)
    offset = 0
    with archive.open("rb") as source:
        while chunk := source.read(pending["max_chunk_bytes"]):
            uploads.chunk(pending["upload_id"], offset=offset,
                          content_base64=base64.b64encode(chunk).decode(), context=context)
            offset += len(chunk)
    staged = uploads.finish(pending["upload_id"], context=context)
    result = owner.execute("import_preview", {"format": "zip", "file_handle": staged["file_handle"],
        "bounds": {"parser_bytes": 4096}}, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["bundle"]["records"] == bundle["records"]
    uploads.close()


def historical_request():
    return {"provider_specific": True, "format": "civicplus-historical-files", "stream": True,
        "source": {"provider": "civicplus-select", "url": "https://city.portal.civicclerk.com"},
        "meeting": {"body": "City Council", "meeting_type": "Regular Meeting", "meeting_date": "2020-12-18"},
        "files": [{"file_type": "Agenda Packet", "content_type": "application/pdf"}]}


def historical_pdf():
    from pathlib import Path
    return (Path(__file__).parent / "fixtures" / "baseline" / "boarddocs-minooka.pdf").read_bytes()


def verify_historical_archive(content, pdf):
    name = "City Council_Regular Meeting_Agenda Packet_12_18_2020.pdf"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.read(name) == pdf
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["files"][0]["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert manifest["vendor_import_accepted"] is False


def test_http_native_export_upload_download_current_policy_ttl_hash_and_legacy(tmp_path):
    owner, cfg, pdf = build_engine(database=tmp_path / "native-http.sqlite"), config(parser_bytes=1024), historical_pdf()
    identity = replace(cfg.tokens[TOKEN_A], operations=frozenset({"export", "normalize"}),
                       authorization=frozenset({"export_attachments"}))
    cfg.tokens[TOKEN_A] = identity
    auth = {"Authorization": "Bearer " + TOKEN_A}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        uploaded = client.post("/v1/files", headers=auth, files={"file": ("packet.pdf", pdf, "application/pdf")})
        assert uploaded.status_code == 200, uploaded.text
        handle = uploaded.json()["data"]["file_handle"]
        request = historical_request()
        request["files"][0]["file_handle"] = handle
        result = client.post("/v1/operations/export", headers=auth, json=request).json()
        assert result["status"] == "completed", result
        path = result["data"]["download_path"]
        downloaded = client.get(path, headers=auth)
        assert downloaded.status_code == 200
        verify_historical_archive(downloaded.content, pdf)
        assert client.post("/v1/operations/export", headers={"Authorization": "Bearer " + TOKEN_B},
                           json=request).json()["status"] == "failed"
        cfg.tokens[TOKEN_A] = replace(identity, authorization=frozenset())
        assert client.get(path, headers=auth).status_code == 404
        assert client.post("/v1/operations/export", headers=auth, json=request).json()["status"] == "failed"
        cfg.tokens[TOKEN_A] = replace(identity, allowed_namespaces=frozenset({"//other.example"}))
        assert client.get(path, headers=auth).status_code == 404
        cfg.tokens[TOKEN_A] = identity
        stored = owner.storage.get("service_files", handle, scope=identity.context().scope)
        assert stored.value["purpose"] == "input"
        assert stored.value["reference"] == stored.value["storage_reference"]
        owner.storage.put("service_files", handle, {**stored.value, "sha256": "0" * 64},
                          scope=identity.context().scope, expected_version=stored.version)
        assert client.post("/v1/operations/export", headers=auth, json=request).json()["status"] == "failed"
        changed = owner.storage.get("service_files", handle, scope=identity.context().scope)
        owner.storage.put("service_files", handle, {**stored.value, "expires_at": 0},
                          scope=identity.context().scope, expected_version=changed.version)
        assert client.get("/v1/files/" + handle, headers=auth).status_code == 404
        assert client.post("/v1/operations/export", headers=auth, json=request).json()["status"] == "failed"
        # Historical persisted handles retain exact scoped reads, without invented MIME or expiry.
        legacy = "a" * 64
        reference = owner.storage.save_capture(io.BytesIO(payload()), scope=identity.context().scope, max_bytes=65536)
        owner.storage.put("service_files", legacy, {"reference": reference}, scope=identity.context().scope)
        assert client.get("/v1/files/" + legacy, headers=auth).content == payload()
        parsed = client.post("/v1/operations/normalize", headers=auth, json={"file_handle": legacy,
            "source": {"provider": "legistar", "url": "https://example.org"}}).json()
        assert parsed["status"] == "completed", parsed
        request["files"][0]["file_handle"] = legacy
        legacy_export = client.post("/v1/operations/export", headers=auth, json=request).json()
        assert legacy_export["status"] == "failed"
        assert "new generic file upload" in legacy_export["errors"][0]["message"]
        cfg.tokens[TOKEN_A] = replace(identity, operations=frozenset({"providers"}))
        assert client.post("/v1/files", headers=auth, content=b"denied").status_code == 403


def test_http_fetch_and_discover_only_uploads_consume_generic_handles(tmp_path):
    from test_interfaces import CAPTURE, DISCOVER
    owner, cfg = build_engine(database=tmp_path / "read-input.sqlite"), config()
    original = cfg.tokens[TOKEN_A]
    auth = {"Authorization": "Bearer " + TOKEN_A, "Content-Type": "application/octet-stream"}
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        for operation in ("fetch", "discover"):
            cfg.tokens[TOKEN_A] = replace(original, operations=frozenset({operation}))
            uploaded = client.post("/v1/files", headers=auth, content=CAPTURE)
            assert uploaded.status_code == 200, uploaded.text
            result = client.post("/v1/operations/" + operation,
                headers={"Authorization": auth["Authorization"]}, json={
                    "source": DISCOVER["source"], "file_handle": uploaded.json()["data"]["file_handle"]}).json()
            assert result["status"] in {"completed", "partial"}, result


def test_http_progress_is_coalesced_but_latest_progress_and_terminal_state_persist(tmp_path):
    from civic_data_connectors.models import OperationResult
    owner, cfg = build_engine(database=tmp_path / "progress.sqlite"), config()
    writes, original_put_many = [], owner.storage.put_many
    def counted(changes, **kwargs):
        changes = list(changes)
        writes.extend(changes)
        return original_put_many(changes, **kwargs)
    owner.storage.put_many = counted
    def reporting(owner, request, content, context):
        for index in range(100):
            context.report(stage="normalize", completed=index + 1, total=100)
        return OperationResult("completed", data={"records": []})
    owner.handlers["discover"] = reporting
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        result = client.post("/v1/operations/discover", headers={"Authorization": "Bearer " + TOKEN_A}, json={}).json()
        assert result["status"] == "completed", result
        saved = owner.storage.get("operations", result["operation_id"], scope=cfg.tokens[TOKEN_A].context().scope)
        assert saved.value["state"] == "completed"
        assert saved.value["progress"]["completed"] == 100
        assert len(writes) < 10


def test_cli_native_export_file_output_exact_and_no_overwrite(tmp_path):
    owner, pdf = build_engine(), historical_pdf()
    trusted = tmp_path / "export-policy.json"
    trusted.write_text(json.dumps({"principal": {"operations": ["export"],
        "authorization": ["export_attachments"]}}), encoding="utf-8")
    source, target = tmp_path / "packet.pdf", tmp_path / "historical.zip"
    source.write_bytes(pdf)
    request = historical_request()
    request["bounds"] = {"parser_bytes": 1024}
    args = ["export", "--config", str(trusted), "--file-root", str(tmp_path),
            "--export-file", "0", str(source), "--output", str(target)]
    stdout, stderr = io.StringIO(), io.StringIO()
    assert main(args, stdin=io.StringIO(json.dumps(request)), stdout=stdout, stderr=stderr, engine=owner) == 0, stderr.getvalue()
    verify_historical_archive(target.read_bytes(), pdf)
    before = target.read_bytes()
    assert main(args, stdin=io.StringIO(json.dumps(request)), stdout=io.StringIO(), stderr=io.StringIO(), engine=owner) == 64
    assert target.read_bytes() == before


def test_mcp_native_upload_export_resource_exact_and_revoked_grants():
    import base64
    import anyio
    import pytest
    from mcp import Client
    from civic_data_connectors.transports.mcp import create_server
    from civic_data_connectors.transports.runtime import Principal, ServiceConfig

    owner, pdf = build_engine(), historical_pdf()
    identity = Principal(operations=frozenset({"export"}), authorization=frozenset({"export_attachments"}))
    cfg = ServiceConfig(local=identity, parser_bytes=1024)
    server = create_server(owner, config=cfg)

    async def run():
        async with Client(server, read_timeout_seconds=15) as client:
            started = await client.call_tool("upload_begin", {"filename": "packet.pdf", "content_type": "application/pdf", "byte_length": len(pdf)})
            upload_id = started.structured_content["data"]["upload_id"]
            chunked = await client.call_tool("upload_chunk", {"upload_id": upload_id, "offset": 0,
                "content_base64": base64.b64encode(pdf).decode()})
            assert chunked.structured_content["status"] == "completed"
            staged = await client.call_tool("upload_finish", {"upload_id": upload_id})
            request = historical_request()
            request["files"][0]["file_handle"] = staged.structured_content["data"]["file_handle"]
            exported = (await client.call_tool("export", {"request": request})).structured_content
            assert exported["status"] == "completed", exported
            uri = f"civic-artifact://{exported['data']['artifact_id']}/0"
            resource = await client.read_resource(uri)
            value = json.loads(resource.contents[0].text)
            archive = base64.b64decode(value["content_base64"])
            assert hashlib.sha256(archive).hexdigest() == value["sha256"]
            verify_historical_archive(archive, pdf)
            cfg.local = replace(identity, authorization=frozenset())
            assert (await client.call_tool("export", {"request": request})).structured_content["status"] == "failed"
            with pytest.raises(Exception):
                await client.read_resource(uri)
            cfg.local = replace(identity, principal="other")
            assert (await client.call_tool("export", {"request": request})).structured_content["status"] == "failed"
    try:
        anyio.run(run)
    finally:
        server._civic_input_uploads.close()
