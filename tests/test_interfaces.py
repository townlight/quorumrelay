"""Synthetic interface acceptance, including a real Node process and loopback ASGI server."""

import base64
import io
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator
from starlette.testclient import TestClient

from civic_data_connectors.cli import main
from civic_data_connectors.models import OperationResult
from civic_data_connectors.transports.http import create_app
from civic_data_connectors.transports.openapi import document
from civic_data_connectors.transports.runtime import Principal, ServiceConfig, build_engine

ROOT = Path(__file__).resolve().parents[1]
TOKEN_A = "synthetic-test-client-a-no-deployment"
TOKEN_B = "synthetic-test-client-b-no-deployment"
CAPTURE = json.dumps([{
    "EventId": 7, "EventBodyName": "Council", "EventDate": "2026-11-11T00:00:00",
    "EventTime": "7:00 PM", "EventRowVersion": "r7", "EventComment": "Parks budget",
    "unknown": [None, False, 0, "", {"non_ascii": "café"}],
}], ensure_ascii=False).encode()
DISCOVER = {
    "source": {"provider": "legistar", "url": "https://mock-city.legistar.com/Calendar.aspx",
               "input_format": "legistar-events-json"},
    "content_base64": base64.b64encode(CAPTURE).decode(),
    "bounds": {"date_from": "2026-11-11", "date_to": "2026-11-11"},
}


def config(**kwargs):
    return ServiceConfig(tokens={
        TOKEN_A: Principal(principal="editor-a", client_id="test", tenant="newsroom-a"),
        TOKEN_B: Principal(principal="editor-b", client_id="test", tenant="newsroom-b"),
    }, **kwargs)


def test_cli_saved_file_stdin_jsonl_and_exit_codes(tmp_path):
    owner = build_engine(database=tmp_path / "cli.sqlite")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = main(["discover"], stdin=io.StringIO(json.dumps(DISCOVER)), stdout=stdout, stderr=stderr, engine=owner)
    result = json.loads(stdout.getvalue())
    assert code == 2 and result["status"] == "partial" and len(result["data"]["records"]) == 1
    assert not stderr.getvalue()
    saved = tmp_path / "request.json"
    saved.write_text("{}", encoding="utf-8")
    stdout = io.StringIO()
    assert main(["providers", "--request", str(saved), "--file-root", str(tmp_path)],
                stdout=stdout, stderr=stderr, engine=owner) == 0
    assert len(json.loads(stdout.getvalue())["data"]["providers"]) == 31
    stdout, stderr = io.StringIO(), io.StringIO()
    assert main(["providers", "--jsonl"], stdin=io.StringIO("{}\ninvalid\n{}\n"),
                stdout=stdout, stderr=stderr, engine=owner) == 64
    assert [json.loads(x)["status"] for x in stdout.getvalue().splitlines()] == ["completed", "failed", "completed"]
    assert stderr.getvalue()
    stdout = io.StringIO()
    assert main(["providers", "--request", str(saved), "--file-root", str(tmp_path / "absent")],
                stdout=stdout, stderr=stderr, engine=owner) == 64
    assert json.loads(stdout.getvalue())["status"] == "failed"


def test_http_real_schemas_parity_auth_scopes_and_multipart(tmp_path):
    owner = build_engine(database=tmp_path / "http.sqlite")
    cfg = config()
    with TestClient(create_app(owner, cfg), base_url="http://127.0.0.1") as client:
        assert client.post("/v1/operations/providers", json={}).status_code == 401
        auth = {"Authorization": "Bearer " + TOKEN_A}
        assert client.post("/v1/operations/providers", headers={**auth, "Origin": "https://evil.example"}, json={}).status_code == 403
        assert client.post("/v1/operations/providers", headers={**auth, "Host": "evil.example"}, json={}).status_code == 400
        assert client.post("/v1/operations/providers", headers=auth, json={"tenant": "newsroom-b"}).status_code == 400
        result = client.post("/v1/operations/discover", headers=auth, json=DISCOVER).json()
        assert result["status"] == "partial"
        assert result["coverage"]["scope"] == "one saved capture, not a complete upstream catalog"
        validate = Draft202012Validator(document()["components"]["schemas"]["result"])
        validate.validate(result)
        imported = client.post("/v1/operations/import_bundle", headers=auth,
                               json={"result": result, "persist": True}).json()
        assert imported["status"] == "partial" and imported["data"]["persisted"]
        found = client.post("/v1/operations/search", headers=auth, json={"query": {"terms": ["Council"]}}).json()
        assert len(found["data"]["hits"]) == 1
        hidden = client.post("/v1/operations/search", headers={"Authorization": "Bearer " + TOKEN_B},
                             json={"query": {"terms": ["Council"]}}).json()
        assert hidden["data"]["hits"] == []
        preview = client.post("/v1/operations/import_preview", headers=auth,
                              json={"bundle": imported["data"]["bundle"]}).json()
        assert preview["data"]["persisted"] is False
        exported = client.post("/v1/operations/export", headers=auth,
                               json={"bundle": imported["data"]["bundle"], "format": "zip"}).json()
        assert exported["status"] in {"completed", "partial"}, exported
        assert base64.b64decode(exported["data"]["content_base64"]).startswith(b"PK")
        uploaded = client.post("/v1/files", headers=auth,
                               files={"file": ("../../hostile.bin", CAPTURE)}).json()
        handle = uploaded["data"]["file_handle"]
        download = client.get("/v1/files/" + handle, headers=auth)
        assert download.content == CAPTURE
        assert "hostile" not in download.headers["content-disposition"]
        assert client.get("/v1/files/" + handle, headers={"Authorization": "Bearer " + TOKEN_B}).status_code == 404
        req = {k: v for k, v in DISCOVER.items() if k != "content_base64"}
        req["file_handle"] = handle
        via_handle = client.post("/v1/operations/discover", headers=auth, json=req).json()
        assert via_handle["data"]["records"][0]["identity"] == result["data"]["records"][0]["identity"]
        for value in (imported, found, preview, exported, uploaded, via_handle):
            validate.validate(value)
        assert len(client.get("/openapi.json").json()["paths"]) >= 30
        assert client.post("/v1/operations/plan_write", headers=auth, json={}).status_code == 403


def test_separate_parser_and_transfer_bounds_and_unsafe_handles(tmp_path):
    cfg = config(parser_bytes=8, transfer_bytes=40, json_bytes=1024)
    with TestClient(create_app(build_engine(database=tmp_path / "limits.sqlite"), cfg),
                    base_url="http://127.0.0.1") as client:
        auth = {"Authorization": "Bearer " + TOKEN_A}
        up = client.post("/v1/files", headers={**auth, "Content-Type": "application/octet-stream"},
                         content=b"x" * 32).json()
        assert up["status"] == "completed"
        handle = up["data"]["file_handle"]
        assert len(client.get("/v1/files/" + handle, headers=auth).content) == 32
        assert client.post("/v1/operations/normalize", headers=auth,
                           json={"file_handle": handle}).status_code == 400
        assert client.post("/v1/files", headers={**auth, "Content-Type": "application/octet-stream"},
                           content=b"x" * 41).status_code == 413
        assert client.post("/v1/operations/providers", headers={**auth, "Content-Type": "application/json"},
                           content=b" " * 1025).status_code == 413
        assert client.get("/v1/files/..%5Csecret", headers=auth).status_code == 404


def test_async_status_cancel_and_restart_preserve_state(tmp_path):
    owner = build_engine(database=tmp_path / "jobs.sqlite")
    def bounded(engine, request, content, context):
        for i in range(100):
            if context.check_cancelled():
                return OperationResult("cancelled", data={"completed": i})
            context.report(completed=i, total=100)
            time.sleep(0.01)
        return OperationResult("completed")
    # Provider logic remains in the engine; this synthetic handler exercises the transport only.
    owner.handlers["discover"] = bounded
    auth = {"Authorization": "Bearer " + TOKEN_A}
    with TestClient(create_app(owner, config()), base_url="http://127.0.0.1") as client:
        submitted = client.post("/v1/jobs/discover", headers=auth, json={}).json()
        operation_id = submitted["operation_id"]
        assert submitted["status"] == "partial"
        cancel = client.post("/v1/operations/cancel", headers=auth, json={"operation_id": operation_id}).json()
        assert cancel["data"]["cancel_requested"]
    with TestClient(create_app(build_engine(database=tmp_path / "jobs.sqlite"), config()),
                    base_url="http://127.0.0.1") as client:
        result = client.post("/v1/operations/status", headers=auth, json={"operation_id": operation_id}).json()
        assert result["data"]["result"]["status"] == "cancelled"


def test_node_independent_tarball_client_real_loopback_sequence(tmp_path):
    """No JS fetch mock: Node crosses an actual socket to a separately started service."""
    if not (ROOT / "client" / "dist" / "index.js").is_file():
        pytest.fail("Build client with npm run build before interface acceptance.")
    package = subprocess.run(["npm.cmd", "pack", "--pack-destination", str(tmp_path)],
                             cwd=ROOT / "client", capture_output=True, text=True, check=True)
    tarball = tmp_path / package.stdout.strip().splitlines()[-1]
    subprocess.run(["npm.cmd", "install", "--ignore-scripts", "--no-audit", "--no-fund", str(tarball)],
                   cwd=tmp_path, capture_output=True, text=True, check=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config_path = tmp_path / "service.json"
    config_path.write_text(json.dumps({"service": {
        "port": port, "tokens": {TOKEN_A: {"principal": "editor-a", "client_id": "fifth-client", "tenant": "independent"}}
    }}), encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-m", "quorumrelay", "serve", "--config", str(config_path),
                               "--database", str(tmp_path / "node.sqlite")],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(url + "/v1/info", headers={"Authorization": "Bearer " + TOKEN_A}, timeout=.2).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(.05)
        else:
            pytest.fail("Loopback service did not start.")
        script = tmp_path / "fifth.mjs"
        script.write_text("""
import assert from 'node:assert/strict';
import {CivicConnectorClient, ServiceError} from 'quorumrelay-client';
const client = new CivicConnectorClient({baseUrl:process.env.CIVIC_CONNECTOR_URL,token:process.env.CIVIC_CONNECTOR_TOKEN});
const info = await client.info(); assert.equal(info.data.version,'0.1.0.dev5');
const discovered = await client.execute('discover',JSON.parse(process.env.CIVIC_REQUEST));
assert.equal(discovered.status,'partial'); assert.equal(discovered.data.records.length,1);
const preview = await client.execute('import_preview',{result:discovered}); assert.equal(preview.data.persisted,false);
const imported = await client.execute('import_bundle',{result:discovered,persist:true}); assert.equal(imported.data.persisted,true);
const search = await client.execute('search',{query:{terms:['Council']}}); assert.equal(search.data.hits.length,1);
const exported = await client.execute('export',{bundle:imported.data.bundle,format:'zip'});
assert.equal(Buffer.from(exported.data.content_base64,'base64').subarray(0,2).toString(),'PK');
const up = await client.upload(new Blob(['fifth independent client'])); const down = await client.download(up.data.file_handle);
assert.equal(await down.text(),'fifth independent client');
const unauth = new CivicConnectorClient({baseUrl:process.env.CIVIC_CONNECTOR_URL});
await assert.rejects(()=>unauth.info(),e=>e instanceof ServiceError && e.httpStatus===401);
console.log(JSON.stringify({status:'PASS',transport:'Node -> loopback HTTP',sequence:['discover','search','import_preview','import_bundle','export','upload','download']}));
""", encoding="utf-8")
        env = {**os.environ, "CIVIC_CONNECTOR_URL": url, "CIVIC_CONNECTOR_TOKEN": TOKEN_A,
               "CIVIC_REQUEST": json.dumps(DISCOVER)}
        node = subprocess.run(["node", str(script)], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=30)
        assert node.returncode == 0, node.stdout + node.stderr
        assert json.loads(node.stdout)["status"] == "PASS"
    finally:
        server.terminate()
        server.communicate(timeout=10)
