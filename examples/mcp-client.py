"""Official SDK client example, explicitly modern or legacy, with synthetic-only write workflow."""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import anyio
import httpx2
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from mock_workflow import DISCOVER, TOKEN, WRITE


async def workflow(client):
    async def call(name, request):
        value = await client.call_tool(name, {"request": request})
        result = value.structured_content
        assert result["status"] in {"completed", "partial"}, result
        return result
    discovered = await call("discover", DISCOVER)
    preview = await call("import_preview", {"result": discovered})
    imported = await call("import_bundle", {"result": discovered, "persist": True})
    search = await call("search", {"query": {"terms": ["Council"]}})
    exported = await call("export", {"bundle": imported["data"]["bundle"], "format": "zip", "stream": True})
    artifact_id, offset, chunks = exported["data"]["artifact_id"], 0, []
    while offset is not None:
        result = await client.read_resource(f"civic-artifact://{artifact_id}/{offset}")
        chunk = json.loads(result.contents[0].text)
        chunks.append(base64.b64decode(chunk["content_base64"]))
        offset = chunk["next_offset"]
    assert b"".join(chunks).startswith(b"PK")
    planned = await call("plan_write", WRITE)
    assert planned["data"]["plan"]["mock"] is True, "This example refuses to commit a non-mock plan."
    approval = {key: planned["data"][key] for key in ("plan_id", "plan_hash")}
    committed = await call("commit_write", approval)
    assert committed["data"]["mock"] is True
    assert committed["data"]["live_acceptance"] == "NOT_RUN"
    receipt = await call("receipt", {"plan_id": approval["plan_id"]})
    assert receipt["data"] == committed["data"]
    print(json.dumps({"protocol": client.protocol_version, "live_acceptance": "NOT_RUN",
                      "preview_persisted": preview["data"]["persisted"], "hits": len(search["data"]["hits"]),
                      "mock_receipt": receipt["data"]["mock"]}))


async def run(args):
    if args.transport == "stdio":
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name("mock_workflow.py")), "stdio", "--database", args.database])
        async with Client(params, mode=args.mode) as client:
            await workflow(client)
    else:
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + os.environ.get("CIVIC_CONNECTOR_TOKEN", TOKEN)}) as http:
            async with Client(streamable_http_client(args.url.rstrip("/") + "/mcp", http_client=http),
                              mode=args.mode) as client:
                await workflow(client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("transport", choices=("stdio", "http"))
    parser.add_argument("--database", default="synthetic-mcp-example.sqlite")
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--mode", choices=("auto", "legacy"), default="auto")
    anyio.run(run, parser.parse_args())
