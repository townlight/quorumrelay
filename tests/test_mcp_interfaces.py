"""Official SDK clients over real stdio and Streamable HTTP, modern and legacy."""

import base64
import io
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import anyio
import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from interface_mock_server import TOKEN, TOKEN_B, engine, principal
from civic_data_connectors.cli import main
from test_interfaces import DISCOVER
from test_writes import create_request

SERVER = Path(__file__).with_name("interface_mock_server.py")


async def sequence(client):
    async def call(name, request):
        result = await client.call_tool(name, {"request": request})
        assert result.structured_content is not None, result
        return result.structured_content

    tools = await client.list_tools()
    names = {x.name for x in tools.tools}
    assert {"discover", "search", "import_preview", "import_bundle", "export",
            "plan_write", "commit_write", "receipt", "status", "cancel"} <= names
    discovered = await call("discover", DISCOVER)
    assert discovered["status"] == "partial" and len(discovered["data"]["records"]) == 1, discovered
    preview = await call("import_preview", {"result": discovered})
    assert preview["data"]["persisted"] is False
    imported = await call("import_bundle", {"result": discovered, "persist": True})
    assert imported["data"]["persisted"] and imported["status"] == "partial"
    searched = await call("search", {"query": {"terms": ["Council"]}})
    assert len(searched["data"]["hits"]) == 1
    exported = await call("export", {"bundle": imported["data"]["bundle"], "format": "zip"})
    assert base64.b64decode(exported["data"]["content_base64"]).startswith(b"PK")
    streamed = await call("export", {"bundle": imported["data"]["bundle"], "format": "zip", "stream": True})
    resource = await client.read_resource(f"civic-artifact://{streamed['data']['artifact_id']}/0")
    chunk = json.loads(resource.contents[0].text)
    assert base64.b64decode(chunk["content_base64"]).startswith(b"PK")
    planned = await call("plan_write", create_request())
    assert planned["status"] == "completed", planned
    approval = {k: planned["data"][k] for k in ("plan_id", "plan_hash")}
    tampered = await call("commit_write", {**approval, "plan_hash": "0" * 64})
    assert tampered["status"] == "failed"
    committed = await call("commit_write", approval)
    assert committed["status"] == "completed", committed
    assert committed["data"]["mock"] and committed["data"]["live_acceptance"] == "NOT_RUN"
    assert committed["data"]["items"][0]["readback"]["EventBodyId"] == 4
    receipt = await call("receipt", {"plan_id": approval["plan_id"]})
    assert receipt["data"] == committed["data"]
    duplicate = await call("commit_write", approval)
    assert duplicate["data"] == committed["data"]
    return approval


@pytest.mark.parametrize("mode,version", [("auto", "2026-07-28"), ("legacy", "2025-11-25")])
def test_stdio_official_client_version_parity_writes_and_stdout(tmp_path, mode, version):
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(SERVER), "--stdio", "--database", str(tmp_path / "stdio.sqlite")])
    async def run():
        async with Client(params, mode=mode, read_timeout_seconds=10) as client:
            assert client.protocol_version == version
            await sequence(client)
    anyio.run(run)


@pytest.fixture
def running_http(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, str(SERVER), "--port", str(port),
                                "--database", str(tmp_path / "mcp-http.sqlite")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/v1/info", headers={"Authorization": "Bearer " + TOKEN}, timeout=.2).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(.05)
        else:
            pytest.fail("MCP fixture service did not start.")
        yield url
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert not stdout, stdout.decode(errors="replace")


@pytest.mark.parametrize("mode,version", [("auto", "2026-07-28"), ("legacy", "2025-11-25")])
def test_http_official_client_version_parity_write_and_oauth_metadata(running_http, mode, version):
    url = running_http
    async def run():
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + TOKEN}) as http:
            transport = streamable_http_client(url + "/mcp", http_client=http)
            async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                assert client.protocol_version == version
                return await sequence(client)
    approval = anyio.run(run)
    hidden = httpx.post(url + "/v1/operations/receipt", json={"plan_id": approval["plan_id"]},
                        headers={"Authorization": "Bearer " + TOKEN_B})
    assert hidden.json()["status"] == "failed"
    unauth = httpx.post(url + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert unauth.status_code == 401
    assert "resource_metadata" in unauth.headers["www-authenticate"]
    metadata = httpx.get(url + "/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["resource"] == url + "/mcp"
    assert metadata["authorization_servers"] == ["https://auth.example"]


def test_http_rejects_unsupported_version_header_mismatch_and_origin(running_http):
    url = running_http
    headers = {"Authorization": "Bearer " + TOKEN,
               "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "1900-01-01"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    result = httpx.post(url + "/mcp", headers=headers, json=body)
    assert result.status_code == 400
    headers["MCP-Protocol-Version"] = "2026-07-28"
    body["params"]["_meta"] = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
                              "io.modelcontextprotocol/clientCapabilities": {}}
    headers["Mcp-Method"] = "tools/call"
    mismatch = httpx.post(url + "/mcp", headers=headers, json=body)
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == -32020
    bad_origin = httpx.post(url + "/mcp", headers={**headers, "Origin": "https://evil.example"}, json=body)
    assert bad_origin.status_code == 403


@pytest.mark.parametrize("transport,mode", [("stdio", "auto"), ("stdio", "legacy"),
                                           ("http", "auto"), ("http", "legacy")])
def test_protocol_cancellation_stops_engine_work(tmp_path, running_http, transport, mode):
    async def check(client, status):
        started = anyio.Event()
        operation_id = None

        async def progress(value, total, message):
            nonlocal operation_id
            operation_id = message.split("operation_id=")[-1]
            started.set()

        async def invoke():
            await client.call_tool("discover", {"request": {"fixture_slow": True}}, progress_callback=progress)

        async with anyio.create_task_group() as group:
            group.start_soon(invoke)
            with anyio.fail_after(5):
                await started.wait()
            group.cancel_scope.cancel()
        assert operation_id is not None
        # The cancelled call's worker must stop, and its durable result must become cancelled.
        with anyio.fail_after(5):
            while True:
                result = await status(operation_id)
                if result.get("result", {}).get("status") == "cancelled":
                    assert result["result"]["data"]["completed"] < 1000
                    break
                await anyio.sleep(.01)

    async def run():
        if transport == "stdio":
            database = tmp_path / "cancel-stdio.sqlite"
            params = StdioServerParameters(command=sys.executable,
                args=[str(SERVER), "--stdio", "--database", str(database)])
            async with Client(params, mode=mode) as client:
                async def status(operation_id):
                    from civic_data_connectors.storage import SQLiteStorage
                    item = SQLiteStorage(database).get("operations", operation_id,
                                                       scope=principal("mcp-stdio").context().scope)
                    return item.value if item else {}
                await check(client, status)
        else:
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + TOKEN}) as http:
                async with Client(streamable_http_client(running_http + "/mcp", http_client=http), mode=mode) as client:
                    async def status(operation_id):
                        result = await anyio.to_thread.run_sync(lambda: httpx.post(
                            running_http + "/v1/operations/status", json={"operation_id": operation_id},
                            headers={"Authorization": "Bearer " + TOKEN}).json())
                        return result.get("data", {})
                    await check(client, status)
    anyio.run(run)


def test_cli_mock_exact_plan_commit_receipt_same_core_contract(tmp_path):
    owner = engine(tmp_path / "cli-writes.sqlite")
    cfg = tmp_path / "principal.json"
    from dataclasses import asdict
    identity = asdict(principal("cli"))
    identity["operations"] = sorted(identity["operations"])
    identity["authorization"] = sorted(identity["authorization"])
    cfg.write_text(json.dumps({"principal": identity}), encoding="utf-8")
    def call(operation, request):
        out = io.StringIO()
        code = main([operation, "--config", str(cfg)], stdin=io.StringIO(json.dumps(request)),
                    stdout=out, stderr=io.StringIO(), engine=owner)
        result = json.loads(out.getvalue())
        assert code == 0, result
        return result
    planned = call("plan_write", create_request())
    approval = {k: planned["data"][k] for k in ("plan_id", "plan_hash")}
    committed = call("commit_write", approval)
    assert committed["data"]["mock"]
    assert call("receipt", {"plan_id": approval["plan_id"]})["data"] == committed["data"]


def test_node_mock_exact_plan_commit_receipt(running_http):
    import os
    module = (Path(__file__).resolve().parents[1] / "client" / "dist" / "index.js").as_uri()
    script = """
import assert from 'node:assert/strict';
const {CivicConnectorClient} = await import(process.env.CIVIC_MODULE);
const client = new CivicConnectorClient({baseUrl:process.env.CIVIC_URL,token:process.env.CIVIC_TOKEN});
const planned = await client.execute('plan_write',JSON.parse(process.env.CIVIC_WRITE));
assert.equal(planned.status,'completed'); assert.equal(planned.data.plan.mock,true);
const approval = {plan_id:planned.data.plan_id,plan_hash:planned.data.plan_hash};
const committed = await client.execute('commit_write',approval); assert.equal(committed.status,'completed');
assert.equal(committed.data.items[0].readback.EventBodyId,4); assert.equal(committed.data.mock,true);
const receipt = await client.execute('receipt',{plan_id:approval.plan_id});
assert.deepEqual(receipt.data,committed.data);
const denied = await client.execute('commit_write',{...approval,plan_hash:'0'.repeat(64)});
assert.equal(denied.status,'failed');
console.log(JSON.stringify({status:'PASS',live_acceptance:'NOT_RUN'}));
"""
    result = subprocess.run(["node", "--input-type=module"], input=script, text=True, capture_output=True,
        env={**os.environ, "CIVIC_MODULE": module, "CIVIC_URL": running_http, "CIVIC_TOKEN": TOKEN,
             "CIVIC_WRITE": json.dumps(create_request())}, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
