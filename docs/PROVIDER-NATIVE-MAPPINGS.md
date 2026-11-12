# Native retrieval mappings and legacy projection

Candidate schema 2.0.0. This is implementation documentation, not provider acceptance.

`providers/native.py` owns additive formats. They do not replace any of the original 34 inputs.

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

## Discovery output and v1 ownership

`discover.data` contains `source`, aggregate `records`, exact page `captures`, and page `bundles`. Every page bundle retains its own source namespace and compatibility projection. Aggregation filters rich records but does not rewrite the original page compatibility output, so callers must not import unfiltered compatibility rows blindly.

A shared legacy projection helper should project **the selected aggregate records**, restricted to meeting record_type, into a v1 `{version,source,meetings}` preview. It must retain the configured source namespace/URL and existing external IDs. A multi-page discovery has multiple capture hashes, so it cannot claim one page hash as the capture hash for all rows. Preserve per-record capture provenance separately and report discovery coverage through the consumer boundary.


## Added detail, supplied captions and observed tenant paths

`legistar-event-json` is the documented bare Event response, requesting supplied items, agenda/minutes notes and item attachment metadata. Native body search separately calls the bounded Events route with verified EventBodyName substring filters; it claims only body-field metadata coverage.

`wistia-media-detail-json` is the authenticated bare Media object, distinct from the unchanged public baseline `wistia-media-json`. Supplied assets retain URL/type/dimensions/file size and original fields. Media detail defines no caption body. `wistia-caption-json` accepts documented supplied track objects or a track list: provider track ID plus parent Media ID, language and source version remain explicit. Supplied cue millisecond anchors and SRT text are preserved. Native `/modern/search` stores complete original responses, returns media-only candidates and matching supplied transcript excerpts, and marks provider caps/no-pagination/excerpt coverage partial. No read requests diarization generation.

CHAMP fixed public `playapi.champds.com/{tenant}/event/{id}` retrieval uses the existing `champ-event-json` compatibility parser and namespace. The observed API returns JSON with an HTML MIME type; response content is still structurally checked as JSON and against the exact tenant/event identity. Two public tenant reads passed; event catalog discovery remains unresolved.

Tyler `calendar_api_base` is an explicitly supplied, same-host application base observed for a tenant. The engine POSTs inclusive date strings and the observed all-meeting-type identifier to its fixed date-range endpoint. It reports partial catalog coverage; an empty live response does not establish live nonempty-row or paging acceptance.


## NovusAGENDA observed public listing

Additive `novus-public-listing-html` reads the observed public ASP.NET form without evaluating source JavaScript. Displayed meeting and agenda-item cells, original link attributes, exact capture bytes and supplied ItemID/MeetingID parent links are retained. Missing provider IDs use explicit per-grid page/row/field derivation; meeting grid page remains unchanged while agenda-item pages advance. No board identity or complete archive/search semantics are invented. GET/POST requests stay on the exact configured HTTPS `/agendapublic/` endpoint; only a fresh validated Next Page target is posted with empty event argument. Cookie/header and form-control state stays private to the engine continuation cache. See the maintained SDK limits and public-read receipt.


## Essential dev API and TelVue Connect (post-dev3 source)

`providers/account_reads.py` implements explicit `fetch` requests for the documented Essential dev API meeting/item/multimedia GETs and single supplied-offset collection POST. Meeting/item/collection response models are undocumented: the result is a raw partial capture, without inferred normalized rows or automatic pagination. `essential-multimedia-json` maps only the documented meetingStructure wrapper. No exact native search semantics are claimed for Words.

The same dispatcher implements TelVue Connect GET media/videos/playlists and only the documented media/playlist detail routes, using the exact CONNECT access-key/passphrase headers. `telvue-connect-media-json`, `telvue-connect-videos-json`, and `telvue-connect-playlists-json` preserve original envelopes/bytes, IDs, transcript, chapters, sources, and unknown fields. No list continuation/end condition or video detail route is invented. Current explicit origin, application account namespace and caller tenant binding is required before credentials are sent. Public tenant legacy identity behavior stays unchanged.

`providers/essential_write.py` maps meeting_multimedia:update only: patch typed documented full-model fields while preserving fixed structure/meeting/item identities and unknown values, then POST the full model with exact readback and durable uncertain-outcome handling. All account checks are synthetic in `tests/test_account_apis.py`; account credentials and live acceptance remain unavailable/NOT_RUN. These implementations do not establish API writes for TelVue, general agenda writes for Essential, token issuance, complete listing or live vendor acceptance.


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
