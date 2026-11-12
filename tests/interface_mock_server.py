"""Synthetic-only server fixture. Real adapters run; the injected upstream never opens a socket."""

import argparse
import time

from civic_data_connectors import Engine, imports, interchange, providers, search, storage, writes
from civic_data_connectors.models import OperationResult
from civic_data_connectors.transports.http import create_app
from civic_data_connectors.transports.mcp import run_stdio
from civic_data_connectors.transports.runtime import OPERATIONS, Principal, ServiceConfig
from civic_data_connectors.write_adapters import default_adapters
from test_writes import LegistarNetwork

TOKEN = "synthetic-mcp-client-a-token-only"
TOKEN_B = "synthetic-mcp-client-b-token-only"


def engine(path):
    owner = Engine(storage=storage.SQLiteStorage(path))
    for module in (providers, imports, interchange, search, storage):
        module.register(owner)
    writes.register(owner, default_adapters(LegistarNetwork()))
    original = owner.handlers["discover"]

    def discover(owner, request, content, context):
        if not request.pop("fixture_slow", False):
            return original(owner, request, content, context)
        for i in range(1000):
            if context.check_cancelled():
                return OperationResult("cancelled", data={"completed": i})
            context.report(completed=i, total=1000)
            time.sleep(.01)
        return OperationResult("completed")
    owner.handlers["discover"] = discover
    return owner


def principal(client_id="fixture"):
    return Principal(principal="synthetic-actor", client_id=client_id, tenant="fixture-city",
                     operations=frozenset(OPERATIONS), authorization=frozenset({"write:plan", "write:commit"}),
                     credentials={"legistar": {"namespace": "fixture-city", "token": "synthetic-secret",
                                               "permissions": ["event:create", "event:update"]}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    owner = engine(args.database)
    if args.stdio:
        run_stdio(owner, principal("mcp-stdio"))
    else:
        import uvicorn
        cfg = ServiceConfig(port=args.port, mcp=True,
                            public_url=f"http://127.0.0.1:{args.port}", issuer_url="https://auth.example",
                            tokens={TOKEN: principal(), TOKEN_B: principal("another-client")})
        uvicorn.run(create_app(owner, cfg), host="127.0.0.1", port=args.port,
                    access_log=False, log_level="warning")
