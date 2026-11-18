# Native retrieval mappings and legacy projection

[Release scope for dev15](DELIVERY-SCOPE.md) gives the current per-provider read and write coverage. Dated counts and artifact references below identify earlier verification snapshots.

Candidate schema 2.0.0. This is implementation documentation, not provider acceptance.

`providers/native.py` owns additive formats. They do not replace any of the original 34 inputs.

CHAMP now also has explicitly selected calendar-group discovery from its
municipality-declared archive and vendor client. It preserves native meeting
identities and both source captures without fetching event details. See
[the bounded archive contract and example](CHAMP-ARCHIVE.md); other groups,
months and external publisher records remain outside that result's coverage.

November 13 public-lead additions are documented separately: [Tyler selected
calendar/detail/search](TYLER-PUBLIC.md), [OnBase embedded results and date
windows](ONBASE-PUBLIC-WINDOWS.md), [BoardDocs committee listing and printable
detail](BOARDDOCS-PUBLIC.md), and [CivicClerk Select detail/files and section
writes](CIVICCLERK-SELECT.md). The [scoped receipt](verification/public-contract-leads-2026-11-13.json)
distinguishes vendor sources, third-party source, public response observations
and synthetic engine execution. No baseline input mapping is replaced.

## Legistar Events

Official references checked November 11, 2026:
https://webapi.legistar.com/Help/Api/GET-v1-Client-Events
and https://webapi.legistar.com/Home/Examples.

Input format: `legistar-events-json`. JSON array, never the old Core-export JSON.

| API field | Normalized field |
|---|---|
| EventId | external_id, decimal string |
| EventBodyName | title and body |
| EventDate | source_date verbatim; meeting_date from the source calendar date |
| EventTime | source_time verbatim |
| EventLocation | location |
| EventInSiteURL | url when public and credential-free; configured citation otherwise |
| EventAgendaFile / EventMinutesFile | documents with agenda/minutes kind |
| EventVideoPath / EventMedia | recordings |
| EventItems | agenda_items with EventItemId, EventItemTitle, EventItemAgendaNumber and original source_fields |
| EventRowVersion / EventLastModifiedUtc | provider_supplied source_revision |
| EventAgendaStatusId/Name, EventMinutesStatusId/Name, EventVideoStatus | source_status, without cancellation filtering |

The mapper does not combine a midnight EventDate with EventTime to invent an offset-aware instant. `time_zone_status` remains `unknown`. Source-supplied motions/votes stay in each item's source_fields, not inferred from prose. Original unknown values and exact capture bytes survive.

Legacy v1 projection retains the same normalized meeting dictionaries, including `external_id`, `title`, `meeting_date`, `url`, `location`, `documents`, `recordings`, `agenda_items` and additive source fields. Projection is not a reparse as the old `MeetingId`/`MeetingName`/`MeetingDate` format.

## Namespace and existing record keys

Every mapping calls the existing `compat.source_namespace(provider, urlsplit(configured_source.url))`. Retrieval request URLs never replace that configured durable source URL.

- Configure the same historic public citation URL to keep its existing namespace, for example `https://city.legistar.com/Calendar.aspx` gives `//city.legistar.com`.
- A source configured directly at `https://webapi.legistar.com/v1/city/Events` retains the existing namespace `//webapi.legistar.com/v1/city`.
- Those two strings are not silently aliased. The library has no independently verified tenant mapping authorizing that merge. An application migrating its configured URL must preserve/reconcile its existing source mapping explicitly.
- Native upstream identity uses EventId, not an application destination ID, capture hash, or revision.

## Wistia account media

Input format: `wistia-api-media-json`. Official modern list endpoint:
https://docs.wistia.com/reference/get_medias.md.

`hashed_id` maps to external_id; name/description remain title/description; duration/type/status/thumbnail remain recording metadata. created/updated remain source_created/source_updated, with updated in source_revision. Upload time is **not** a meeting date. These records have record_type `recording`; their missing meeting date remains explicit in bounded discovery coverage. They do not enter a legacy meeting import automatically.

## Laserfiche WebLink listing

Input format: `laserfiche-listing-json`, based on independently captured public WebLink 11 responses, not the separate Repository API.

Each dated document entry preserves its provider entryId as external_id, matching the legacy per-document identity model. The document name provides meeting_date with `meeting_date_derivation=dated_document_name`. ElectronicFile.aspx versus DocView.aspx follows supplied isEdoc. Original entry fields are retained. Undated or nonmeeting entries remain explicit unclassified coverage. Folder failures/depth/page/date bounds cannot become a complete catalog.

Saved `laserfiche-listing-json` pages can be replayed through `normalize` without
a session. Replay uses the configured WebLink base path, repository and database
for citations, preserves the supplied listing `folderId` separately, and does
not infer that a child listing belongs directly to the configured root. It maps
dated document names with the same rules as guarded discovery, retains exact
capture bytes and original rows, and discloses unclassified entries and
untraversed folders. One page never proves full folder or archive coverage and
does not initiate continuation, viewer-text or Repository account requests.

## Laserfiche Repository entry metadata

The account API is separate from WebLink. Given an explicit configured v2 folder
Children URL, `fetch_record` uses the same repository and one caller-supplied
positive entry ID. The pinned vendor SDK documents GetEntry and repository.Read.
Both returned entry ID and parent folder must match; the repository-wide source
identity keeps its parent as a relationship. Unknown fields, supplied revisions
and exact response bytes are retained. `laserfiche-repository-entries-json`
normalizes either the OData children wrapper or one Entry object. Neither path
retrieves file content or treats creation/modification time as a meeting date.
See [the SDK example](SDK.md#related-legistar-records-and-repository-folder-reads)
and [scoped synthetic evidence](verification/laserfiche-entry-metadata-2026-11-13.json).

Original electronic files have a separate attachment operation: the documented
Repository `/Export` POST with `part=Edoc` returns a private single-use download
link. The connector revalidates the current parent folder, requires configured
download origins, sends no bearer header to the download, and retains the durable
entry citation and fresh metadata revision. Byte/deadline bounds and cancellation
apply across the steps; a retry creates a new export. This does not extract text,
export image pages or infer WebLink account access. See
[synthetic content evidence](verification/laserfiche-document-content-2026-11-13.json).

The same scoped attachment path now supports explicit Image, Text and AlternateEdoc
export options from the pinned SDK. Edoc remains the default. Image PDF/TIFF/PNG/JPEG
choices retain included annotations/redactions; TIFF uses AsStored compression.
Text retains redactions. AlternateEdoc names are validated against the vendor's
restricted character/length contract. Download results disclose the selected
representation, preserve exact returned bytes and use the durable entry citation.
See [variant mapping evidence](verification/laserfiche-export-variants-2026-11-13.json).

The explicit `repository_export_async` source option selects the documented
ExportAsync/Tasks lifecycle for any of those representations. Only the task ID
issued by the current call is polled or cancelled. Status, task type and optional
result entry identity are checked; completed export `result.uri` remains private
and single-use. Early exit requests exact-task cancellation and independently
checks terminal state within reserved time/bytes. Unconfirmed cleanup remains
explicit, with the task ID available for follow-up. There is no cancel-all request,
document mutation, background worker or task-resume cursor. See
[synthetic task evidence](verification/laserfiche-async-export-2026-11-13.json).

Opt-in `fetch_record(..., include_text=True)` enriches that document with existing
page text from the pinned SDK's ListPageInfos and GetPageText contracts. Supplied
page IDs and numbers remain anchors within the document, not new meeting IDs.
Exact page response captures use the standard supplemental `captures` location;
the document's original metadata capture and fields remain intact. Text hashes
participate in normalized change detection. Missing streams and bounds remain
explicit through local search. No generation, OCR or atomic snapshot is claimed.
See [scoped text evidence](verification/laserfiche-page-text-2026-11-13.json).

Repository native search uses the explicit configured API folder, trusted
`laserfiche_token`, and the pinned SearchAsync/Tasks/Results/ContextHits contract.
The first literal term or phrase obtains Basic-search candidates across document
text, fields, annotations and names; numeric LookIn plus Subfolders=N restricts
the query to direct children. Quotes and wildcard/indexed-string characters are
escaped using the pinned vendor syntax paper. The shared local matcher applies
all requested exact terms/phrases to the metadata and excerpts actually returned.
This is not a full-document exact-search or catalog-completeness claim.

Result and context pages preserve original bytes, unknown fields, supplied row/hit
identities and page anchors. Parent IDs, task type/identity and the exact result
route are verified. Record/page/time and cumulative API-byte bounds apply;
failed context reads retain metadata with partial coverage. Dates/bodies cannot
be inferred from repository creation times. Search tasks are removed using only
the issued task ID, including after successful reads; cleanup acknowledgement
and confirmed cancellation remain separate. No cross-call task cursor, WebLink
account inference, generated text or live-tenant acceptance is claimed. See
[synthetic search evidence](verification/laserfiche-native-search-2026-11-13.json).

Source option `repository_include_fields: true` enriches selected entry detail,
discovery records and native-search candidates from the pinned SDK's paginated
`GET Entries/{id}/Fields` route. Listing/search field projections can contain only
the first value; this route obtains assigned field objects and their supplied
multi-values. Values are unformatted strings, with missing/null/empty values and
unknown properties preserved. A field named Date is not promoted to a meeting
date. Already captured `Entry.fields` are also retained in searchable normalized
metadata without any additional network request.

Field reads keep exact supplementary captures and normalized change detection.
They are opt-in and do not alter the original GetEntry/list/search capture or
record identity. `field_metadata` coverage distinguishes complete, unavailable,
truncated and unknown/more-value responses. Collection pages, field count,
cumulative supplemental bytes, caller cancellation and the original deadline
are bounded. Native search shares its existing task API-byte budget; combined
detail field/page-text reads share their supplemental byte budget. Partial field
reads keep obtained values and metadata, including through later discovery
failure and SQLite import/ZIP export. Saved discovery captures initiate no field
requests; the option does not affect attachment export's internal membership
check. See [synthetic field evidence](verification/laserfiche-fields-2026-11-13.json).

## OnBase Agenda Online supplied meeting-document wrappers

The recorded Fitchburg `Documents/Downloadfile/...pdf` response is a vendor-authored
HTML download wrapper, not PDF bytes. Its exact captured JavaScript declares
`InvokeDownloadMeetingDocument` (POST with no data) and `ViewDocument` (GET after
a one-second preparation delay). The mapped reader treats this page as data;
it does not execute JavaScript or follow arbitrary supplied routes.

Only captured HTTPS same-tenant meeting documents are mapped. The wrapper's
meeting/type/name constants, meeting-document branch and exact route templates
must agree with the selected record and link. Preparation JSON must identify the
same meeting, document type/name, zero item/publish IDs and non-section scope.
Final bytes require PDF magic and a PDF/octet-stream media type. Section
attachments and changed/unknown wrappers remain partial, with the meeting
retained. Selected non-section agenda-item attachments use the separate explicit
`fetch_attachment` mapping below.

Cookies stay in one call's memory and are never returned in captures. Requests
disable redirects, retain public-network safeguards and share the original
deadline/transfer budget; HTML/JSON also share a parser budget. At least three
request slots are needed. Verified wrapper/preparation captures survive a later
failure and are returned in `data.captures`; supplied capture bundles include them
for explicit persistence and export. The original supplied link stays the citation.
The [pinned wrapper](capabilities/evidence/onbase-download/source.json) and
[synthetic execution receipt](verification/onbase-meeting-document-2026-11-13.json)
establish this narrow wrapper mapping. They do not establish live PDF
availability, native search, Agenda detail, meeting-associated import or full
Agenda coverage. This existing meeting-document retrieval path is unchanged.

## OnBase current-listing meeting and Agenda detail

From the configured HTTPS `/OnBaseAgendaOnline/` root, `fetch_record` first
revalidates the supplied native meeting ID against the current listing. It then
accepts only the exact supplied `Meetings/ViewMeeting?id=<id>&doctype=1` page,
checks its declared accessible agenda URL, and reads only
`Meetings/ViewMeetingAgenda?meetingId=<id>&type=agenda`. The result carries the
native meeting plus supplied `agenda_section` and `agenda_item` records. Child
IDs use the meeting as their canonical parent; supplied items also preserve the
parent-section relationship. The meeting keeps current-listing normalized
metadata and recording references/relationships when agenda data is composed,
and the compatibility meeting projection is synchronized to the final record.
The same `onbase-public-listing-html` format parses the exact supplied
`Meetings/ViewMeetingAgendaItem` variant with
`isSection=false&type=agenda` for an item and `isSection=true&type=agenda` for
a section. `fetch_related` lists sections or items; selected detail requires
current-agenda membership in the requested record type and the exact literal
route declared by the meeting page. Section IDs retain section identity even if
an item has the same number. The observed section response supplies only its
rendered title; attachments and additional section content are not established.

Original supplied fields, HTML captures and citation URLs are retained. Rendered
text has partial completeness; timezone remains unknown. Attachment native IDs,
publish IDs and supplied links remain locators and are not fetched by this path.
Reads enforce cumulative parser/transfer bytes, page and deadline bounds,
cancellation, same-origin exact response URLs and disabled redirects. Successful
results remain partial, with no catalog/source completeness or snapshot guarantee.
The three actual public detail-page GET captures are pinned in
[the evidence manifest](capabilities/evidence/onbase-detail/source.json). The
[scoped receipt](verification/onbase-detail-2026-11-13.json) records 17 new
synthetic cases and 70 affected cases passed, including SQLite reopen, search and
ZIP roundtrip; this is not whole-provider or live API acceptance. Native search,
meetings absent from the current listing, other Agenda variants, broader APIs
and remote import or association to an existing application meeting remain
unresolved.

The subsequent [section capture](capabilities/evidence/onbase-detail/section-source.json)
and [section receipt](verification/onbase-section-detail-2026-11-13.json) extend
selected detail to native sections under the same bounds and partial semantics.

## OnBase selected item attachment retrieval

The detail and related-record calls return supporting-document native IDs,
publish IDs and supplied URLs as locators; they do not fetch the attachment.
`fetch_attachment` separately resolves a supplied locator on a selected
`agenda_item` record. The locator, canonical meeting parent, item ID, publish ID,
document type `1`, `isSection=false` and `isAttachment=true` must agree with the
record. The captured wrapper must declare the exact same-tenant
`InvokeDownloadAttachment` POST and `ViewDocument` GET, with a safe `.pdf`
filename. Preparation JSON must echo the selected meeting/item/publish/type and
non-section scope; the returned body must have PDF magic and a PDF or
octet-stream media type. The call uses strict same-origin exact-URL requests,
disabled redirects, cumulative bounds, deadline/cancellation checks and
in-memory cookies. The result returns the file bytes; supplemental captures retain
the verified wrapper and preparation responses without cookie values.

The observed published attachment branch is pinned with the existing wrapper
evidence. Its item-specific wrapper and PDF response are synthetic composition;
no real item wrapper or PDF response was captured, so live file availability and
rendering are unverified. Only the selected non-section Agenda item branch is
mapped; section attachments and packet routes remain unmapped. The receipt records
24 new synthetic cases, including reopened-item retrieval and capture
persistence/ZIP roundtrip: [item-document receipt](verification/onbase-item-document-2026-11-13.json).

## Discovery output and v1 ownership

`discover.data` contains `source`, aggregate `records`, exact page `captures`, and page `bundles`. Every page bundle retains its own source namespace and compatibility projection. Aggregation filters rich records but does not rewrite the original page compatibility output, so callers must not import unfiltered compatibility rows blindly.

A shared legacy projection helper should project **the selected aggregate records**, restricted to meeting record_type, into a v1 `{version,source,meetings}` preview. It must retain the configured source namespace/URL and existing external IDs. A multi-page discovery has multiple capture hashes, so it cannot claim one page hash as the capture hash for all rows. Preserve per-record capture provenance separately and report discovery coverage through the consumer boundary.


## Added detail, supplied captions and observed tenant paths

`legistar-event-json` is the documented bare Event response, requesting supplied items, agenda/minutes notes and item attachment metadata. Native body search separately calls the bounded Events route with verified EventBodyName substring filters; it claims only body-field metadata coverage.

`wistia-media-detail-json` is the authenticated bare Media object, distinct from the unchanged public baseline `wistia-media-json`. Supplied assets retain URL/type/dimensions/file size and original fields. Media detail defines no caption body. `wistia-caption-json` accepts documented supplied track objects or a track list: provider track ID plus parent Media ID, language and source version remain explicit. Supplied cue millisecond anchors and SRT text are preserved. Native `/modern/search` stores complete original responses, returns media-only candidates and matching supplied transcript excerpts, and marks provider caps/no-pagination/excerpt coverage partial. No read requests diarization generation.

CHAMP fixed public `playapi.champds.com/{tenant}/event/{id}` retrieval uses the existing `champ-event-json` compatibility parser and namespace. The observed API returns JSON with an HTML MIME type; response content is still structurally checked as JSON and against the exact tenant/event identity. Two public tenant reads passed; event catalog discovery remains unresolved.

Later rich source normalization additionally preserves [CHAMP native agenda relationships](CHAMP-AGENDA.md), item descriptions/document IDs and captured-player timeline anchors. The compatibility projection remains unchanged. Supplied visible descriptions are searchable with citation/item provenance and a timestamp when exactly one validated interval is associated; this does not infer transcript text, speakers or media-byte verification.

Tyler `calendar_api_base` is an explicitly supplied, same-host application base observed for a tenant. The engine POSTs inclusive date strings and the observed all-meeting-type identifier to its fixed date-range endpoint. It reports partial catalog coverage; an empty live response does not establish live nonempty-row or paging acceptance.


## NovusAGENDA observed public listing

Additive `novus-public-listing-html` reads the observed public ASP.NET form without evaluating source JavaScript. Displayed meeting and agenda-item cells, original link attributes, exact capture bytes and supplied ItemID/MeetingID parent links are retained. Missing provider IDs use explicit per-grid page/row/field derivation; meeting grid page remains unchanged while agenda-item pages advance. No board identity or complete archive/search semantics are invented. GET/POST requests stay on the exact configured HTTPS `/agendapublic/` endpoint; only a fresh validated Next Page target is posted with empty event argument. Cookie/header and form-control state stays private to the engine continuation cache. See the maintained SDK limits and public-read receipt.


Granicus’s [lifecycle planning page](https://granicus.com/iqm2-and-novusagenda-end-of-life-planning/) gives Novus data extraction as December 11, 2026 and final shutdown as December 31, 2026 in its migration guidance; its earlier FAQ/table retains a conflicting 2025 date and its [downloadable FAQ](https://granicus.com/wp-content/uploads/application/pdf/FAQ_EOL_IQM2_NOVUS.pdf) lists September 30, 2025. These are vendor plans, not observations that every tenant is unavailable. Saved captures and the scoped public reader remain applicable. See the [lifecycle source evidence](capabilities/evidence/granicus-legacy-lifecycle/source.json).


## CivicWeb MeetingsService listing

Additive `civicweb-meetings-json` maps the tenant's public `/Services/MeetingsService.svc/meetings?from=YYYY-MM-DD&to=YYYY-MM-DD` array and `civicweb-meeting-documents-json` maps `/meetings/{id}/meetingDocuments`. Meeting identity is the provider `Id` in the tenant namespace; title is `Name` and the day is `MeetingDate`. `MeetingDateTime` is kept as a local literal with `time_zone_status: unknown`. `body` is the portal meeting-type name for `TypeId` (from `/Portal/MeetingTypeList.aspx`), else the title with its trailing date and any cancellation marker removed, with `body_source` saying which. Rows with `Published` not true, rows without an ID/title/date, are left out and counted in coverage. Meetings of a meeting type whose name matches notices, reports, budgets, ordinances, financials, newsletters, messages, profile, applications, articles or calendar are kept and flagged (`likely_not_a_meeting`, `likely_not_a_meeting_type`; types in `coverage.flagged_meeting_types`); the request option `exclude_likely_non_meetings: true` omits them and counts them in `coverage.likely_non_meeting_omitted`. Document identity is the provider document `Id` with the meeting as parent identity. `DocumentType` 1/9 map to HTML and 4/10/53 to PDF links of the form `/document/{id}/{name}.html|.pdf`; other types use the bare `/document/{id}/` route; `IsPublic` not true gives no link. The inline `Html` body is not copied into the record original (the exact bytes are in the capture). Nothing is downloaded. Routes are observed on a public tenant, not a vendor-documented API.

## Cablecast shows

Cablecast (`*.cablecast.tv`) is a built-in typed connector outside the 31 baseline families. `cablecast-shows-json` maps `/cablecastapi/v1/shows` and `cablecast-show-json` maps `/cablecastapi/v1/shows/{id}`. Show identity is the show `id` in the `//{host}` namespace. Shows with no `vods` entry are not recordings and are left out. The day is the day the title names, else `eventDate`'s first ten characters. The site ignores `pageSize`, so the reader sends `page_size=200` (and `pageSize=200`); `offset` is observed to act as a page index on the one site read. Copies of a meeting share title and day; the reader keeps the copy whose `vod.m3u8` has a `SUBTITLES` entry and records the others in `duplicate_show_ids`. Recording and caption entries are links: watch page `/internetchannel/show/{id}`, the vod `url`, the HLS `vod.m3u8` and the `SUBTITLES` playlist. Caption segment text, media files and audio are not read.

## Municode public PublishPage

`municode-publishpage-html` reads one explicitly configured public PublishPage. It scopes the supplied `me` selector to the `cid` tenant and preserves the listing columns, document and multimedia locators, original HTML and declared page controls. The selector comes from ADA document links and is not asserted to be an authenticated API meeting ID. It does not infer time zone or status, fetch linked files, or traverse pages automatically. See [the bounded format guide](MUNICODE-PUBLISHPAGE.md).

## Essential account API and TelVue Connect (post-dev3 source)

`providers/account_reads.py` implements explicit `fetch` requests for the documented Essential meeting/item/multimedia GETs and single supplied-offset collection POST. The support article's development origin and the vendor-linked Postman collection's production origin are selected explicitly; credentials bind to the chosen origin and cannot be reused across them. Meeting/item/collection response models are undocumented: the result is a raw partial capture, without inferred normalized rows or automatic pagination. `essential-multimedia-json` maps only the documented meetingStructure wrapper. No exact native search semantics are claimed for Words.

| Explicit source origin | Item detail route |
|---|---|
| `https://meetingsgov.devmunicode.com` | `/PublicApi/item/{id}` from the support article |
| `https://meetings.municode.com` | `/PublicApi/meeting/item/{id}` from the [vendor-linked Postman documentation](https://documenter.getpostman.com/view/7558574/TWDcEuDz) |

Meeting, multimedia and collection routes keep
their documented `/PublicApi/meeting/` paths on the selected origin. No origin
fallback, automatic token acquisition or alternate item-route probing occurs.
The current [vendor-linked Postman collection](https://documenter.getpostman.com/view/7558574/TWDcEuDz)
contains a production multimedia update sample with lower-camel-case `id`,
`meetingId`, `audioVideoDetails` (`audioVideoProviderType`, `audioVideoUrl`),
`publishState`, and `multimediaItems` fields (`entityId`, `entityName`,
`entityTypeName`, `timeStamp`, `multimediaDisplayOptions`, `customDisplay`,
`includeNumbering`, `useDefaultMultimediaSettings`, `multimediaBaseUrl`). Its
multimedia GET and update POST both have zero response examples. The [official
development API article](https://www.civicplus.help/meetings-essential/docs/public-application-programming-interface-api)
shows a Pascal-case .NET `MeetingStructure` inside `meetingStructure` for its
development host and describes the update response only as `HttpResponseMessage`;
it does not document production response casing/wrapper or persistence/readback
semantics. That development response cannot safely be assumed for production.
Although the production request fields are recorded, no production response is
supplied. The write adapter therefore remains unmapped and rejects production
updates before network; its internal reads also target only the development
origin. No account is required to record this source-level gap; no live account
request or mutation was made. Meeting/item create/update and file upload remain
unresolved. See the [production-route receipt](verification/essential-production-2026-11-14.json)
and [saved collection evidence](capabilities/evidence/essential-postman/source.json).

The same dispatcher implements TelVue Connect GET media/videos/playlists and only the documented media/playlist detail routes, using the exact CONNECT access-key/passphrase headers. `telvue-connect-media-json`, `telvue-connect-videos-json`, and `telvue-connect-playlists-json` preserve original envelopes/bytes, IDs, transcript, chapters, sources, and unknown fields. No list continuation/end condition or video detail route is invented. Current explicit origin, application account namespace and caller tenant binding is required before credentials are sent. Public tenant legacy identity behavior stays unchanged.

`providers/essential_write.py` maps meeting_multimedia:update only: patch typed documented full-model fields while preserving fixed structure/meeting/item identities and unknown values, then POST the full model with exact readback and durable uncertain-outcome handling. All account checks are synthetic in `tests/test_account_apis.py`; live acceptance remains NOT_RUN and is not a synthetic acceptance gate. These account-read mappings do not establish general agenda writes for Essential, token issuance, complete listing or live vendor acceptance.

`providers/telvue_write.py` separately maps `playlist_order:update` and `playlist_membership:create` from the exact public Connect client. It uses application-owned tenant/namespace/playlist/meeting/media policy, session+CSRF POSTs and documented v2 credentialed readback. Only the scoped synthetic transactions are accepted; upload and vendor meeting association remain unmapped. See [the contract](TELVUE-WRITES.md) and [source/evidence receipt](verification/telvue-boarddocs-contracts-2026-11-14.json).


## CivicClerk captured media in discovery

For `civicplus-select` discovery, an already supplied, valid absolute HTTPS
`mediaStreamPath` is retained as a recording, relationship and citation. The
observed Erie event1277 capture exercises this path. Relative storage names and
malformed values remain in the original record but are never expanded into a
constructed CDN address. This does not establish that every tenant supplies the
same media format or that an attachment is reachable.

The direct `normalize` compatibility contract remains unchanged. Discovery's
selected-record projection adds the captured recording to the matching legacy
meeting only when its identity and capture hash match; it preserves namespace,
external ID and original capture bytes. Canonical import preview retains the
same enriched record. Retrieving an external media origin still requires the
source's explicit `options.download_origins` and all existing guarded network,
current authorization and transfer bounds. A supplied URL is not a download
permission or proof of a completed Station/transcription handoff.

A captured HTTPS `mediaStreamPath` whose URL path ends in `.mp4` additionally
sets `video_url` in discovery and the matched legacy projection. This exposes
the supplied direct-file candidate to consumers such as Station without
classifying a generic player link as a downloadable MP4. Guarded retrieval and
consumer file validation still apply; the path is not proof of playable bytes.

The pinned official `EventModel_28658b0b` also declares
`mediaSourcePathMp4`, `closedCaptionSourcePath` and `closedCaptionBlobPath`.
Discovery and selected detail expose supplied absolute HTTPS values, requiring
an MP4 URL path for the direct video field. Repeated caption URLs deduplicate;
relative storage names remain raw. Caption descriptors use `kind: transcript`;
retrieved bytes retain `text_availability: not_extracted`. No caption timing,
playability, visibility or processing readiness is inferred. Guarded transfers
recheck the captured published Event, native identity, exact descriptor and
source, require explicit download origins, reject redirects and honor bounds.
SQLite/reopen and neutral ZIP preserve these values and original captures.
[Executed scope and contract hashes](verification/civicclerk-supplied-assets-2026-11-14.json)
cover synthetic transfers; preserved dev13 packages predate this source.

## Boardable legacy agenda client

[BOARDABLE-WRITES.md](BOARDABLE-WRITES.md) documents the pinned runtime org/meeting binding, native list and item GETs, reorder JSON and preserved-field multipart text edits. Vendor client source and36 synthetic coordinator checks are separately attributed; new editor/draft creation/new files/publication remain unmapped. Current source is later than preserved dev13 packages.

## gWorks and TownCloud

[gWorks published HTML](GWORKS-PUBLISHED-HTML.md) uses the original city listing namespace and meeting ID. Rendered item IDs remain capture-local. Its [production editor mapping](GWORKS-EDITOR.md#production-one-unpublished-meeting-title-location-or-schedule) supports one title, location or schedule change on an existing unpublished meeting. The [TownCloud public reader](TOWNCLOUD-AGENDA.md) retrieves selected documents from the direct or embedded listing capture. The [existing TownCloud draft-text adapter](TOWNCLOUD-WRITES.md) is preserved and further writes remain parked.

Historical TelVue CloudCast 4.1 chapter CSV preparation is available as `telvue-cloudcast-4.1-chapters-csv`; see [the format and limits](TELVUE-CHAPTER-CSV.md). This is local file preparation, with current Connect applicability and remote import unverified.

Legistar legislative Text Editor preparation is available as `legistar-legislative-text`; see [the explicit title/body format and encoding limits](LEGISTAR-TEXT-FILES.md). This prepares a local `.txt` file with documented section markers. It does not establish historical meeting/media migration, remote import or association.

Peak public archive search now maps the vendor-declared GET form and native clip groups with rendered search excerpts. See [request, continuation and source inconsistency limits](PEAK-PUBLIC-SEARCH.md). Empty or inconsistent later pages fail verification; no complete empty search or full-document coverage is inferred.

## Account response bounds

TelVue Connect and Essential account reads check cancellation and the shared
operation deadline after response mapping and identity checks, before returning
a bundle. Cancellation returns `cancelled`; an expired deadline returns the
existing sanitized `account_read_failed` error. Mapping is synchronous and is
checked on return. No additional requests or automatic continuation are made.
The [executed boundary cases](verification/account-read-boundaries-2026-11-15.json)
cover both providers without requiring live credentials.

Essential production request routes have no response examples in the pinned
official-linked collection. Production multimedia therefore preserves an exact
raw partial capture, as do its meeting/item/collection routes; it does not
apply the development-only normalized MeetingStructure model. The documented
development-host mapping remains available. The
[response qualification regressions](verification/essential-response-qualification-2026-11-15.json)
cover development-shaped, lower-camel and unknown production fixtures without
claiming any of them is an observed production response.


### Utah supplied notice assets (2026-11-15)

Native notice detail enrichment retains the exact Add Notice to Calendar locator and explicitly labeled Audio Recording MP3 locator. Exact calendar file bytes are independently captured; no calendar-to-notice field merge, timezone or recording-date inference. Legacy output unchanged. See [mapping and limits](UTAH-SUPPLIED-ASSETS.md) and [211-case affected verification](verification/utah-supplied-assets-2026-11-15.json).


### Shared attachment completion bounds (2026-11-15)

Document/recording byte attachments check cancellation and the total deadline after the transfer and final wrapper resolution. Interrupted reads retain the source record and any captured wrapper context, returning cancelled or partial rather than completed. Cancellation is cooperative after synchronous work returns. Exact provider route/origin/MIME checks remain in force. See [120 affected cases](verification/attachment-response-boundaries-2026-11-15.json).


Explicit Digital Towpath detail retrieval now applies the smaller parser/transfer response cap and checks cancellation/deadline after normalization. An interrupted detail returns cancelled/failed without a completed mapped result. See [three regressions and full1968-case source validation](verification/owned-boundaries-full-2026-11-15.json).


### TelVue source-declared public captions (2026-11-15)

The original public playlist native-media link now supports literal player JSON metadata and explicit supplied WebVTT reading without account credentials. No script execution, title-date/language-code inference, playback or staff-write contract is implied. See [mapping and identity limits](TELVUE-PUBLIC-CAPTIONS.md) and [253 affected execution cases](verification/telvue-public-player-2026-11-15.json).


### SuiteOne supplied event transcripts (2026-11-15)

Native event2165 now maps its selected rendered transcript table/source timing strings and explicit declared WebVTT. Stable event key matches the original archive. No script execution, date/body/cue/vote/playback or Liberty timed-import equivalence is inferred. See [mapping and limits](SUITEONE-SUPPLIED-TRANSCRIPTS.md) and [245 affected checks](verification/suiteone-public-event-2026-11-15.json).

The local eSCRIBE [PublishingService mapping](ESCRIBE-PUBLISHING-SERVICE.md) now pins a deployed WSDL/five XSDs and implements scoped native record reads/create/update plus metadata-bound document bytes. Exact native parameters and synthetic coordinator evidence are separate from public portal HTML, chunk-upload semantics and live deployment/visibility acceptance.

## BoardBook public search-index entries

`boardbook-public-search-html` and the native search handler map the declared public GET form with four observed index types to explicit `search_result` records. Index/native ID remain distinct from canonical meeting/item/document IDs; parent identity and dates are not inferred. Native locators, rendered excerpts, exact captures and hashes survive persistence and neutral export. All native results remain partial; local offset checkpoints bind the entire captured response hash. See [usage, fields and limits](BOARDBOOK-PUBLIC-SEARCH.md).

## Town Hall Streams archive keyword search

The public native search handler uses the baseline/current declared POST form and reuses `town-hall-streams-html`. Literal event IDs/local dates/title/stream links stay within the configured location; precise stream citations and exact POST capture/context survive storage/export. One39meeting current response and scoped execution are documented in [the usage guide](TOWNHALL-PUBLIC-SEARCH.md). No provider exhaustion/fulltext/body or time-zone inference.

## TelVue player-wide public video search

`telvue-public-search-html` maps43observed native media candidates to recording IDs, supplied title/summary/duration, explicitly title-derived dates and exact search-locator citations/relationships. Query-bearing locators stay outside searchable metadata so22exact local hits persist after reopening. Playlist sources are rejected rather than broadened. Native search remains partial with declared/unretrieved counts and local hash-bound offset continuation; caption/chapter match text and server paging remain unverified. See [contract](TELVUE-PUBLIC-SEARCH.md).
