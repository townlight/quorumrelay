"""An unrelated Python application using only public installed-package APIs.

Example: python sdk_saved_capture.py --provider escribe --format escribe-calendar-json
  --source https://tenant.example/Meetings.aspx --capture saved.json --database app-state.sqlite3
"""

import argparse
import json
from pathlib import Path

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--format", required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args(argv)
    store = SQLiteStorage(args.database) if args.database else None
    engine = create_engine(storage=store)
    source = Source(args.provider, args.source, input_format=args.format)
    with args.capture.open("rb") as stream:
        content = stream.read(Bounds().parser_bytes + 1)
    preview = engine.normalize(source, content, input_format=args.format)
    if preview.status not in {"completed", "partial"}:
        print(json.dumps(preview.public_dict()))
        return 1
    context = OperationContext(principal="external-developer", client_id="python-sdk-example",
                               tenant="example-owned-state",
                               allowed_namespaces=frozenset({preview.data["source"]["namespace"]}))
    imported = engine.execute("import_bundle", {
        "result": preview.public_dict(), "persist": store is not None,
    }, context=context)
    searched = engine.execute("search", {"bundle": preview.data, "query": {"limit": 5}}, context=context)
    exported = engine.execute("export", {"bundle": preview.data, "format": "zip"}, context=context)
    print(json.dumps({
        "normalize": preview.status, "import": imported.status, "search": searched.status,
        "export": exported.status, "records": len(preview.data["records"]),
        "hits": len(searched.data.get("hits", [])) if searched.data else 0,
        "persisted": imported.data.get("persisted", False) if imported.data else False,
        "coverage": {key: searched.coverage.get(key) for key in
                     ("scope", "truncated", "searched_records", "incomplete_text", "failures")},
    }))
    return int(any(r.status in {"failed", "unsupported"} for r in (imported, searched, exported)))


if __name__ == "__main__":
    raise SystemExit(main())
