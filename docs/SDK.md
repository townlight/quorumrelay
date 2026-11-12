# Python SDK

Install the QuorumRelay candidate wheel (`quorumrelay==0.1.0.dev2`) into a Python 3.11+ environment. The canonical import and CLI are `quorumrelay`; existing `civic_data_connectors` imports and the `civic-data-connectors` CLI remain compatible and use the same implementation objects. No reference application, HTTP server, model, hosted service, or database is required.

```python
from quorumrelay import Bounds, OperationContext, Query, Source, create_engine

engine = create_engine()
source = Source("escribe", "https://example.org/Meetings.aspx",
                input_format="escribe-calendar-json")
preview = engine.normalize(source, saved_calendar_bytes,
                           input_format=source.input_format)
# Always retain the complete result, including partial/errors/coverage.
assert preview.status in {"completed", "partial"}
```

Normalization and import preview never persist. The caller decides whether to save:

```python
from quorumrelay.storage import SQLiteStorage

store = SQLiteStorage("caller-owned-captures.sqlite3")
engine = create_engine(storage=store)
context = OperationContext(principal="producer", client_id="my-app",
                           tenant="city-configuration-42",
                           allowed_namespaces=frozenset({preview.data["source"]["namespace"]}))
saved = engine.execute("import_bundle", {"result": preview.public_dict(), "persist": True}, context=context)
hits = engine.search(Query(terms=("council",), limit=20), context=context)
```

Use the same principal/client/tenant for a state's lifetime. The consumer owns store startup/shutdown, backups, retention and pinned package version. Its own database may implement `Storage`; see the atomic versioned contract in `ENGINE-CONTRACT.md` and the storage guide. A source namespace is not the application's newsroom/city/profile ID.

Discover only explicitly configured, evidenced sources and bounded dates:

```python
result = engine.discover(source, bounds=Bounds(date_from="2026-11-01",
                                               date_to="2026-11-30",
                                               max_pages=10, max_records=500),
                         context=context)
```

Both end dates are inclusive. A connector may require account credentials, explicit API client configuration, saved captures or a guarded browser session. Check capability status and returned coverage. Lack of access does not mean the vendor lacks a feature.

Fetch a captured document, never an arbitrary user-provided URL:

```python
record = preview.data["records"][0]
document = engine.fetch_attachment(source, record, index=0, context=context)
# Without persistent storage, provide capture=saved_calendar_bytes instead.
```

This helper uses the source identity and captured document index, plus scoped storage or an original capture. It preserves durable citations independently of signed download URLs. Check the full result for unavailable or unreadable content. Parser and transfer bounds are separate; the default transfer cap is 200 MiB.

Export/import/search and write requests also use `engine.execute(operation, request, context=...)`. The transports and SDK share the same result/error contract. Writes require durable atomic storage, explicit `write:plan`/commit policy grants, server-side credentials, supported mappings and exact authorized plan approval. Importing a capture never writes upstream.

For backward-compatible application imports:

```python
from quorumrelay.legacy import legacy_previews

legacy = legacy_previews(result)  # Original saved-reader pages, selected records only.
brand_new = legacy_previews(native_api_result, new_source=True)
```

Only mark a source new when the application has checked its existing import/configuration ledger. Existing portal/API transitions require an evidenced `LegacyIdentityMapping`; do not guess old export IDs equal live API IDs or infer aliases from similar hostnames.

Typed `from_dict`/`public_dict` helpers preserve unknown schema fields. Exact original bytes, supplied fields, false/null/zero/empty values, relationships and source revision metadata remain separate from normalized projections. The optional store does not own canonical application records or change-resolution decisions.
