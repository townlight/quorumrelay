"""Executable synthetic workflow and servers. The upstream fixture never opens a socket."""

from __future__ import annotations

import argparse
import base64
import json
from urllib.parse import parse_qs, urlsplit

from quorumrelay import create_engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.transports.http import create_app
from quorumrelay.transports.mcp import run_stdio
from quorumrelay.transports.runtime import OPERATIONS, Principal, ServiceConfig
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse

TOKEN = "synthetic-demo-token-never-for-deployment"
CAPTURE = [{"EventId": 7, "EventBodyName": "Council", "EventDate": "2026-11-11T00:00:00",
            "EventTime": "7:00 PM", "EventComment": "Parks budget", "EventRowVersion": "r7",
            "unknown": [None, False, 0, "", {"non_ascii": "café"}]}]
DISCOVER = {"source": {"provider": "legistar", "url": "https://mock-city.legistar.com/Calendar.aspx",
                       "input_format": "legistar-events-json"},
            "bounds": {"date_from": "2026-11-11", "date_to": "2026-11-11"},
            "content_base64": base64.b64encode(json.dumps(CAPTURE).encode()).decode()}
WRITE = {"source": {"provider": "legistar", "url": "https://webapi.legistar.com/v1/mock-city/events",
                    "namespace": "mock-city"},
         "changes": [{"key": "synthetic-1", "entity": "event", "operation": "create",
                      "fields": {"EventDate": "2026-11-11T00:00:00", "EventBodyId": 4}}]}


class SyntheticUpstream:
    """Tiny response fixture, not a provider implementation or acceptance environment."""

    mock = True

    def __init__(self):
        self.records = {}

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        if parsed.hostname != "webapi.legistar.com":
            raise AssertionError("Synthetic fixture refuses every other origin.")
        if method == "POST":
            row = {**json.loads(body), "EventId": 100 + len(self.records), "EventRowVersion": "AQ=="}
            self.records[str(row["EventId"])] = row
            return WriteResponse(200, json.dumps(row).encode())
        if method == "GET":
            if "$filter" in parse_qs(parsed.query):
                return WriteResponse(200, json.dumps(list(self.records.values())).encode())
            row = self.records[parsed.path.rsplit("/", 1)[-1]]
            return WriteResponse(200, json.dumps(row).encode())
        return WriteResponse(405)


def demo_principal():
    return Principal(principal="synthetic-editor", client_id="independent-example", tenant="synthetic-city",
        operations=frozenset(OPERATIONS), authorization=frozenset({"write:plan", "write:commit"}),
        credentials={"legistar": {"namespace": "mock-city", "token": "synthetic-upstream-not-a-service-token",
                                  "permissions": ["event:create", "event:update"]}})


def workflow(engine):
    context = demo_principal().context()
    def call(operation, request):
        result = engine.execute(operation, request, context=context)
        assert result.status in {"completed", "partial"}, result.public_dict()
        return result
    discovered = call("discover", DISCOVER)
    preview = call("import_preview", {"result": discovered.public_dict()})
    imported = call("import_bundle", {"result": discovered.public_dict(), "persist": True})
    found = call("search", {"query": {"terms": ["Council"]}})
    assert not preview.data["persisted"] and imported.data["persisted"]
    assert len(discovered.data["records"]) == 1 and len(found.data["hits"]) >= 1
    exported = call("export", {"bundle": imported.data["bundle"], "format": "zip", "stream": True})
    planned = call("plan_write", WRITE)
    assert planned.data["plan"]["mock"] is True
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    committed = call("commit_write", approval)
    receipt = call("receipt", {"plan_id": approval["plan_id"]})
    assert committed.data == receipt.data
    print(json.dumps({"mode": "synthetic", "live_acceptance": "NOT_RUN",
                      "discover_status": discovered.status, "persisted": imported.data["persisted"],
                      "hits": len(found.data["hits"]), "artifact_id": exported.data["artifact_id"],
                      "receipt_mock": committed.data["mock"], "preview_persisted": preview.data["persisted"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("python", "serve", "stdio"))
    parser.add_argument("--database", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    engine = create_engine(storage=SQLiteStorage(args.database),
                           write_adapters=default_adapters(SyntheticUpstream()))
    if args.mode == "python":
        workflow(engine)
    elif args.mode == "stdio":
        run_stdio(engine, demo_principal())
    else:
        import uvicorn
        config = ServiceConfig(port=args.port, mcp=True,
            public_url=f"http://127.0.0.1:{args.port}", issuer_url="https://auth.example",
            tokens={TOKEN: demo_principal()})
        uvicorn.run(create_app(engine, config), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
