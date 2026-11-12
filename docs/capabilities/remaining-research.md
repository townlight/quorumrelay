# Remaining provider research and access gaps

All operations remain mandatory where exposed in the bounded domain. Unknown is not unsupported. The resumed full plan authorizes supported writes against explicitly authorized provider test tenants. No such test tenant or credentials were supplied, so live write acceptance remains access-blocked; no arbitrary public-city data was mutated. Procurement and outreach remain unauthorized.

## F01 Legistar (`legistar`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"Some clients public; others token query required. Tenant policy controls access.","outbound":"Write credential scope and authorized test tenant not supplied."}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://webapi.legistar.com/v1/olympia: One Events result fetched publicly; flattened extractor output is not raw JSON acceptance.

### Remaining research

- Follow-up exact Help-page review (2026-11-12 UTC) confirms attachment create/update JSON exposes `MatterAttachmentBinary` as base64 bytes, separate hyperlink/file-name fields, and visibility flags; create sort is server-generated and update sort cannot change. Existing `write_adapters.py` implements these fields, excludes sort and compares `/File` readback bytes. [Create contract](https://webapi.legistar.com/Help/Api/POST-v1-Client-Matters-MatterId-Attachments), [update contract](https://webapi.legistar.com/Help/Api/PUT-v1-Client-Matters-MatterId-Attachments-MatterAttachmentId), [file readback](https://webapi.legistar.com/Help/Api/GET-v1-Client-Matters-MatterId-Attachments-MatterAttachmentId-File). Provider byte limits, processing and tenant visibility behavior are not specified there and still need authorized acceptance.
- [Event creation contract](https://webapi.legistar.com/Help/Api/POST-v1-Client-Events) exposes `EventMedia` and `EventVideoPath` as strings, without file/upload semantics. Existing string mappings do not establish binary recording upload or replacement; those exact semantics remain unresolved. No additional media endpoint was inferred and no provider mutation was performed.
- Olympia Event 7011 and the selected Vote/RollCall reads are bounded receipts, not catalog coverage. Write token, tenant permissions, accepted Vote/RollCall ValueId enumeration and RowVersion conflict behavior need an authorized test tenant; none was supplied.
- The historical vendor import package/current media import path has no accepted file contract or authorized transfer evidence.

### Pagination contract

{
  "status": "documented",
  "evidence_ids": [
    "legistar-paging"
  ],
  "details": "$top/$skip, max1000; stable EventId order/keyset checkpoint for mutable catalogs; ge lower/lt upper EventDate examples."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.

## F02 PrimeGov (`primegov`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://reno.primegov.com/public/portal: Search/filter UI fetched publicly; no catalog-completeness test.

### Remaining research

- The observed Reno public `/api/v2/PublicPortal/search` form is source-implemented after dev6. Bounded first/resumed calls each returned three distinct records with partial coverage. Stable native-kind/id traversal handles provider tie-order changes and checks canonical row-set values while retaining exact captures; ranking is deliberately not retained. Exact local checks use supplied metadata/highlight excerpts only. Full document content, provider matching/caps and cross-tenant completeness remain unverified; authenticated Meeting API routes are separate.
- Official release notes identify Meeting API, speaker endpoint and tracking-number search but no executable schema. Obtain PrimeGov account-specific API specification and enablement before coding those routes.
- No provider write tenant/credentials were supplied; create/update/upload fields, permissions, readback and conflict semantics remain unverified.

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.

## F03 Granicus (`granicus`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townofsuperior.granicus.com/ViewPublisher.php?view_id=2: Public listing with meeting rows and links.
- 2026-11-12 bounded native Clip search: same-origin `ViewSearchResults.php` form uses numeric `view_id`, `types[Clip]=on`, first supplied expression in `allwords`, and numeric `pagenumber`. First and resumed engine reads returned five distinct hits each with partial coverage; receipt `docs/verification/granicus-native-search-2026-11-12.json`.

### Remaining research

- On the selected Superior ViewPublisher tenant, GET one RSS link and one older-year page; record exact feed URL/schema, date coverage and document/video MIME/redirect behavior. Provider candidate semantics, other tenants and full archive/catalog coverage remain unverified; the implemented search checks only Clip title/date metadata.
- The official MediaManager SDK article names Event creation, uploads and Agenda/Minutes operations but is behind customer support login. Obtain the readable version matching the configured product/version.
- Keep ViewPublisher, MediaManager, Legistar, Peak, Swagit and iQM2 separate; no authorized write account was supplied.

### Pagination contract

{
  "status": "partial",
  "details": "The selected ViewSearchResults.php Clip form uses numeric pagenumber and guarded continuation; the bounded first/resumed receipt returns five distinct hits per call. Publisher archive bounds, cross-tenant behavior and full catalog coverage remain unverified."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.

## F04 NovusAGENDA (`novusagenda`)

Official documentation status: inspected_with_recorded_limits; the current search result is not a documented machine API.
Account/tier: East Brunswick public page responded without credentials. Staff/test credentials were not supplied; no private access attempted.
Test environment: bounded public reads only. One supplied agenda PDF was fetched on 2026-11-12; no credentials or remote writes were used.

### Representative research observations

- https://ebps.novusagenda.com/agendapublic/: GET returned 124337 B HTML. The stateful form posts to `./`. Search fields include `ctl00$ContentPlaceHolder1$SearchAgendasMeetings$ddlDateRange`, `$radCalendarFrom`, `$radCalendarFrom$dateInput`, `$radCalendarTo`, `$radCalendarTo$dateInput`, `$ctl00` (meeting type), `$ctl01` (category), `$ctl02` (containing text) and the Search image control. Page-size control is `...$radGridItems$ctl00$ctl03$ctl01$PageSizeComboBox`. Carry current ASP.NET `__VIEWSTATE`, Telerik client state and returned session cookies; the current response’s Next Page `__doPostBack` target changes across the traversal. Cookie values were not saved.
- Form values 2026-08-11 through 2027-02-11 returned a 12-page item pager: 180 item rows at 15 rows/page. All page bodies and SHA-256 values are in outputs/provider-route-probes-2026-11-11/novus-eastbrunswick-page-01-of-12.body through page-12-of-12.body and novus-eastbrunswick-page-traversal-2026-11-11.json. The meeting grid displayed 11 rows.
- Item rows are `table[id*='radGridItems_ctl00'] tr.rgRow, table[id*='radGridItems_ctl00'] tr.rgAltRow`; meeting rows are `table[id*='radGridMeetings_ctl00'] tr.rgRow, table[id*='radGridMeetings_ctl00'] tr.rgAltRow`. Of 180 item rows, 75 had literal `Coversheet.aspx?ItemID=...&MeetingID=...` onclick targets (75 unique ID pairs); 105 rows had no such target, and no IDs were inferred.
- A separate stateful read-only POST for “Superintendent’s report” returned HTTP 200 HTML with zero item rows. This does not establish exact/phrase semantics or a complete empty result.
- 2026-11-12 follow-up: the saved postback response for a search candidate contained an ASP.NET date-validation error (“TO date must be after FROM date”) and no rows; no opaque form state was replayed. Visible form controls and MeetingView/Coversheet/DisplayAgendaPDF.ashx link shapes were recorded.
- The engine fetched one supplied DisplayAgendaPDF.ashx?MeetingID=996 link as application/pdf, 28,849,631 bytes, SHA-256 90644aacdb5f3fc7bf0d82deff93edb5f51d60d5226344d1871fd6246eaf0c03. This is one supplied agenda only; no Minutes or structured detail read.

### Remaining research

- The selected-window listing covers 12 pages/180 items and 11 meeting rows. One supplied agenda PDF has now been fetched. Successful native-search semantics, structured MeetingView/Coversheet retrieval and Minutes remain unverified; the saved postback error did not return rows.
- On this same tenant, establish date-window defaults, retained history and meeting-grid continuation. The receipt exhausts only the selected window; catalog/source completeness are false.
- No current machine create/update/upload route or authorized staff/test account was supplied; historical UI instructions are not API fields.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "The item pager was traversed for the displayed form values 2026-08-11 through 2027-02-11: 12 pages, 180 rows, 15 per page. Meeting grid showed 11 rows. Follow-up did not establish successful native search or meeting-grid continuation; retained-history and full-catalog bounds remain unknown."
}

### Authorization restrictions

- No credentials or remote writes were used in the 2026-11-11 research capture; no document bytes were downloaded.
- Preserve provider-issued IDs only when present in link targets; rows without linked IDs remain without IDs.
- Unknown search, retention and continuation behavior is incomplete, not unsupported.

## F05 CivicPlus Agenda and Meeting Management Select (`civicplus-select`)

Official documentation status: historical file-import article and authenticated UI guides inspected; no external REST contract verified.
Account/tier: public Lacey portal evidence only. Historical FTP credentials are project-lead supplied and were not available.
Test environment: documentation and public read-only observation; no FTP access or transfer.

### Representative research observations

- https://www.civicplus.help/meetings-select/docs/historical-imports (updated October 29, 2026): PDF/MP4 only; up to five PDFs plus one audio/video file per event/meeting. Filename stem `MeetingBody_MeetingType_FileType_MM_DD_YYYY`; explicit examples use `Agenda`, `Agenda Packet`, `Minutes`. Files are placed in the Imports FTP main folder, then a CivicPlus consultant processes, spot-checks and releases the import.
- Exact names in prose vary: `Packet` versus `Agenda Packet`, `Notice` versus `Notices`, and `Media` versus `Audio/Video`. Only the three filename examples establish exact input tokens in the page. It omits file extensions, component escaping rules and a historical FTP size ceiling.
- The article contradicts itself on host: `ftp://imports.civicclerk.com` in credential instructions and `ftp://important.civicclerk.com` in FileZilla instructions. Project-lead username/password were not supplied; no host probe or transfer occurred.
- Agenda packets are imported as indivisible PDFs; MP4 bookmarks/timestamps are not carried over. A separate UI upload-size page does not establish the historical FTP limits.

### Remaining research

- On the selected Lacey portal, capture the exact Events/OData request generated by date/type/keyword controls and one continuation response; existing evidence proves an event/file read, not search pagination.
- The exporter now prepares canonical Agenda, Agenda Packet, Minutes, Notice and Other PDFs plus Media MP4. The official-linked Filename Tester v3.5.9 classifies Notice/Notices as Notice, Packet/Agenda Packet as Agenda Packet, Media `.mp4` as Video and Other as Other; these results establish classifier behavior, not consultant/vendor acceptance. Confirm accepted filenames and post-import behavior with the consultant/vendor. MP4 codec/playability, captions and timestamp preservation remain unverified; ambiguous aliases Packet, Notices and Audio/Video remain rejected.
- Historical FTP host is contradictory; credentials, transfer, consultant processing and readback are absent. Authenticated create/update/upload routes remain account-gated.

### Pagination contract

{
  "status": "unverified",
  "details": "The historical import article documents named-file intake, not a paged catalog. Select public portal OData request and pagination remain unverified."
}

### Authorization restrictions

- The 2026-11-11 research capture made no remote writes or FTP connections and used no credentials or consultant contact; authorized test-tenant acceptance remains blocked pending supplied access.
- Do not use unrelated Select UI size limits as historical FTP acceptance limits.
- Vendor PDF optimization may change bytes; preserve local source hashes and do not promise post-import hash equality.

## F06 CivicPlus Agenda Center (`civicplus-agenda-center`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.effinghamcounty.org/AgendaCenter: selected year=2024/category=3 returned HTTP 200 HTML with 35 rows (2024-01-16 through 2024-12-03).
- A supplied ViewFile URL ending `?html=true` returned 2,481 bytes of `text/html` (SHA-256 4d84e2d105bf4e452065aa75f6d845cc7700a5722e6eafaa21c1d59c18f88690); it is HTML, not a PDF/binary-document result.
- Receipts: `docs/verification/civicplus-agenda-center-year-2024-2026-11-12.json` and `docs/verification/agendacenter-viewfile-html-2026-11-12.json`.
- https://www.cityofchino.org/AgendaCenter: Chino candidate access failure; No directly fetched content; no unsupported conclusion.

### Remaining research

- Other Effingham years/categories, continuation, previous-version links and actual binary/PDF routes remain unresolved; the observed `html=true` representation must not be counted as a PDF. Chino extraction failure is already recorded; do not add another tenant.
- Official CivicPlus material describes the staff agenda/item UI but supplies no external machine request/response or file-import schema. Obtain tenant-supported API/integration specification and authorized test account.
- If access is supplied, verify role/approval/visibility and duplicate/update/readback separately for meeting, item and file; no remote writes occurred.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "One selected year/category (2024/category 3) returned 35 rows. Continuation, other categories/years and full archive bounds remain unknown; ViewFile?html=true returned HTML, not PDF."
}

### Authorization restrictions

- SVG unsupported; PDF-only agendas do not accept structured items; item removal required before modification; approval/publishing rights.

## F07 Municode Meetings (`municode-meetings`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://meetings.municode.com/PublishPage/index?cid=EFFINGHAM&ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=1: Effingham Board of Commissioners; Initial page; do not assume p is numeric pagination.

### Remaining research

- Source now implements explicit-offset POST collection and GET meeting/item/multimedia capture on the documented support-gated dev origin. Only the multimedia `{meetingStructure:...}` response is schema-mapped; meeting/item/collection bodies remain raw partial captures with zero inferred normalized records.
- Collection offset is caller-supplied; page size, ordering, total/terminal condition and offset progression remain undocumented. Live request validation needs a support-issued token/account; none was supplied.
- The documented multimedia update is source-implemented and fixture-tested. Official examples demonstrate URL/timestamp/default/baseURL changes, but other enum/mutability constraints and update response/readback/version conflicts remain unverified without an authorized tenant.
- The inspected API page has no meeting/item create/update or document upload route; obtain applicable current support API documentation before coding those routes or treating omission as unsupported. No token was issued, and the test host is not a production host.
- Essential reaches end-of-life on 2027-06-30. Keep this product row separate from Select and Aha CMS.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "cid/ppid/p observed; p semantics unverified; older years may be outside product."
}

### Authorization restrictions

- Essential end-of-life June 30, 2027; preserve legacy input and IDs.
- Do not merge public/private packets or substitute Aha CMS API.

## F08 BoardBook (`boardbook`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://meetings.boardbook.org/public/organization/1807: Minneapolis public organization listing; Initial list; full archive pagination not tested.

### Remaining research

- Selected Minneapolis organization page supplied629meetings back to2010 without separate archive pager; bounded Agenda→PDF read now completed. Broader provider retention, detail relationships and complete catalog remain unverified; no new tenant/history survey implied.
- Quick Reference/custom-document guides describe Premier UI and report exports, not machine field payloads or import schema. Vendor-file import and external create/update/upload routes remain unverified.
- No authorized staff/test account was supplied for roles, API enablement, write/readback or conflict checks.

### Pagination contract

{
  "status": "observed_single_page_with_local_continuation",
  "details": "629meetings in selected organization HTML; no separate archive pager exposed. Existing local checkpoint/date bounds apply; no catalog completeness guarantee."
}

### Authorization restrictions


## F09 eSCRIBE (`escribe`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://pub-oakville.escribemeetings.com/meetingscalendarview.aspx?Expanded=Council: Public calendar and agenda/PDF/player links; admin host auth-blocked separately.

### Remaining research

- Calendar POST already implemented/proven; bounded Meeting.aspx HTML fetch completed and supplied FileStream PDF returned403 (correctly partial). No bypass/retry or complete agenda-item/catalog claim.
- Public native search source implementation and bounded first/page2/resume are verified with partial coverage. Provider full-text/exact matching semantics, broader document visibility and catalog completeness remain unknown; no saved metadata search is mislabeled native.
- The official product overview describes modules, not public API schemas. No customer API/import contract or authorized write tenant was supplied for meeting/item create/update/upload.

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.

## F10 Simbli (`simbli`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://simbli.eboardsolutions.com/index.aspx?S=36031063: Oneida public Simbli landing page; Extracted landing page does not expose actual meeting list.

### Remaining research

- Working public menu/listing and page2 now verified and source implemented. Supplied ViewMeeting.aspx returned HTML; its hydrated agenda/detail/document chain remains a bounded current-source contract follow-up. Body filtering/search/full-catalog semantics remain unverified.
- Reviewed current Simbli pages describe archive search and staff meeting/item/document workflows but publish no machine field schema. Obtain customer API specification before implementing writes or claiming absence.
- No authorized provider test tenant, staff credentials or tenant-specific write configuration was supplied.

### Pagination contract

{
  "status": "observed_and_source_implemented",
  "details": "First50 embedded rows; published POST /Services/api/GetMeetingListing uses current anonymous controls, RecordCount50 and RecordStart51,101,...; bounded opaque scoped cursor retains midpage position, seen IDs and private cookie state for15minutes in one engine process. No public full-catalog claim."
}

### Authorization restrictions


## F11 iCompass CivicWeb (`civicweb`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://csknowledgebase.civicweb.net/document/57754/: Milton staff guide hosted on CivicWeb knowledgebase; Tenant staff UI instructions not vendor API; deployment differences possible.
- https://ciindependenceor.civicweb.net/Portal/MeetingTypeList.aspx: Independence meeting-type listing; may be stale July 2025 content; not full catalog. One linked MeetingInformation.aspx?Id=11021 record was a City Council Work Session and supplied a completed print PDF (120,193 bytes, application/pdf; SHA-256 781943f47d7af1b250ee3c6f4b69b862feeb369ac829d2a66e851b3426348643). The document kind was not inferred as agenda/minutes. Receipt: `docs/verification/civicweb-supplied-document-2026-11-12.json`.

### Remaining research

- One MeetingInformation.aspx record and supplied print PDF have been captured. Full meeting-type archive, continuation, adjacent-date coverage and agenda/minutes classification remain unknown.
- The public product page/staff guide describe UI scheduling/document workflows but publish no machine schema. Obtain the tenant API/import specification and authorized write credentials before external create/update/upload.
- Do not derive write fields from labels such as Meeting Type, Description or auto-assigned item/file numbers.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "One explicit meeting detail and its supplied print PDF were fetched; full MeetingTypeList archive bounds and continuation remain unknown."
}

### Authorization restrictions


## F12 iQM2 (`iqm2`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://kentwa.iqm2.com/citizens/default.aspx: Kent IQM2 portal; Self/# placeholders not downloadable documents; no binary fetch.

### Remaining research

- On the existing Kent iQM2 tenant, follow one list/calendar entry to Detail_Meeting and FileOpen routes; capture date/body filters and older-record navigation. Pre-2007 records are reported elsewhere, not in this portal.
- Current Granicus/iQM2 help pages describe authenticated locations/types/meeting and streaming-media workflows, not an iQM2 external API. Get deployment-specific customer documentation/account enablement.
- No tenant API credentials, upload limits, write schema or write acceptance were supplied; do not reuse Legistar contracts.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Upcoming list plus Full Calendar/group filter; archive boundaries untested, pre-2007 Kent archive external."
}

### Authorization restrictions

- Preserve Scheduled/Cancelled; ignore self/# file placeholders; minutes may be embedded in following packet.

## F13 Granicus Swagit (`swagit`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Archive public without credentials; support article requires customer login. Swagit/MediaManager integration account prerequisites unverified."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://princetontx.new.swagit.com/views/261/: the selected archive capture maps 482 rows. GET /videos/search with q=Council returned 10 provider-ID rows on each of the first two pages; the page-2 request followed the supplied same-origin rel=next link and IDs were disjoint. Search query semantics remain unknown. Sound Search timestamp links were retained, not transcript text. Receipt: `docs/verification/swagit-native-search-page2-2026-11-12.json`.

### Remaining research

- The current archive capture maps 482 rows; only search pages 1 and 2 were fetched (10 provider-ID rows each). No third page or full archive boundary was established. The earlier player error remains separate from archive/search evidence.
- The public Search Archives request is now observed for q=Council on pages 1 and 2. Upstream query semantics remain unverified; exact matching is limited to returned title/date metadata, so this does not prove all source matches are returned.
- Official Swagit integration documentation is login-gated and describes PrimeGov/MediaManager ID integration, not a general write API. Exact create/update/upload methods require customer documentation and authorized access.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Selected archive capture maps 482 rows. Search pages 1 and 2 each returned 10 disjoint provider-ID rows; no third page or full catalog boundary was tested."
}

### Authorization restrictions

- No media playback, upload, API write, search submission or caption retrieval tested.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F14 SuiteOne Media (`suiteone-media`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public archive GET anonymous. Upload/update requires an authorized SuiteView Admin account; account tier not specified."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://vermilionoh.suiteonemedia.com/: root plus one supplied Older Meetings POST returned 328 meeting rows total; 17 older groups were reported, continuation retained, and coverage remains partial/truncated. The selected dates span 2022-01-25 through 2026-11-17. The one POST returned 52 parsed meetings. Other groups and document downloads are not established. Receipts: `docs/verification/suiteone-older-groups-2026-11-12.json` and `docs/verification/suiteone-older-group-request-2026-11-12.json`.

### Remaining research

- One Older Meetings group request and continuation checkpoint are now captured. Remaining groups and full history, plus separate event/agenda/packet/minutes MIME/redirect outcomes, remain unresolved.
- The official SuiteOne guide names WMV and Liberty *_content.HTML intake with asynchronous processing, but no exact bookmark HTML schema. Obtain an authorized vendor-produced example before completing that file export.
- Admin UI steps are documented; no machine write contract, account credentials or publication/readback test is available.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Root plus one Older Meetings group yielded 328 records with continuation retained; 17 older groups were reported. Remaining groups and full history are unresolved."
}

### Authorization restrictions

- Uploaded media requires processing before public visibility; do not report upload completion as publication.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F15 Granicus Peak (`peak`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://elkocounty.granicus.com/DocumentViewer.php?file=elkocounty_297e107d2b4284d01a905ef2af7c24f9.pdf&view=1: Elko public copy of vendor-authored Peak manual; Historical 2015-era examples/browser requirements; current 200 MB limit must be reverified; not current API.
- https://lowermerion.granicus.com/ViewPublisher.php?view_id=1: bounded capture returned 116 records dated 2025-10-08 through 2026-11-18, partial. One separately supplied PDF retrieval completed with SHA-256 19994b412b91e3b6a41f77a7999971d8396c3d5bffaeb74290954e39e62db4cc; detailed receipt serialization failed afterward and the fetch was not repeated. Receipts: `docs/verification/peak-lower-merion-capture-2026-11-12.json` and `docs/verification/peak-champ-supplied-artifacts-2026-11-12.json`.

### Remaining research

- The selected capture and one supplied PDF are now recorded. RSS schema, full archive continuation and other document/media outcomes remain unverified; the receipt serialization failure is preserved and was not repaired by repeating the fetch.
- The Elko Peak manual gives authenticated UI fields, attachment privacy values and a 200 MB limit, but no external route/payload. Machine create/update/upload, role permissions and readback need a supported API contract and authorized Peak account.
- Do not use ViewPublisher fields as write parameters or reuse MediaManager/Legistar contracts.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "The selected Lower Merion capture has 116 rows dated 2025-10-08 through 2026-11-18, partial; one supplied PDF completed separately. Full archive continuation is unknown."
}

### Authorization restrictions


## F16 Utah Public Notice Website (`utah-public-notice`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Reads public. Writes require Utah login and approved poster/owner rights for target Body; publish permission distinct from draft edit."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.utah.gov/pmn/sitemap/notice/1120627.html: GET 200; notice detail read. Contains body URL, title, start/end, agenda text, location, posted/edited dates, PDF attachment and /noticeical/1120627.ics link. Limits: One Body observed. Outbound UI field names not inferred from public display labels; attachment bytes not fetched.

### Remaining research

- On the existing Utah Public Notice site, submit bounded government/body/date/ZIP searches and capture continuation/result cap plus one notice document/iCalendar response; notice 1120627 is only one detail.
- Admin Help documents notice draft/publish and attachments as UI steps; no external API or import schema is published. Obtain a supported integration contract and authorized test account.
- Notice publication has legal timing/visibility consequences; future writes require explicit authorization and planned readback.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "No public search paging contract verified. Detail is one notice; per-notice iCalendar link is not a complete notice catalog."
}

### Authorization restrictions

- Notice writes affect legally consequential public postings. Only authorized synthetic/test Body writes permitted; none attempted.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F17 Destiny AgendaQuick (`destiny-agendaquick`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Yuma list public; staff publishing/editing requires authorized installation account. Hosted and client-installed deployment supported; no API credentials supplied."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://destinyhosted.com/frs/coonrapids.htm: GET redirects to /frs/fas/default.cfm?con=coonr26667. Provider-branded shell/version announcement only in extracted response. Limits: No usable meeting listing in this response; not a discovery success.
- https://public.destinyhosted.com/agenda_publish.cfm?id=98622: GET 200 after destinyhosted.com redirect. Meeting type/month/year filters; Previous/Next Period links with mt,get_month,get_year; agenda seq=1737; CHAMP video link. Search Agenda Items visible. Limits: Search not submitted; HTML/PDF attachment bytes and API not checked.

### Remaining research

- On Yuma’s current AgendaQuick page, follow Previous/Next Period for one adjacent month and another meeting type; inspect agenda sequence 1737 and its supplied attachment/video URLs.
- The public Keyword Search and Search Agenda Items controls have no captured successful query route/response. Verify method, matching and paging on this same tenant.
- Official feature copy describes staff scheduling/minute votes/uploads but no machine schema. No authorized credentials or vendor file-import contract were supplied.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Previous/Next Period explicitly observed; month/year and meeting-type coverage must be bounded. Not all tenants return same public shell."
}

### Authorization restrictions

- Public HTML/PDF export is not a vendor import contract. Roll call/votes are product features, not guaranteed structured fields in listing HTML.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F18 Town Hall Streams (`town-hall-streams`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Town archive public. Scheduling requires service account; tier/roles unknown."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townhallstreams.com/town.php?id=72: GET 200, 87,874 bytes; 132 embedded event rows parsed with partial status. Event 74003 detail returned 31,913 bytes of text/html and no supplied document links; HTML is not playable-stream evidence. Time-zone status stays unknown and history bounds remain unverified. Receipts: `docs/verification/town-hall-streams-capture-2026-11-12.json` and `docs/verification/town-hall-stream-detail-2026-11-12.json`.

### Remaining research

- The selected page already embeds 132 rows, and one supplied event detail is captured as HTML. No additional network group/page, PDF, agenda/minutes link or playable stream bytes were observed.
- The earlier player error and later completed HTML response are not media acceptance. Stream bytes and tenant retention remain unverified.
- Reviewed sources provide no public create/update/upload API or vendor import schema; provider/admin documentation is needed for write questions.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "132 embedded event rows were parsed from the selected page; no additional network continuation was observed. Long-term catalog/retention bounds remain unknown."
}

### Authorization restrictions

- No supplied captions/transcripts or direct playable media verified. Service statement 'no uploading' must not be reclassified as unavailable upload capability.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F19 TelVue (`telvue`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public playlists anonymous; Connect API requires client application access key + secret passphrase in custom headers, not Basic auth. Upload roles Contributor/Coordinator/Admin and account feature settings matter."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://videoplayer.telvue.com/player/WDZPS7GoaEEQAF8v5_qEOE_Kj--KiACH/categories/574?showtabssearch=false: GET 200; provider-owned demonstration/training player. Categories/media links and 14 training videos visible, including Uploads and Creating Playlists. Limits: Provider training content, not municipal meeting fixture.
- https://videoplayer.telvue.com/player/dQtoDvlZYDOtqaf7eRn9z2lb1Nb6EZzu/playlists: GET 200. Named City Council playlist (87 videos at observation), committee playlists and stable player/playlist/media paths visible. Limits: Playlist media enumeration, paging, video playback and search were not tested.

### Remaining research

- Documented Connect v2 reads are GET /api/v2/media[/{id}], /videos and /playlists[/{id}]. The source fetch adapter now implements explicitly requested account reads; live calls remain blocked because no Connect key/secret was supplied.
- Published pages show example JSON envelopes/fields but omit filters, pagination/cursor, caps and rate limits. Record these from a supplied authorized account response/current guide; do not claim catalog completeness.
- The upload article documents UI drag-and-drop only. No REST mutation route was found in the cited v2 pages; other write paths remain unresolved, not unsupported. CloudCast MRSS CAPTCHA and HyperCaster are separate.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "API examples do not specify paging, filtering or limits; playlist counts require verification against enumerated media, not assumed exhaustive single page."
}

### Authorization restrictions

- No authenticated API requests. Keep TLS verification even though old sample curl uses -k. HyperCaster API not assumed applicable. Legacy MRSS doc CAPTCHA-blocked.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F20 CHAMP (`champ`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public player metadata observed; CHAMP login required for UI writes; role/tier and API credential contract unknown."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- Public player JS https://play.champds.com/_COMMON/js/cds.event.js?1794445126 derives GET https://playapi.champds.com/{CustomerAccessID}/event/{EventID} and expects JSON.
- https://playapi.champds.com/lakezurichil/event/164 and https://playapi.champds.com/yumacoaz/event/657: two bounded detail reads remain complete with original fields preserved (14 agenda items each; Lake Zurich 6 documents, Yuma 0; one recording each); catalog_complete=false. Follow-up Lake Zurich supplied PDF completed (1,933,081 bytes, application/pdf) and player HTML completed, while a separate supplied HLS/media fetch was partial. The public client composes VOD2 first, otherwise service 2048 or 8 plus URLFilename; this is URL-selection evidence, not playable-stream proof. Receipts: `docs/verification/champ-detail-2026-11-11.json`, `docs/verification/champ-supplied-links-2026-11-12.json`, `docs/verification/peak-champ-supplied-artifacts-2026-11-12.json`.

### Remaining research

- Two public event detail GETs are engine-receipted, but no public event index/list or paging route is established. Continue only through existing tenant links if an index is visibly exposed.
- One supplied Lake Zurich PDF is now fetched; a separate supplied HLS/media attempt remains partial and player HTML is not playback. Do not generalize these results to all attachments or events; Yuma reports no media.
- CHAMP Help documents staff event/media/PDF workflows, not machine writes. API codecs, account roles and write/readback remain unverified without authorized credentials.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Public event detail is engine-live-read-verified on two existing tenants; no public catalog/list or pagination route found. Admin help says authenticated Events list has 15/page; that is not a public JSON pagination contract."
}

### Authorization restrictions

- Do not ingest unpublished JSON through baseline public path. Supplied media/captions only; player/download button not proof playable media.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F21 Hyland OnBase Agenda Online (`onbase`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/: current root maps 30 rows. A supplied Meetings response returned HTTP 200 but mapped zero; a guarded search POST was rejected before redirect details/results. One supplied `.pdf` link returned HTTP 200 `text/html`, 3,719 bytes, without PDF magic; corrected engine result is partial and retains the meeting. It is not a PDF success or unsupported-route finding. Receipts: `docs/verification/onbase-public-search-2026-11-12.json` and `docs/verification/onbase-pdf-mismatch-2026-11-12.json`.

### Remaining research

- The current bounded follow-up covered root, Meetings response, guarded search attempt and one supplied Downloadfile route. Search results, redirect target/method and adjacent-date/archive completeness remain unresolved; the supplied `.pdf` response is HTML, not a PDF.
- Hyland Agenda Foundation 25.1 guidance is version/installation-scoped. Identify tenant deployment/version and entitlement before applying API or write operations to Agenda Online.
- No authorized deployment-matched staff/test account or integration contract was supplied for create/update/upload.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Current root mapping yielded 30 rows; Meetings response mapped zero. Search redirect was not followed, so archive/year/search continuation and completeness remain unknown."
}

### Authorization restrictions


## F22 Laserfiche WebLink (`laserfiche-weblink`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"WebLink cookie/browser session may be required; saved capture baseline remains.","outbound":"Cloud OAuth v2 scopes AND principal ACL; self-hosted API deployment/version separate. No access supplied."}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://miweblink.metro-inet.us/sapublic/Browse.aspx?startid=207&cr=1: cookie_blocked
- https://weblink.ci.northfield.mn.us/WebLink/Browse.aspx?dbid=0&startid=92&row=1&cr=1: cookie_blocked

### Remaining research

- Guarded offline-Chrome WebLink session is implemented with PublicTransport routing; synthetic/browser checks are separate from live acceptance. Current Boulder request is blocked at the cross-origin redirect boundary and Louisville returns HTTP 403. No catalog was obtained; both tenant contexts have been used.
- Repository v2 child-list GET is implemented from the official route and supports returned nextLinks, but live reads need a supplied repository.Read OAuth tenant token; no account credentials were supplied.
- Resolve the official ImportUploadedParts multipart-vs-JSON and CreatePages image/text pairing conflicts from authoritative documentation or an authorized sandbox. Do not infer Repository API identity/access from WebLink repository name.

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.
- No DELETE or empty all-page replacement; move/copy/rotate and general repository administration not part of connector write scope.

## F23 TownCloud (`towncloud`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Published agenda detail public. Editing/publication requires authorized TownCloud account; API access and tier unknown."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://woodfordvt.org/: GET 200. Recent agendas grouped by body, links to /go/woodford-vt/agendas/{id} and PDF document links. Limits: Recent-only homepage is not full agenda table or exhaustive discovery.

### Remaining research

- On the existing Woodford public agenda and detail, inspect the actual list/table request source and one body/year control; the current detail shows items and document links only.
- The exact list JSON query, next-page token, retained history and public search request remain unverified; record the actual request/response before claiming discovery completeness.
- No external write route or vendor file-import schema is in reviewed evidence; obtain tenant-supported documentation and an authorized account before write work.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Homepage recent groups only; table JSON request method, pagination/search/date filtering and full history remain unverified."
}

### Authorization restrictions

- Downloadable packet output does not establish a TownCloud import file format. Do not infer table JSON write endpoint.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F24 Digital Towpath (`digital-towpath`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Demo reads public; dashboard required for administration. Customer credentials and account roles not supplied."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townbrutus.digitaltowpath.org:10148/content/MinuteCategories/View/1: GET redirected to digitaltowpathny.gov:10148/content/404, HTTP 200. Provider-branded File Not Found page, search and Minutes navigation links. Limits: Requested category was not obtained; HTTP 200 cannot mean successful meeting fetch. Legacy/new templates may differ.

### Remaining research

- On the selected Digital Towpath demo, follow Other Years from Meetings and Minutes and capture date/category continuity, one meeting detail and one PDF URL/MIME. The old Brutus category URL is a moved path, not a current executable route.
- Demo search query semantics and archive bounds remain unknown; HTML success does not establish PDF extraction or attachment availability.
- The indexed Meetings Module guide describes staff entry without a machine payload. No vendor API/import contract or test account was supplied.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Demo Other Years navigation observed. Legacy Brutus category URL moved; no numeric paging or complete archive verified."
}

### Authorization restrictions

- PDF manual extraction blocked; indexed excerpts insufficient to claim upload/update API. Demo inconsistent minutes dates must not silently override page dates.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F25 ClerkBase (`clerkbase`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://clerkshq.com/southkingstown-ri: South Kingstown ClerkBase public portal; Shell/help extracted, not actual meeting-document tree or search results.

### Remaining research

- On the sole South Kingstown public context, follow the public tree and one Quick/Advanced Search link if exposed; retrieve one meeting-document/video link and preserve query and identity details.
- Current vendor pages distinguish ClerkBase Meeting Center/OnBoardGOV from ClerkMate. Obtain a current ClerkBase-specific API/import contract before implementing writes.
- No staff/API credentials supplied; roles, page caps, write permissions and readback remain gated. Do not substitute another product route.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Folder/tree and search-result paging unknown."
}

### Authorization restrictions


## F26 Municipality-published calendar (iCalendar) (`first-party`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Observed feed public. Publication/admin credentials and hosting CMS are separate, unknown contracts."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.logan-twp.org/events/: GET 200 redirected from /municipal-calendar/. Municipal meeting calendar has iCalendar webcal subscription and HTTP Export .ics links. Limits: Calendar page includes non-meeting events; explicit source/type bounds required.

### Remaining research

- On the existing Logan Township feed, compare /events/month/?ical=1 across one adjacent month and inspect UID, recurrence, timezone and updated-event behavior; current saved response contains five events.
- RFC 5545 defines event serialization, not universal feed paging or a write endpoint. Establish the published feed horizon/update behavior; do not infer mutation from subscription URLs.
- Keep neutral iCalendar export separate from writing to a municipality calendar; no provider-specific import/write contract is supplied.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "iCalendar defines no universal pagination. Tenant export window is bounded/implementation-specific; observed month endpoint omitted past early-month events."
}

### Authorization restrictions

- No generic calendar-host write support. METHOD:PUBLISH and RFC property names do not grant upstream create/update/upload. Preserve floating/all-day/timezone/recurrence distinctions.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F27 Wistia (`wistia`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://fast.wistia.com/embed/medias/26sk4lmiix.json: Public official demonstration media JSON observed; not municipal live meeting acceptance.

### Remaining research

- Core now implements authenticated media-detail and supplied-caption-list/per-language GETs plus native search. Complete account-level reads only after a trusted Wistia token and selected account are supplied; none was supplied.
- /modern/search is capped at 100 primary and 100 transcript-only candidates with no cursor and provider-defined exact/phrase candidate semantics. Local exact checks cover returned metadata/excerpts, not full transcripts.
- Resolve account-tier limits and media replacement/swap behavior before those paths are claimed. Keep upload/import, media metadata, caption create/update and edits permission scopes separate; no remote writes occurred.

### Pagination contract

{
  "status": "documented_with_conflict",
  "evidence_ids": [
    "wistia-list"
  ],
  "details": "page/per_page offset OR cursor[enabled]/before/after, never combine page/cursor. Cursor sort_by description permits id/created, but enum excludes id; shared unambiguous supported sort value created. Numeric per_page bounds not stated in inspected schema."
}

### Authorization restrictions

- Research boundary on 2026-11-11: read-only public captures. The resumed plan authorizes supported writes only on an explicitly authorized test tenant; no authorized test tenant or credentials have been supplied, so live acceptance remains access-blocked. Procurement and outreach remain unauthorized.
- Unverified and access-blocked are incomplete, not unsupported.
- No caption purchasing or ASR/transcription generation authorized.
- Official older embed guide cautions audio/Channels,modern schemas include audio types; feature/version mismatch needs validation rather than unsupported claim.

## F28 Boardable (`boardable`)

Official documentation status: UI create/edit/upload/public-page instructions inspected; no vendor-published external API or import contract established. The public listing API route below is observed in the rendered client and engine, not documented as a supported integration.
Account/tier: public VCCCD listing accessed without credentials. No Boardable staff/test account or credentials were supplied; no private account access or writes were attempted.
Current authorization/access (2026-11-12): the full plan authorizes test-tenant acceptance, but no Boardable test tenant or credentials are available. Provider write acceptance is NOT_RUN/access-blocked; no arbitrary public-city data was mutated.

### Bounded public-list observations

- The existing VCCCD organization root and `/meetings` page resolve the numeric public `SiteId` by matching the organization slug in rendered `__NUXT_DATA__`.
- The rendered public client requests `GET https://app.boardable.com/api/public-sites/meetings` with `SiteId`, `count=10`, blank `search/group/status`, `sort=asc`, `upcoming=true|false`, and `page`. The captured `links.next` advances the same mode to the next page.
- Saved page 1 and page 2 each contain ten rows with numeric provider IDs; their ID sets are disjoint. The engine receipt exercised `upcoming=true` through two pages, returning 15 first-call records and five distinct resumed records. Both calls returned partial status without errors. The provider-reported total is 150; full catalog completion is not claimed.
- Captured rows supply title, description, start/end date strings, timezone literals, groups and published-material flags. The implementation retains the exact original row and page capture. `description` is not normalized as governing-body `body`; timezone values are not converted.
- The listing does not supply agenda/document/media links. Existing saved detail parsing remains the baseline behavior; the new discovery path does not claim live detail or document retrieval.
- Receipt: `docs/verification/boardable-public-discovery-2026-11-12.json`. Saved response fixtures: `tests/fixtures/boardable-discovery/page-1.json` and `page-2.json`; the sanitized landing fixture omits expiring signed asset URLs.

### Remaining research

- The live engine read covered only VCCCD `upcoming=true` pages 1-2 and one page-offset resume. `upcoming=false` has fixture coverage only; the provider-reported total 150 and full listing/catalog remain unexhausted.
- The public client/API request is observed, not a published supported Boardable integration contract. Version stability, rate limits, native search semantics and date-query semantics remain unverified; this implementation sends blank search and filters returned source dates locally.
- Body filters remain unknown because the listing's `description` field is not proven equivalent to a governing body. Preserve timezone literals and the earlier detail-versus-landing time display discrepancy.
- Direct detail retrieval and one supplied agenda/minutes/document download with MIME, redirect and exact-byte/hash evidence remain unverified. Listing flags that materials are published do not provide their links or prove public download access.
- Official guides describe UI create/edit and public-page upload, not external API/import fields. Notification, visibility and approval effects need an authorized account/manual. No test tenant/credentials were supplied; create/update/upload and readback acceptance remain access-blocked, not unsupported.

### Pagination contract

{
  "status": "observed_bounded_public_client_route; live_engine_partial",
  "details": "The rendered client uses SiteId from matching public organization state and GET /api/public-sites/meetings with count=10, blank search/group/status, sort=asc, upcoming mode and page. Same-mode links.next is validated. Live engine evidence covered upcoming=true pages 1-2 and resumed an offset; past mode is fixture-only. The provider total was not exhausted and full catalog completeness is false."
}

### Authorization restrictions

- Private document upload is not public publication.
- Invited-meeting edits send mandatory notifications.
- No arbitrary public-city writes; use an authorized Boardable test tenant when credentials are supplied.
- Keep the explicit PST versus unspecified landing-time display discrepancy.

## F29 gWorks FrontDesk (`gworks`)

Official documentation status: inspected with recorded limits; some indexed-only/login or extraction-blocked material
Account/tier: public city JSON read observed; login/admin writes remain separate. Galena UI showed login disabled at the earlier observation; API credentials and roles remain unknown.

### Bounded public observations

- Current Galena source: `GET https://files.frontdeskgworks.com/city/1117/cms/data.json` returned HTTP 200 `application/json`, 49,618 bytes. The engine parsed the one response as 153 meetings (153 `agenda_fl=true`, 142 `minutes_fl=true`), date span 2021-01-05 through 2026-06-01. It returned `partial`, with one page, no errors and no truncation because catalog completeness is unknown. Receipt: `docs/verification/gworks-galena-listing-2026-11-12.json`; raw response and row summary are under `outputs/gworks-followup-20261112/`.
- Existing city-1311 capture row 5017 (`agenda_fl=true`) used the baseline-derived `GET https://api.gworks.cloud/cms/public/city/1311/agenda/pdf/5017/`. The engine resolved it and retrieved one 5,211-byte PDF object (`application/octet-stream`, `%PDF-` signature, SHA256 `6b9d4bc7967dfd2f0d695113f5e6e2fbf9892f9d37b9f6a7dc429751ec483037`), without a redirect. Receipt: `docs/verification/gworks-city-1311-agenda-fetch-2026-11-12.json`.
- Galena row 4195 has `minutes_fl=true`; `GET https://api.gworks.cloud/cms/public/city/1117/minutes/pdf/4195/` returned a resolver-ready response, but the guarded signed-object GET returned HTTP 403 `application/xml` (543 bytes, SHA256 `6667a8b825cdfaab782d382a398e8000b848bab4d343c860f0d5bf174e8f045d`). The engine returned `partial`/`attachment_unavailable` and retained the citation. This is one document access failure, not evidence the route or provider capability is unsupported. Receipt: `docs/verification/gworks-galena-minutes-fetch-2026-11-12.json`.
- Signed transfer URL paths and query values were not saved. The successful read used explicit `download_origins` for the resolver API and the signed origin observed from that resolver.

### Remaining research and limits

- The current city JSON is one static public listing response; no continuation token or separate meeting-detail URL was observed. Provider-wide catalog completeness and successful retrieval of every flagged document remain unverified.
- Retained history, update frequency and maximum response payload remain unknown; a single response cannot establish them. Additional repeated sampling is optional and is not required for this bounded research result.
- The FrontDesk builder describes staff UI, not an external write schema. No vendor API or authorized test credentials were supplied; writes remain unaccepted/access-blocked.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "One current Galena response returned 153 rows in a 49,618-byte static JSON body. No continuation token was observed in that response; full catalog, retained history, update frequency and maximum payload remain unknown."
}

### Authorization restrictions

- Keep cancelled titles/status indicators. Public city JSON fields and PDF routes are not writable API fields.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.

## F30 Diligent BoardDocs (`boarddocs`)

Official documentation status: current BoardDocs product/support materials inspected; historical official-hosted proposal surfaced through public search indexing; no current API/feed specification found.
Account/tier: the Colorado public shell was previously extracted but its latest unauthenticated GET returned 403. Las Positas evidence is a staff workflow guide, not a public API. No staff/test credentials were supplied.
Test environment: two bounded tenant contexts only; no remote writes or private access.

### Representative research observations

- Current Diligent BoardDocs page says BoardDocs remains supported for existing customers and describes search, agendas and document/minutes management, but gives no machine endpoint or payload.
- Official-hosted 2017 BoardDocs LT proposal (https://go.boarddocs.com/pa/lewi/Board.nsf/files/AU2Q6567B2FC/%24file/BoardDocs%2006%2008%2017.pdf) is visible in search-indexed text and says subscribers could access public data through RSS/XML. Direct PDF open returned 403. The proposal supplies no feed URL, request/response fields, pagination, permissions or current product-tier applicability.
- https://www.laspositascollege.edu/gv/assets/docs/INSTRUCTIONS%20-%20Submitting%20Agenda%20Items%20-%20Final.pdf: tenant staff guide documents Meeting, Category, Subject, Access, Recommended Action, Approval Tree, Public Content and Public Files UI labels, with submit/approval constraints. These are UI labels, not request keys.
- https://go.boarddocs.com/co/cde/Board.nsf/Public: earlier extraction saw a branded shell and print controls without dynamic meeting rows; latest bounded direct unauthenticated GET returned HTTP 403. Do not bypass or infer unsupported from this result.

### Remaining research

- Two bounded BoardDocs contexts are used: Colorado direct GET currently returns HTTP 403, and the other evidence is a staff-guide document. Do not probe a third tenant. Capture an exact RSS/XML URL only if a current public link appears in either existing context; the 2017 proposal itself has no route/schema.
- Current Diligent BoardDocs materials give features but no API/search request schema. Current tier applicability, public catalog access and the 403 path remain unresolved pending supported endpoint/access evidence.
- No authorized BoardDocs non-production account supplied for role/approval, create/update/upload, readback or conflict checks.

### Pagination contract

{
  "status": "unverified",
  "details": "Historical 2017 proposal makes a product-level RSS/XML claim but gives no route or page contract. One Colorado shell GET returned 403; the second tenant context is a staff PDF. No current public meeting catalog or pagination contract was verified."
}

### Authorization restrictions

- Stay within the two inspected tenant contexts; do not test a third tenant.
- Keep baseline unencrypted printed numbered-PDF input; a JS shell is not equivalent.
- Do not substitute Diligent Community/Boards APIs.
- Respect post-approval edit lock and public/private visibility.

## F31 Tyler Meeting Manager (`tyler-meeting-manager`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Ector public calendar anonymous. Staff functions need authorized Tyler account and configured workflow; API tier/access unknown."}
Test environment (2026-11-11 bounded research snapshot; not current permissions): {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://cityofmurraycityuttmmapp.tylerhost.net/7452prod/tylermm/calendar/: prior FetchUrl extraction service HTTP 500; public URL found but no calendar response verified. This is not proof of tenant unavailability.
- https://ectorcountyclerktxtmmapp.meetingmanager.tylerapp.com/46612prod/tylermm/calendar/: direct GET returned 1403-byte SPA shell; public bundle provides tcmURL and POST meetingInformation/getMeetingInformationByDate with JSON `{startDate,endDate,meetingTypeIds}`, dates MM/DD/YYYY, no type filter [-1]. Nov 9-15 and Nov 1-30, 2026 returned HTTP 200 `[]`; no nonempty row schema. Captures/hashes in outputs/provider-route-probes-2026-11-11.

### Remaining research

- The Ector bundle exposes POST /tylermmcalendar46612prod/meetingInformation/getMeetingInformationByDate with JSON startDate/endDate/meetingTypeIds (MM/DD/YYYY; [-1] all types). The added 2025 historical query returned HTTP 200 and `[]` (2 bytes); all observed ranges are empty, so record schema/paging cannot yet be established.
- A nonempty public result on Ector is the next executable dependency before validating record fields, agenda/minutes/media links, status fidelity and archive completeness. The other bounded Murray context had a fetch-extraction failure; no third tenant.
- Official Tyler product features describe staff scheduling, item/document, minutes and video workflows but no machine write/import schema. No authorized credentials/test tenant supplied.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Public Ector client bundle exposes a date-range JSON query; two bounded Nov 2026 requests returned empty arrays. Successful nonempty response, JSON record fields, date bounds, pagination and archive completeness remain unverified."
}

### Authorization restrictions

- Baseline source skips cancelled/adjourned records and derives agenda item ids by position; new schema must preserve statuses and explain identity derivation rather than advertise baseline as full fidelity.
- As of the 2026-11-11 research capture, no provider test tenant/credentials were supplied and no live writes were performed. The resumed full plan authorizes supported writes only against an explicitly authorized test tenant; arbitrary public-city mutations, procurement and outreach are not authorized.
