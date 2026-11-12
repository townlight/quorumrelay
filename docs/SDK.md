# Python SDK

Install the QuorumRelay candidate wheel (`quorumrelay==0.1.0.dev4`) into a Python 3.11+ environment. The canonical import and CLI are `quorumrelay`; existing `civic_data_connectors` imports and the `civic-data-connectors` CLI remain compatible and use the same implementation objects. No reference application, HTTP server, model, hosted service, or database is required.

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


## Related Legistar records and Repository folder reads

```python
# A supplied EventItem parent is mandatory; no tally or attendance is inferred.
rows = engine.fetch_related(legistar_source, "102964", "vote", bounds=Bounds(max_records=20))
row = engine.fetch_related(legistar_source, "102964", "vote", external_id="30763")
# record_type="roll_call" uses the separate supplied RollCalls route.
```

Related collections return `data.records` and exact per-page `data.bundles`; one detail returns its capture bundle. ID-keyset checkpoints bind source, parent, entity and caller scope. Collection completeness refers only to the selected EventItem, with no snapshot guarantee across pages. Original person/value/result/row-version fields are preserved, and the agenda-item parent remains explicit. Saved replay formats are `legistar-votes-json` and `legistar-rollcalls-json`. The public Olympia receipt records seven supplied votes and seven attendance rows over three pages each; it does not establish live write acceptance.

```python
repository = Source("laserfiche-weblink",
    "https://api.laserfiche.com/repository/v2/Repositories/r-city/Entries/54/Folder/Children")
children = engine.discover(repository, bounds=Bounds(max_pages=5, max_records=100),
    context=OperationContext(credentials={"laserfiche_token": repository_read_token}))
```

This distinct account API path requires `repository.Read` and an explicitly configured repository/folder URL. It lists direct children only and follows provider-issued same-folder OData nextLinks under byte/page/record/deadline bounds. No public WebLink-to-repository account relationship is guessed. Document, folder and shortcut IDs are repository-wide; current parent folder is a relationship so moving an entry does not change its identity. Creation/modification times and supplied fields remain metadata, never inferred meeting dates. File content, subtype expansion and recursive traversal are not requested by this operation. The saved format is `laserfiche-repository-entries-json`. Canonical account namespaces are `//api.laserfiche.com/repository/v2/Repositories/{repositoryId}`; writes route the repository separately while enforcing the exact configured namespace/credential grant, and retain explicit legacy write-only repository slug configurations. Public WebLink identities are unchanged. No authorized Repository account token has been supplied, so live account acceptance remains unrun.

Official read contracts: [Legistar Votes](https://webapi.legistar.com/Help/Api/GET-v1-Client-EventItems-EventItemId-Votes), [Legistar RollCalls](https://webapi.legistar.com/Help/Api/GET-v1-Client-EventItems-EventItemId-RollCalls), [Laserfiche folder contents](https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_get-folder-listing/).


## CivicPlus Select historical file preparation

```python
prepared = engine.execute("export", {
    "provider_specific": True,
    "source": {"provider": "civicplus-select", "url": "https://city.portal.civicclerk.com"},
    "format": "civicplus-historical-files", "stream": True,
    "meeting": {"body": "City Council", "meeting_type": "Regular Meeting", "meeting_date": "2020-12-18"},
    "files": [{"file_type": "Agenda Packet", "file_handle": uploaded_pdf_handle}],
}, context=export_context)
```

The caller must hold `export`, `export_attachments` and the exact configured source namespace grant. Scoped generic input handles retain current expiry/policy/integrity checks; small inline files can use `content_base64` and `content_type`. `stream:true` returns the usual scoped `artifact_id`; inline output returns `content_base64`. Caller byte/deadline limits apply. The historical import guide does not establish a vendor file-size limit.

The portable ZIP contains named original PDFs plus a hash/loss manifest. Extract the named files for the documented consultant intake: ZIP itself is not an established vendor input. Literal mapped FileType values are `Agenda`, `Agenda Packet` and `Minutes`, from official examples such as `City Council_Regular Meeting_Agenda Packet_12_18_2020.pdf`. Body/type/date must be explicit; path characters, underscore delimiters, duplicate tokens/bytes and filename collisions are rejected without silent renaming. PDF structure is parsed before export. Meeting fields without a filename mapping are retained in the manifest and disclosed as projection losses; agenda item structure/bookmarks, captions, media timestamps, votes and source revisions are not reconstructed by this import workflow.

`Packet`, `Notice`, `Notices`, `Other`, `Media` and `Audio/Video` lack an unambiguous verified filename token in the inspected guide. Those requests return `provider_filename_mapping_unverified` and no files, rather than inventing a usable provider filename. MP4 preparation therefore remains incomplete until its exact filename token is verified. The vendor permits at most five PDFs and one media file per event, but only the three evidenced PDF token mappings are currently prepared. Consultant processing, FTP hostname/credentials and live vendor import acceptance remain unresolved. No FTP action is performed. See the [official historical import guide](https://www.civicplus.help/meetings-select/docs/historical-imports).


## Observed NovusAGENDA public listing

```python
source = Source("novusagenda", "https://ebps.novusagenda.com/agendapublic/")
page = engine.discover(source, bounds=Bounds(max_records=25, max_pages=2,
    date_from="2026-10-01", date_to="2026-10-31"))
# Resume with the same engine, source, caller and filters; record/page bounds may change.
next_page = engine.discover(source, bounds=Bounds(max_records=25, max_pages=2,
    date_from="2026-10-01", date_to="2026-10-31", checkpoint=page.coverage["checkpoint"]))
```

The adapter reads the public `/agendapublic/` form and follows only its current validated Next Page controls. It retains a fresh anonymous cookie jar and form controls privately; no staff or search form action is submitted. Explicit date and record-type filters apply locally to displayed rows. A supplied body filter cannot infer a board from the tenant or meeting type: unmapped bodies remain in `unknown_body_records` with partial coverage.

Continuation tokens are opaque and bind the exact caller/source/date/type selection. They expire after 15 minutes and work only in the current engine process; a restart explicitly invalidates them. Exact page bytes are interned across cursor snapshots under a 32 MiB accounted cache budget, so one-record traversal does not hit an arbitrary 32-cursor cap. Active other-caller cursors are not silently evicted. Capacity failures explicitly report that continuation is unavailable; expiry/restart requires a fresh read. This is a changing public listing, not a snapshot transaction.

Meeting and agenda-item pager counters remain separate. Item paging does not create new derived meeting identities. Supplied ItemID/MeetingID links retain their parent relationships; rows without a provider ID use a page/row/field-derived ID whose stability limitation is explicit. Exact full HTML captures—including public hidden controls—remain intact, while anonymous cookies and separate session state are never exposed in errors or tokens.

`novus-public-listing-html` is an additive saved-page format. The existing `meeting-export` parser remains the default for saved Novus meeting exports and is unchanged. One bounded public engine read of the existing East Brunswick tenant returned 180 agenda rows and 11 meeting rows over 12 pages without errors. Status remains partial: exhausting that displayed window proves neither complete archive coverage nor native search/detail semantics. See `docs/verification/novus-public-discovery-2026-11-11.json`.


## Essential and TelVue account API reads (post-dev3 source)

`engine.fetch(source, request, context=context)` routes these account APIs only from the documented fixed origins. Essential (`municode-meetings`) uses `https://meetingsgov.devmunicode.com`; production hosts and token issuance are not inferred. TelVue uses `https://connect.telvue.com`. Both require an explicit application-owned `Source.namespace`, plus trusted `context.credentials[provider]` binding `origin`, `tenant == context.tenant`, and exact `namespace` (or an explicit `allowed_namespaces` list). The current caller operation/namespace policy still applies. Saved additive format replay retains that namespace without needing account credentials.

Essential credentials use `token`. Its request uses `api_resource: meeting|item|multimedia` with supplied `external_id`, or `api_resource: collection`, an explicit nonnegative `offset`, and the exact documented `filters` object (`Words`, `CreatedMeetingFromDate`, `CreatedMeetingToDate`, `ArchivedState`, `MeetingTypeIds`). No offset stride, automatic paging, response envelope, or exact text-search semantics is guessed. Meeting/item/collection responses return exact raw captures with partial schema coverage and zero inferred normalized rows. Multimedia uses the documented `meetingStructure` wrapper and additive `essential-multimedia-json` replay format. Timestamp integers remain supplied values; no undocumented units are assigned.

TelVue credentials use `access_key` and `secret_passphrase`, sent as the documented CONNECT-ACCESS-KEY and CONNECT-SECRET-PASSPHRASE headers over verified TLS. Request `api_resource: media|videos|playlists`; only media/playlists accept an optional decimal `external_id`. The `.json` list/detail routes preserve the documented envelopes, provider IDs, transcript text, chapters, sources and unknown fields. HTTP(S) media sources can become recording relationships; RTMP values stay in original data. Upload/creation timestamps are not meeting dates. Additive replay formats are `telvue-connect-media-json`, `telvue-connect-videos-json`, and `telvue-connect-playlists-json`.

All account reads remain partial coverage: list pagination/end conditions and account visibility are unverified. Caller byte, deadline, maximum-record and cancellation bounds apply; unsupported date/body filters and forged checkpoints fail explicitly. Account responses that echo configured credential material cannot be captured. No token service or live account mutation was called during fixture verification.
