# Python SDK

Install the QuorumRelay candidate wheel (`quorumrelay==0.1.0.dev3`) into a Python 3.11+ environment. The canonical import and CLI are `quorumrelay`; existing `civic_data_connectors` imports and the `civic-data-connectors` CLI remain compatible and use the same implementation objects. No reference application, HTTP server, model, hosted service, or database is required.

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

## Fetch one known record

```python
source = Source("legistar", "https://webapi.legistar.com/v1/olympia")
detail = engine.fetch_record(source, "7011", bounds=Bounds(deadline_seconds=15))
# Equivalently: engine.execute("fetch", {"source": source.public_dict(), "external_id": "7011"})
```

The evidenced Legistar detail route requests supplied agenda items, agenda/minutes notes and attachment metadata. It preserves the exact response bytes and all original values. Linked item attachments become documents with explicit item relationships; downloading those files remains a separate captured-attachment operation. `legistar-event-json` replays a saved single-event response; `legistar-events-json` remains the listing-array format. `providers` reports additive formats separately from the 34 historical combinations.

One-event retrieval is bounded to that identity and does not claim full catalog coverage. An unimplemented provider detail mapping reports that gap explicitly. Credentials use trusted `OperationContext.credentials["legistar_token"]` when required; source URLs and returned captures do not contain that token.

Legistar vote and roll-call writes use `entity="vote"` / `entity="roll_call"`, `operation="create"` / `"update"`, and `parent_id` for the event item. Each requires an explicitly authorized `meeting_id` relationship. Native `VotePersonId`/`VoteValueId` or `RollCallPersonId`/`RollCallValueId` are required when creating, with matching parent identifiers bound into the exact plan. Provider enum values, tenant access and live write readback acceptance remain access-dependent; synthetic adapter checks do not establish these outcomes.

Official detail contract: https://webapi.legistar.com/Help/Api/GET-v1-Client-Events-EventId_EventItems_AgendaNote_MinutesNote_EventItemAttachments

## Native search

```python
native = engine.execute("search", {
    "native": True,
    "source": {"provider": "wistia", "url": "https://api.wistia.com/modern/medias"},
    "query": {"terms": ["water"], "phrases": ["budget was approved"]},
}, context=OperationContext(credentials={"wistia_token": account_read_token}))
```

The Wistia adapter calls the documented `/modern/search` endpoint with media-only results. The provider chooses candidate matching semantics; QuorumRelay applies its exact local term/phrase rules to returned metadata and supplied transcript excerpts. Matches retain source timestamps. The response includes `data.bundle` for explicit preview/import. Provider limits (100 primary media plus up to 100 transcript-only matches, no pagination) and partial excerpt coverage remain explicit even below the cap. A video upload timestamp does not establish its meeting date. The account must permit this read route; missing/denied credentials produce a failure, never an empty success.

Other unregistered native search routes report an implementation gap. `native=false` performs the existing local capture search. Connector extensions can supply their own typed `native_search` hook. Wistia live account acceptance remains unrun without authorized credentials; see the capability inventory.


Legistar native search uses the same request shape with a configured Legistar source and explicit dates. It searches **EventBodyName metadata only**, using provider-side substring filters and exact local term/phrase checking on that field. It retains full original records but does not advertise searching agenda titles, document text or vote details. Coverage states the searched field and binds resumed pages to the exact source/query/scope.

Wistia `fetch_record` supports the configured authenticated `https://api.wistia.com/modern/medias` source, with `wistia_token` in the trusted context. It preserves supplied Media fields/assets and has no invented caption body. Use `engine.fetch_captions(source, "mediaHashedId", language="eng", context=context)` for one supplied time-coded language, or omit language for the visible supplied track list. Track IDs retain their parent recording identity and source version. Existing cue timestamps remain searchable. An empty delegated-token track list is partial visibility. These GETs never request diarization, transcription or translation generation. Saved replay formats are `wistia-media-detail-json` and `wistia-caption-json`; the old public `wistia-media-json` remains unchanged.

CHAMP event sources such as `https://play.champds.com/lakezurichil/event/164` retrieve their fixed public event JSON route. `fetch_record(source, "164")` returns the same baseline identity and supplied agenda/media metadata; discovery of one configured event is partial catalog coverage.

Tyler Calendar POST needs the API base observed in that exact tenant's public application, not a guessed host. For the checked Ector tenant, configure:

```json
{"provider":"tyler-meeting-manager",
 "url":"https://ectorcountyclerktxtmmapp.meetingmanager.tylerapp.com/46612prod/tylermm/calendar/",
 "options":{"calendar_api_base":"https://ectorcountyclerktxtmmapp.meetingmanager.tylerapp.com/tylermmcalendar46612prod/"}}
```

Discovery requires explicit inclusive dates. The engine uses a fixed POST endpoint/body, enforces the same tenant hostname, and binds configuration into checkpoints. The checked live response was empty; nonempty live rows and complete catalog/pagination acceptance remain unresolved. Saved calendar input still works. The maintained [core coverage map](ENGINE-COVERAGE.md) distinguishes implemented paths from remaining research, code and access requirements across all 31 families.
