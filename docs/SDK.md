# Python SDK

Install the approved source checkout with `python -m pip install -e .` into a Python 3.11+ environment. The integrated source reports `quorumrelay==0.1.0.dev13`; its matching wheel is built locally but unpublished. The preserved hash-verified dev11 wheel predates the reader integration. The canonical import and CLI are `quorumrelay`; existing `civic_data_connectors` imports and the `civic-data-connectors` CLI remain compatible and use the same implementation objects. No reference application, HTTP server, model, hosted service, or database is required.

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

For a recording that supplies a direct `video_url`, `audio_url` or `playback_url`, select that captured field with `kind="recordings", url_field="video_url"`. The default `url_field="url"` preserves existing behavior, which may retrieve a player HTML page. A selected HLS URL returns the manifest only; it does not download its segments or establish playable-video acceptance. External media origins still require explicit `source.options.download_origins`. HTTP/CLI/MCP/TypeScript use the same `fetch` request attachment object: `{"record_key":"…","index":0,"kind":"recordings","url_field":"video_url"}`. The selector accepts only these known fields already present on the authorized captured record; it accepts no caller-supplied media URL.

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

Legistar vote and roll-call writes use `entity="vote"` / `entity="roll_call"`, `operation="create"` / `"update"`, and `parent_id` for the event item. Each requires an explicitly authorized `meeting_id` relationship. Native `VotePersonId`/`VoteValueId` or `RollCallPersonId`/`RollCallValueId` are required when creating, with matching parent identifiers bound into the exact plan. Callers supply applicable native ValueIds and tenant grants; undocumented enum meanings and RowVersion conflict behavior remain qualified. Documented synthetic execution is accepted verification under the owner amendment; live tenant mutation is optional supporting evidence.

Legistar `event` create/update also accepts the documented `EventMedia` and `EventVideoPath` string fields. A partial update of those fields preserves the existing required date and other documented event values in the native PUT body. This verifies exact JSON metadata values, not recording-byte upload, replacement, playback, or processing. The official [Event POST](https://webapi.legistar.com/Help/Api/POST-v1-Client-Events) and [Event PUT](https://webapi.legistar.com/Help/Api/PUT-v1-Client-Events-EventId) contracts do not define those recording-transfer semantics.

`matter_attachment` create/update can carry a hyperlink with `MatterAttachmentIsHyperlink=true`, `MatterAttachmentHyperlink` and an explicit `MatterAttachmentShowOnInternetPage` boolean. The hyperlink-only flow sends no binary and does not request `/File`. Readback verifies the supplied values, including the visibility flag; it does not establish effective public access. Separate binary attachment operations use base64 `MatterAttachmentBinary` JSON and the documented `/File` readback, retaining their existing evidence. The [field-level receipt](verification/legistar-media-link-writes-2026-11-13.json) covers exact approval, create/update, omitted-field preservation, receipt replay and persistent mismatches without duplicate creates. It does not establish file-to-link conversion or the historical vendor import package.

Official detail contract: https://webapi.legistar.com/Help/Api/GET-v1-Client-Events-EventId_EventItems_AgendaNote_MinutesNote_EventItemAttachments

OnBase Agenda Online supports a bounded selected-detail path from its configured
HTTPS root:

```python
onbase = Source("onbase", "https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/")
meeting = engine.fetch_record(onbase, "3825")
items = engine.fetch_related(onbase, "3825", "agenda_item")
item = engine.fetch_related(onbase, "3825", "agenda_item", external_id="88173")
section = engine.fetch_related(onbase, "3825", "agenda_section", external_id="54973")
```

`fetch_record` revalidates the native meeting ID against the current public
listing, then follows only its supplied `ViewMeeting?doctype=1` page and literal
accessible `ViewMeetingAgenda?type=agenda` route. It returns the native meeting,
agenda sections and agenda items. The selected listing metadata and recording
references/relationships remain on the meeting result, and its compatibility
meeting projection reflects that final record. `fetch_related` lists supplied sections/items;
selected item/section detail is fetched only after membership in the requested
record type and its exact declared `ViewMeetingAgendaItem` route are verified.
The route uses `isSection=false` for an item and `isSection=true` for a section.
The captured section response supplies a title only; it does not establish
section attachments or additional section content.
Native child IDs retain the meeting parent, and items retain a supplied parent
section relationship. Rendered text is partial, timezone remains unknown, and
supporting attachment IDs, publish IDs and links remain metadata locators; the
detail call itself does not fetch attachment bytes. Exact page captures and
citations are preserved.
Reads use cumulative byte, page and deadline bounds, cancellation checks and
same-origin exact-URL GETs with redirects disabled. Coverage remains partial.
Only the supplied Agenda variant and selected item/section detail are mapped;
archived meetings absent from the current listing,
native search and broader Agenda APIs remain unresolved. The three pinned public
detail-page GETs and scoped synthetic composition, persistence, search and ZIP
evidence are recorded in [the OnBase detail receipt](verification/onbase-detail-2026-11-13.json)
and [the pinned captures](capabilities/evidence/onbase-detail/source.json).
The separately captured section response and scoped synthetic verification are
recorded in [the section receipt](verification/onbase-section-detail-2026-11-13.json).

After persisting the selected agenda-item record in the engine's scoped storage,
retrieve its supplied supporting document with the separate attachment operation,
for example
`engine.fetch_attachment(onbase, item_record, index=0, context=context)`. This
path accepts the exact same-tenant item locator only when its meeting, item,
publish ID, Agenda document type and non-section attachment flags match both the
record and the captured wrapper. It checks the declared safe PDF filename,
performs the exact empty-body preparation POST and declared `ViewDocument` GET,
and validates the returned PDF type and magic bytes. Redirects are disabled;
cookies remain in call memory. The item wrapper and returned PDF are synthetic
in this verification: no real item wrapper/PDF response was captured, and no
live file availability or rendering is established. Section attachments and
packet branches remain unmapped. See the separate
[item-document receipt](verification/onbase-item-document-2026-11-13.json).

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

Laserfiche Repository v2 native search accepts the same `native=true` request
with an explicitly configured folder Children source and trusted
`OperationContext(credentials={"laserfiche_token": token})`. For example:

```python
result = engine.execute("search", {
    "native": True,
    "source": {"provider": "laserfiche-weblink",
        "url": "https://api.laserfiche.com/repository/v2/Repositories/REPOSITORY/Entries/54/Folder/Children"},
    "query": {"terms": ["park"], "phrases": ["funding was approved"]},
    "bounds": {"max_records": 100, "max_pages": 10}
}, context=context)
```

The provider supplies first-expression candidates within that folder's direct
children; all exact terms/phrases are then checked against returned metadata and
context excerpts. Results remain partial because excerpts are not whole-document
text. Inspect coverage for candidate/context truncation, failures and task cleanup.
Use the full `result` for explicit import to preserve records, page/context
captures and partial coverage. Metadata-only records remain available even when
context retrieval fails. Meeting date/body filters and task-resume checkpoints
are rejected; WebLink public sources do not imply Repository API access. Search
tasks are cleaned up within the call; there is no automatic background worker.

For assigned Repository metadata, set source option
`"repository_include_fields": true` on API-folder sources. Selected entry detail,
discovery and native-search candidates then read the documented `/Fields`
collection, preserving supplied multi-values rather than relying on a listing's
first-value projection. Inspect `coverage.field_metadata` and each record's
`extensions.repository_field_coverage`; missing/more values and bounded partial
reads remain explicit. Searchable values appear in
`normalized.repository_fields`, and raw supplementary captures survive explicit
import/export. This option performs no template administration or field writes.


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

For a selected child, `engine.fetch_record(repository, "71", context=...)` reads
`GET /repository/v2/Repositories/{repositoryId}/Entries/{entryId}` from the pinned
vendor SDK. Use the same trusted `repository.Read` token context shown above.
The response must identify entry 71 and parent folder 54; an entry moved elsewhere
requires an explicitly updated source folder. This returns metadata and an exact
capture, with `content_fetched: false`; it does not download the document or infer
a meeting date. The existing `laserfiche-repository-entries-json` parser replays
both children responses and single Entry responses offline. Namespace, caller,
response URL, token privacy and byte/deadline bounds remain enforced.

Use `engine.fetch_record(repository, "71", include_text=True, context=...)` to
also read existing supplied page text. The equivalent operation request contains
`"external_id":"71", "include_text":true` on SDK `fetch`, CLI, HTTP or MCP.
The flag requires a boolean and is explicitly unavailable for other providers.
The connector follows the documented page-info collection's same-document
nextLinks and GETs text only for pages advertising `hasText`. It never requests
OCR, text generation or transcription. `max_pages` limits document pages;
supplementary responses share a cumulative `min(parser_bytes, transfer_bytes)`
budget and the metadata request's original deadline. A bounded partial response
can be retried with a larger bound; this enrichment has no continuation cursor.

Page segments retain page numbers, supplied page IDs, citations and response
hashes. Raw page-info/text captures occupy the bundle's standard `captures`
collection, so scoped persistence and ZIP interchange preserve them. Missing
text, failed pages and truncation keep the result and subsequent local search
partial. Normalized change detection includes the page-text hash while the
document identity and provider-supplied revision remain distinct. The reads do
not form an atomic snapshot; `text_complete` describes the returned page
collection and supplied text, not every kind of content in the document.

For original electronic-document bytes, call `engine.fetch_attachment(repository,
document_record, capture=original_capture, context=...)`, or omit `capture` when
the record is persisted in the caller's scoped engine storage. This selects the
document itself at index zero. Configure `repository.options["download_origins"]`
with the exact HTTPS origins permitted for provider-issued downloads; a returned
URL does not automatically authorize a new origin. The connector rechecks the
entry's current parent, POSTs `{"part":"Edoc"}` to its documented `/Export`
route, and downloads the single-use link once without bearer headers or redirects.
Retries start a new export. The result contains bounded bytes as `content_base64`,
SHA-256, durable entry citation and fresh metadata revision/capture hash; the
signed link is never returned. Download failure retains the record as partial.
The default is original-file retrieval. To select another documented representation,
set `Source.options["repository_export_part"]` to `Image`, `Text` or `AlternateEdoc`.
Image export defaults to PDF; `repository_image_format` also accepts MultiPageTIFF,
SinglePageTIFF, PNG and JPEG. TIFF exports use the documented `AsStored` encoding.
Image annotations and image/text redactions remain included. AlternateEdoc requires
`repository_alternate_edoc_name`, using the vendor's restricted 1–15 character
name. Irrelevant or invalid options fail before network access. Results disclose
the exact `export_part` and `export_options`; files may be a vendor-created archive
for formats containing multiple files. No local conversion is performed. Text-file
export does not imply page-anchored extraction; use `include_text` for that path.
Set `repository_export_async: true` in source options for the documented
`/ExportAsync` task path. The default remains synchronous. The connector validates
the issued task ID/type and optional result entry ID, polls only that exact task,
then downloads its single-use `result.uri` through the same guarded transfer.
`max_pages` bounds task polls in this mode; `deadline_seconds` covers metadata,
start, polling, cleanup and download. Task responses share a bounded parser-byte
budget, with time and bytes reserved for cleanup. Increasing the deadline supports
longer exports without an unbounded background worker.

If polling stops early, the connector requests cancellation for its own task and
checks terminal status. It never submits a cancel-all request or changes document
content. `coverage.export_task` distinguishes cancellation requested/accepted from
terminal confirmation. A timeout can leave cleanup unconfirmed; the task ID and
next action are returned explicitly, while raw task errors and signed URLs remain
private. A retry starts a new export; no resumable task cursor is claimed. An
unconfirmed start is reported when no safe task reference was returned. Synthetic
verification is accepted; live account execution remains unobserved.

Official read contracts: [Legistar Votes](https://webapi.legistar.com/Help/Api/GET-v1-Client-EventItems-EventItemId-Votes), [Legistar RollCalls](https://webapi.legistar.com/Help/Api/GET-v1-Client-EventItems-EventItemId-RollCalls), [Laserfiche folder contents](https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_get-folder-listing/).


## Granicus native Clip search

For a configured HTTPS `ViewPublisher.php?view_id=<numeric>` source on a `*.granicus.com` host, `search` with `native: true` uses the observed same-origin `ViewSearchResults.php` Clip form. The provider receives the first supplied term or phrase as `allwords`; provider candidate semantics are not guaranteed. QuorumRelay applies exact local AND matching to supplied title/date metadata, with inclusive date filters. The observed numeric `pagenumber` route is bounded by page/record/deadline limits. Continuations bind source, query and caller scope and verify the page hash when resuming within a page; a changed page requires restarting. Search results remain partial and do not claim complete catalog, agenda or document text, transcripts, or other form categories. Source rows without a provider-issued clip ID are omitted and counted. See `outputs/granicus-followup-20261112/native-search-live.json` for the bounded Superior observation; other tenants and semantics remain unverified.

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

The portable ZIP contains named original PDFs and an optional MP4 plus a hash/loss manifest. Extract the named files for the documented consultant intake: ZIP itself is not an established vendor input. Literal mapped FileType values are `Agenda`, `Agenda Packet` and `Minutes`, from official examples such as `City Council_Regular Meeting_Agenda Packet_12_18_2020.pdf`. Body/type/date must be explicit; path characters, underscore delimiters, duplicate tokens/bytes and filename collisions are rejected without silent renaming. PDF structure is parsed before export. Meeting fields without a filename mapping are retained in the manifest and disclosed as projection losses; agenda item structure/bookmarks, captions, media timestamps, votes and source revisions are not reconstructed by this import workflow.

The supported canonical file types are `Agenda`, `Agenda Packet`, `Minutes`, `Notice`, `Other` and `Media`; only `Media` accepts MP4. The official help page embeds a [filename tester](https://civicplus-lruiz.github.io/Historical-Import-Tester/Tester.html). Its file-type classification examines the entire filename, so the exporter rejects generated names where body or meeting-type words cause a different tester classification. For example, a body containing “Agenda” can cause an MP4 to be classified as Agenda. The exporter checks bounded top-level MP4 box framing and required `ftyp`, `moov` and `mdat` boxes; that does not prove a playable file or codec compatibility. It preserves original bytes and records hashes. `Packet`, `Notices` and `Audio/Video` aliases remain unsupported; use the canonical names above. At most five PDFs and one MP4 may be prepared. The tester is preparation evidence, not proof of consultant processing or vendor import acceptance. The official instructions give conflicting FTP hosts; credentials and live vendor intake remain unresolved. No FTP action is performed. See the [official historical import guide](https://www.civicplus.help/meetings-select/docs/historical-imports).


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


## Bounded public native search

The dev7 source candidate adds the verified public search forms for PrimeGov, eSCRIBE, Swagit, SuiteOne, CivicPlus Select, AgendaCenter, AgendaQuick, Utah, iQM2 and ClerkBase. These adapters apply only to their evidenced source routes/tenants; `providers` and the capability inventory distinguish them from the preserved saved-input formats. They submit the first term or phrase to the provider, then apply exact local matching to the returned metadata and explicitly supplied excerpts. Provider ranking/candidate selection is separate from the local match and is not a full-text or catalog-completeness promise. Current PrimeGov source also declares the public client document branches below; search preserves locators without fetching their files. Authenticated Meeting API schemas remain unresolved.

```python
result = engine.execute("search", {
    "native": True, "source": configured_source.public_dict(),
    "query": {"terms": ["Council"], "limit": 20},
    "bounds": {"date_from": "2026-11-01", "date_to": "2026-11-30",
               "max_pages": 2, "max_records": 100},
}, context=context)
# Supply coverage.checkpoint in the next request's bounds, with the same
# source/query/caller and current grants. Retain partial status and all errors.
```

PrimeGov public search attachments can be explicitly retrieved with `engine.fetch_attachment(source, record, context=context)` after importing the search bundle into that engine's scoped storage. The configured source remains its HTTPS `public/portal` URL. The selected record must retain its original type, native document ID, meeting parent, namespace and declared document URL.

| Vendor search type | Selected document behavior |
|---|---|
| 1, system-item attachment | Exact public PDF URL resolver, then a bounded PDF-byte fetch |
| 2, system document | Exact public original-file route |
| 3, section attachment | Exact public PDF route including its native meeting ID |
| 4, compiled document | Exact file URL resolver for supplied numeric non-HTML output types; HTML type 3 and unknown output types remain unmapped |

The captured client assigns each JSON resolver's callback value to `window.location`. Accepting a JSON URL string is an explicit inference from that code, verified with synthetic responses; it is not an observed server response schema. Relative URL strings resolve against the configured public page. Every request rejects redirects and obeys the deadline, parser/request and cumulative transfer limits. Another download origin requires explicit `download_origins`. Received bounded resolver bytes survive subsequent failures; attachment citations use the durable meeting page rather than a resolved transient file URL. PDF signatures establish supplied byte shape, not rendering or live availability.

Types 1, 3 and 4 now use identity external IDs `type:<type>:<native-id>` to distinguish resources with overlapping numeric IDs. Native IDs remain unchanged in original fields and document metadata, and the canonical meeting parent remains part of identity. Existing type-2 and all baseline identities are preserved. This corrects the unpublished source's previously unqualified generic search identities for types 1/3/4; already stored unqualified records are retained and are not automatically migrated or reconciled. Earlier public-search checkpoints must restart because their identity contract has changed. See [the selected-document receipt](verification/primegov-selected-documents-2026-11-13.json) for the executed scope.

Date/body requirements are adapter-specific. Utah requires explicit dates and the configured public body for discovery; native search supports only its observed form. iQM2 rejects a body filter whose mapping is unverified. AgendaCenter and Boardable retain unknown bodies explicitly. AgendaQuick meeting rows and agenda items, iQM2 mixed result kinds, Select parents and related children, and ClerkBase supplied-URL document keys preserve their separate identities; consumers must not treat every result as a meeting.

Continuations are bounded by the current source/query/caller and policy. Process-private session cursors expire after 15 minutes and cannot survive an engine restart; cookies and CSRF state are not placed in public tokens. An expired, changed or unavailable continuation requires a fresh request. Exact raw captures remain available independently of normalized matching. No adapter bypasses captcha, login or staff controls. Fixture-only pager checks and bounded endpoint reads do not establish complete live traversal or installed-consumer acceptance.
