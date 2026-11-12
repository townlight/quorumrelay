# Remaining provider research and access gaps

All operations remain mandatory where exposed in the bounded domain. Unknown is not unsupported. No credentials, live writes or new provider acceptance were supplied.

## F01 Legistar (`legistar`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"Some clients public; others token query required. Tenant policy controls access.","outbound":"Write credential scope and authorized test tenant not supplied."}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://webapi.legistar.com/v1/olympia: One Events result fetched publicly; flattened extractor output is not raw JSON acceptance.

### Remaining research

- No authorized write credential or test tenant was supplied; write token scope, tenant entitlement and field permissions remain unverified
- EventRowVersion conflict semantics and idempotency not established
- Vote and RollCall POST/PUT under EventItems are documented, with required PersonId and ValueId fields; tenant value IDs, permission scope, accepted enum values and readback remain unverified
- Other in-scope meeting-media write surfaces in Help still need systematic endpoint review; no unsupported conclusion
- Vendor-file import format unverified
- Vote and RollCall entity/field contracts are recorded in inventory.json and provider-api-contracts.json from the official v1 endpoint pages; they are documented contracts only, not accepted live writes.

### Pagination contract

{
  "status": "documented",
  "evidence_ids": [
    "legistar-paging"
  ],
  "details": "$top/$skip, max1000; stable EventId order/keyset checkpoint for mutable catalogs; ge lower/lt upper EventDate examples."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.

## F02 PrimeGov (`primegov`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://reno.primegov.com/public/portal: Search/filter UI fetched publicly; no catalog-completeness test.

### Remaining research

- Official machine create/update/upload/import contracts and account tiers unverified
- Public meeting-list endpoint request/pagination semantics must be proven separately
- Portal search UI does not prove usable native-search API

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.

## F03 Granicus (`granicus`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townofsuperior.granicus.com/ViewPublisher.php?view_id=2: Public listing with meeting rows and links.

### Remaining research

- Official API/import/export documentation
- At most two public tenants where available
- Explicit entity/field mappings and supported create/update/upload routes
- Credential/account-tier and readback/conflict semantics

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.

## F04 NovusAGENDA (`novusagenda`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://ebps.novusagenda.com/agendapublic/: direct GET HTTP 200 HTML, 124337 B, SHA256 6423712a99fed083a971b148d5f13b0c3545cf7c62489ca998bb2656b4a7bb9a. Stateful ASP.NET search POST to ./ for "Superintendent's report" returned HTTP 200 HTML, zero item rows, SHA256 b5e7fd2fc21a76650ec9682204ff0a2f7f87add1e698a772f084b67a384d01f7. Raw captures are in outputs/provider-route-probes-2026-11-11. Form controls include dates, type, category, containing text and search; not a JSON API.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Landing GET showed meeting/item grids; prior bounded scan reported 180 items across 12 pages and item page-size controls 10/15/20/50. No paging traversal; one query returned zero results, leaving semantics and coverage unresolved."
}

### Authorization restrictions


## F05 CivicPlus Agenda and Meeting Management Select (`civicplus-select`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://laceywa.portal.civicclerk.com/event/1077/files: Public published agenda/items observed.

### Remaining research

- Exact Events/search/write API documentation, auth and pagination
- Historical FTP host typo and project-specific permitted filename labels
- UI media/caption/transcript upload contract and feature permissions

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.
- Historical-import host conflict requires clarification; no FTP attempted.
- Source PDF bytes may change through vendor optimization; preserve local original/capture, do not promise upstream byte equality.

## F06 CivicPlus Agenda Center (`civicplus-agenda-center`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.effinghamcounty.org/AgendaCenter: Effingham Agenda Center Archive; Initial archive page; year/filter requests and binary downloads untested.
- https://www.cityofchino.org/AgendaCenter: Chino candidate access failure; No directly fetched content; no unsupported conclusion.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Year navigation/View More observed; page/date/search request parameters unknown."
}

### Authorization restrictions

- SVG unsupported; PDF-only agendas do not accept structured items; item removal required before modification; approval/publishing rights.

## F07 Municode Meetings (`municode-meetings`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://meetings.municode.com/PublishPage/index?cid=EFFINGHAM&ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=1: Effingham Board of Commissioners; Initial page; do not assume p is numeric pagination.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

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
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://meetings.boardbook.org/public/organization/1807: Minneapolis public organization listing; Initial list; full archive pagination not tested.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Type/committee controls; default 13-month separate archive documented; full traversal unknown."
}

### Authorization restrictions


## F09 eSCRIBE (`escribe`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://pub-oakville.escribemeetings.com/meetingscalendarview.aspx?Expanded=Council: Public calendar and agenda/PDF/player links; admin host auth-blocked separately.

### Remaining research

- Official API/import/export documentation
- At most two public tenants where available
- Explicit entity/field mappings and supported create/update/upload routes
- Credential/account-tier and readback/conflict semantics

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.

## F10 Simbli (`simbli`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://simbli.eboardsolutions.com/index.aspx?S=36031063: Oneida public Simbli landing page; Extracted landing page does not expose actual meeting list.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Unknown; actual list not obtained."
}

### Authorization restrictions


## F11 iCompass CivicWeb (`civicweb`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://csknowledgebase.civicweb.net/document/57754/: Milton staff guide hosted on CivicWeb knowledgebase; Tenant staff UI instructions not vendor API; deployment differences possible.
- https://ciindependenceor.civicweb.net/Portal/MeetingTypeList.aspx: Independence meeting-type listing; May be stale July 2025 content; not full catalog.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Overview only three meetings/body; detail/type navigation required; continuation unknown."
}

### Authorization restrictions


## F12 iQM2 (`iqm2`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://kentwa.iqm2.com/citizens/default.aspx: Kent IQM2 portal; Self/# placeholders not downloadable documents; no binary fetch.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

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
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://princetontx.new.swagit.com/views/261/: GET 200; archive rows and links visible. Body/year archives expose title, date, duration, /videos/{id} and /videos/{id}/agenda links. Search Archives control visible. Limits: Player reported HLS playlist request error; media playback and search submission not tested.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Body/year sections observed; page/API pagination, caps and historical completeness unverified.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Body/year sections observed; page/API pagination, caps and historical completeness unverified."
}

### Authorization restrictions

- No media playback, upload, API write, search submission or caption retrieval tested.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F14 SuiteOne Media (`suiteone-media`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public archive GET anonymous. Upload/update requires an authorized SuiteView Admin account; account tier not specified."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://vermilionoh.suiteonemedia.com/: GET 200; upcoming/past meeting tables read. Tables grouped by category/year expose /event/?id=, agenda aid, packet apid, minutes mid download links. Search/date/category controls and Older Meetings links visible. Limits: Older Meetings lazy-load and search requests not exercised; document links observed, not downloaded.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Older Meetings controls indicate additional history; loading endpoint, page size and completeness need verification.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Older Meetings controls indicate additional history; loading endpoint, page size and completeness need verification."
}

### Authorization restrictions

- Uploaded media requires processing before public visibility; do not report upload completion as publication.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F15 Granicus Peak (`peak`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://elkocounty.granicus.com/DocumentViewer.php?file=elkocounty_297e107d2b4284d01a905ef2af7c24f9.pdf&view=1: Elko public copy of vendor-authored Peak manual; Historical 2015-era examples/browser requirements; current 200 MB limit must be reverified; not current API.
- https://lowermerion.granicus.com/ViewPublisher.php?view_id=1: Lower Merion public ViewPublisher; First extraction HTTP 500, retry succeeded; no submitted search or binary downloads.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Upcoming/archive/RSS observed; full continuation unknown; ViewPublisher alone not unique Peak fingerprint."
}

### Authorization restrictions


## F16 Utah Public Notice Website (`utah-public-notice`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Reads public. Writes require Utah login and approved poster/owner rights for target Body; publish permission distinct from draft edit."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.utah.gov/pmn/sitemap/notice/1120627.html: GET 200; notice detail read. Contains body URL, title, start/end, agenda text, location, posted/edited dates, PDF attachment and /noticeical/1120627.ics link. Limits: One Body observed. Outbound UI field names not inferred from public display labels; attachment bytes not fetched.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- No public search paging contract verified. Detail is one notice; per-notice iCalendar link is not a complete notice catalog.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "No public search paging contract verified. Detail is one notice; per-notice iCalendar link is not a complete notice catalog."
}

### Authorization restrictions

- Notice writes affect legally consequential public postings. Only authorized synthetic/test Body writes permitted; none attempted.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F17 Destiny AgendaQuick (`destiny-agendaquick`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Yuma list public; staff publishing/editing requires authorized installation account. Hosted and client-installed deployment supported; no API credentials supplied."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://destinyhosted.com/frs/coonrapids.htm: GET redirects to /frs/fas/default.cfm?con=coonr26667. Provider-branded shell/version announcement only in extracted response. Limits: No usable meeting listing in this response; not a discovery success.
- https://public.destinyhosted.com/agenda_publish.cfm?id=98622: GET 200 after destinyhosted.com redirect. Meeting type/month/year filters; Previous/Next Period links with mt,get_month,get_year; agenda seq=1737; CHAMP video link. Search Agenda Items visible. Limits: Search not submitted; HTML/PDF attachment bytes and API not checked.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Previous/Next Period explicitly observed; month/year and meeting-type coverage must be bounded. Not all tenants return same public shell.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Previous/Next Period explicitly observed; month/year and meeting-type coverage must be bounded. Not all tenants return same public shell."
}

### Authorization restrictions

- Public HTML/PDF export is not a vendor import contract. Roll call/votes are product features, not guaranteed structured fields in listing HTML.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F18 Town Hall Streams (`town-hall-streams`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Town archive public. Scheduling requires service account; tier/roles unknown."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townhallstreams.com/town.php?id=72: GET 200. Upcoming and Previous Events grouped by year/month or meeting type; event title, date, time and EST label; stream.php?location_id=72&id=... links. Limits: EST label even on summer events must not silently become reliable DST offset. Completeness beyond retained history unknown.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Year/month and meeting-type groups observed; no paging API or long-term completeness verified. Advertised one-year retention is a service claim, not universal tenant cutoff.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Year/month and meeting-type groups observed; no paging API or long-term completeness verified. Advertised one-year retention is a service claim, not universal tenant cutoff."
}

### Authorization restrictions

- No supplied captions/transcripts or direct playable media verified. Service statement 'no uploading' must not be reclassified as unavailable upload capability.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F19 TelVue (`telvue`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public playlists anonymous; Connect API requires client application access key + secret passphrase in custom headers, not Basic auth. Upload roles Contributor/Coordinator/Admin and account feature settings matter."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://videoplayer.telvue.com/player/WDZPS7GoaEEQAF8v5_qEOE_Kj--KiACH/categories/574?showtabssearch=false: GET 200; provider-owned demonstration/training player. Categories/media links and 14 training videos visible, including Uploads and Creating Playlists. Limits: Provider training content, not municipal meeting fixture.
- https://videoplayer.telvue.com/player/dQtoDvlZYDOtqaf7eRn9z2lb1Nb6EZzu/playlists: GET 200. Named City Council playlist (87 videos at observation), committee playlists and stable player/playlist/media paths visible. Limits: Playlist media enumeration, paging, video playback and search were not tested.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- API examples do not specify paging, filtering or limits; playlist counts require verification against enumerated media, not assumed exhaustive single page.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "API examples do not specify paging, filtering or limits; playlist counts require verification against enumerated media, not assumed exhaustive single page."
}

### Authorization restrictions

- No authenticated API requests. Keep TLS verification even though old sample curl uses -k. HyperCaster API not assumed applicable. Legacy MRSS doc CAPTCHA-blocked.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F20 CHAMP (`champ`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public player metadata observed; CHAMP login required for UI writes; role/tier and API credential contract unknown."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- Public player JS https://play.champds.com/_COMMON/js/cds.event.js?1794445126 derives GET https://playapi.champds.com/{CustomerAccessID}/event/{EventID} and expects JSON.
- https://playapi.champds.com/lakezurichil/event/164 and https://playapi.champds.com/yumacoaz/event/657: unauthenticated GETs returned HTTP 200 JSON-shaped bodies served as text/html. Engine receipt docs/verification/champ-detail-2026-11-11.json reports completed one-event reads with original fields preserved (14 agenda items each; Lake Zurich 6 documents, Yuma 0; 1 recording each); catalog_complete=false. No attachment bytes downloaded. Direct hashes and snapshots: outputs/provider-route-probes-2026-11-11/capture-index.json.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Public event detail is engine-live-read-verified on two existing tenants; no public catalog/list or pagination route found. Admin help says authenticated Events list has 15/page; that is not a public JSON pagination contract.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Public event detail is engine-live-read-verified on two existing tenants; no public catalog/list or pagination route found. Admin help says authenticated Events list has 15/page; that is not a public JSON pagination contract."
}

### Authorization restrictions

- Do not ingest unpublished JSON through baseline public path. Supplied media/captions only; player/download button not proof playable media.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F21 Hyland OnBase Agenda Online (`onbase`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/: Fitchburg public listing; No archive/search traversal or binary download.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Upcoming body/date filters; archive/year/search pagination unverified."
}

### Authorization restrictions


## F22 Laserfiche WebLink (`laserfiche-weblink`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"WebLink cookie/browser session may be required; saved capture baseline remains.","outbound":"Cloud OAuth v2 scopes AND principal ACL; self-hosted API deployment/version separate. No access supplied."}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://miweblink.metro-inet.us/sapublic/Browse.aspx?startid=207&cr=1: cookie_blocked
- https://weblink.ci.northfield.mn.us/WebLink/Browse.aspx?dbid=0&startid=92&row=1&cr=1: cookie_blocked

### Remaining research

- RepositoryAPI v2 full pagination continuation and limits
- Self-hosted tenant equivalent API/deployment/version and auth
- WebLink official API/download/search contract vs saved HTML
- Rename/metadata template update/version conflict semantics
- Native vendor import/export-file format beyond API file import unverified
- CreatePages indexed-pair prose/sample contradiction needs authoritative resolution or authorized test evidence; mocks cannot settle.
- ImportUploadedParts exact request content type conflicts in guide prose/sample (multipart/form vs shown JSON); resolve before automatic submission.

### Pagination contract

{
  "status": "unverified",
  "details": "Provider-specific bounds/pagination and date coverage pending."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.
- No DELETE or empty all-page replacement; move/copy/rotate and general repository administration not part of connector write scope.

## F23 TownCloud (`towncloud`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Published agenda detail public. Editing/publication requires authorized TownCloud account; API access and tier unknown."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://woodfordvt.org/: GET 200. Recent agendas grouped by body, links to /go/woodford-vt/agendas/{id} and PDF document links. Limits: Recent-only homepage is not full agenda table or exhaustive discovery.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Homepage recent groups only; table JSON request method, pagination/search/date filtering and full history remain unverified.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Homepage recent groups only; table JSON request method, pagination/search/date filtering and full history remain unverified."
}

### Authorization restrictions

- Downloadable packet output does not establish a TownCloud import file format. Do not infer table JSON write endpoint.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F24 Digital Towpath (`digital-towpath`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Demo reads public; dashboard required for administration. Customer credentials and account roles not supplied."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://townbrutus.digitaltowpath.org:10148/content/MinuteCategories/View/1: GET redirected to digitaltowpathny.gov:10148/content/404, HTTP 200. Provider-branded File Not Found page, search and Minutes navigation links. Limits: Requested category was not obtained; HTTP 200 cannot mean successful meeting fetch. Legacy/new templates may differ.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Demo Other Years navigation observed. Legacy Brutus category URL moved; no numeric paging or complete archive verified.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Demo Other Years navigation observed. Legacy Brutus category URL moved; no numeric paging or complete archive verified."
}

### Authorization restrictions

- PDF manual extraction blocked; indexed excerpts insufficient to claim upload/update API. Demo inconsistent minutes dates must not silently override page dates.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F25 ClerkBase (`clerkbase`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://clerkshq.com/southkingstown-ri: South Kingstown ClerkBase public portal; Shell/help extracted, not actual meeting-document tree or search results.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Folder/tree and search-result paging unknown."
}

### Authorization restrictions


## F26 Municipality-published calendar (iCalendar) (`first-party`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Observed feed public. Publication/admin credentials and hosting CMS are separate, unknown contracts."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.logan-twp.org/events/: GET 200 redirected from /municipal-calendar/. Municipal meeting calendar has iCalendar webcal subscription and HTTP Export .ics links. Limits: Calendar page includes non-meeting events; explicit source/type bounds required.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- iCalendar defines no universal pagination. Tenant export window is bounded/implementation-specific; observed month endpoint omitted past early-month events.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "iCalendar defines no universal pagination. Tenant export window is bounded/implementation-specific; observed month endpoint omitted past early-month events."
}

### Authorization restrictions

- No generic calendar-host write support. METHOD:PUBLISH and RFC property names do not grant upstream create/update/upload. Preserve floating/all-day/timezone/recurrence distinctions.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F27 Wistia (`wistia`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":{"public_read":"unverified","outbound":"not supplied; authorized provider test tenant/credentials absent"}}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://fast.wistia.com/embed/medias/26sk4lmiix.json: Public official demonstration media JSON observed; not municipal live meeting acceptance.

### Remaining research

- Account-tier upload/feature/media limits and modern schema vs older guide discrepancies
- Provider-specific file-import package other than uploadAPI unverified
- No Wistia account token/tenant supplied; native search/media detail live acceptance not run
- Caption list/per-language GET is documented but no retrieval adapter implemented
- Search is capped at 100+100 with no cursor; exact/phrase semantics not specified
- Provider write acceptance remains NOT_RUN because no authorized provider test tenants or credentials were supplied
- Media swap/replacement official endpoint remains candidate; full fields/receipt and domain impact need review.

### Pagination contract

{
  "status": "documented_with_conflict",
  "evidence_ids": [
    "wistia-list"
  ],
  "details": "page/per_page offset OR cursor[enabled]/before/after, never combine page/cursor. Cursor sort_by description permits id/created, but enum excludes id; shared unambiguous supported sort value created. Numeric per_page bounds not stated in inspected schema."
}

### Authorization restrictions

- No remote writes authorized; no procurement or outreach.
- Unverified and access-blocked are incomplete, not unsupported.
- No caption purchasing or ASR/transcription generation authorized.
- Official older embed guide cautions audio/Channels,modern schemas include audio types; feature/version mismatch needs validation rather than unsupported claim.

## F28 Boardable (`boardable`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://site.boardable.com/ventura-county-community-college-district: VCCCD Public Site; Initial list; search/pagination untested.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "View all meetings, previous/next detail links; list date/page requests unknown."
}

### Authorization restrictions

- Private document upload not public publication.
- Invited-meeting edits send mandatory notifications.
- Keep explicit PST vs unspecified landing timezone.

## F29 gWorks FrontDesk (`gworks`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"City JSON public; login/admin writes separate. Galena UI login disabled at observation; API credentials/roles unknown."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://galenaks.frontdeskgworks.com/: GET 200. Public extracted homepage lists Latest Agendas and Minutes; login features describe browsing meeting records. Images identify city 1117. Limits: Links are hash/UI controls; page also says Login is disabled at this moment; not evidence all reads require login.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- One static public JSON blob observed; no next-page token. Retained history/update frequency and maximum blob size unknown.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "One static public JSON blob observed; no next-page token. Retained history/update frequency and maximum blob size unknown."
}

### Authorization restrictions

- Keep cancelled titles/status indicators. Public city JSON response fields and PDF GET route are not writable API fields.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.

## F30 Diligent BoardDocs (`boarddocs`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Public pages accessed without credentials where content returned. Staff/test credentials not supplied; no private access attempted."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://www.laspositascollege.edu/gv/assets/docs/INSTRUCTIONS%20-%20Submitting%20Agenda%20Items%20-%20Final.pdf: Las Positas BoardDocs submitting agenda items; Tenant UI workflow not vendor API; permissions/approval/visibility must be preserved.
- https://go.boarddocs.com/co/cde/Board.nsf/Public: Colorado Board of Education BoardDocs shell; Dynamic meetings not extracted; shell not printed numbered PDF fixture.

### Remaining research

- Verify tenant-specific supported machine contract, authorization, rate/size limits and pagination.
- Obtain authorized non-production write access; validate duplicates, conflicts, ambiguous retries, approval/visibility and readback receipts.
- Preserve legacy IDs/namespaces/parent identities, unknown extensions, original fields, supplied revisions and missing timezone explicitly.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Current direct unauthenticated GET to the existing Colorado shell returned HTTP 403, whereas earlier extraction only saw the branded shell. Dynamic meetings and any BoardDocs-specific public catalog/API remain unresolved; HTTP 403 is not unsupported evidence."
}

### Authorization restrictions

- Keep baseline unencrypted printed numbered PDF; JS shell is not equivalent.
- Do not substitute Diligent Community/Boards APIs.
- Respect post-approval edit lock and public/private visibility.

## F31 Tyler Meeting Manager (`tyler-meeting-manager`)

Official documentation status: inspected_with_recorded_limits; some indexed_only/login_or_extraction_blocked
Account/tier: {"status":"unverified_unless_named_in_evidence","details":"Ector public calendar anonymous. Staff functions need authorized Tyler account and configured workflow; API tier/access unknown."}
Test environment: {"mode":"synthetic_mock_only","authorized_remote_writes":false,"provider_credentials":"not_supplied","live_provider_write_acceptance":"NOT_RUN/BLOCKED_ACCESS","rule":"Mock checks may prove adapter behavior; never provider acceptance."}

### Representative research observations

- https://cityofmurraycityuttmmapp.tylerhost.net/7452prod/tylermm/calendar/: prior FetchUrl extraction service HTTP 500; public URL found but no calendar response verified. This is not proof of tenant unavailability.
- https://ectorcountyclerktxtmmapp.meetingmanager.tylerapp.com/46612prod/tylermm/calendar/: direct GET returned 1403-byte SPA shell; public bundle provides tcmURL and POST meetingInformation/getMeetingInformationByDate with JSON `{startDate,endDate,meetingTypeIds}`, dates MM/DD/YYYY, no type filter [-1]. Nov 9-15 and Nov 1-30, 2026 returned HTTP 200 `[]`; no nonempty row schema. Captures/hashes in outputs/provider-route-probes-2026-11-11.

### Remaining research

- Pin baseline source commit and extract/test standalone readers.
- Public Ector client bundle exposes a date-range JSON query; two bounded Nov 2026 requests returned empty arrays. Successful nonempty response, JSON record fields, date bounds, pagination and archive completeness remain unverified.
- Resolve supported machine write/import contract separately from documented UI operations; do not infer absent capability from missing access.
- Run authorized test-tenant create/update/upload and required receipt/conflict/idempotency cases where supported.

### Pagination contract

{
  "status": "partly_observed_or_unverified",
  "details": "Public Ector client bundle exposes a date-range JSON query; two bounded Nov 2026 requests returned empty arrays. Successful nonempty response, JSON record fields, date bounds, pagination and archive completeness remain unverified."
}

### Authorization restrictions

- Baseline source skips cancelled/adjourned records and derives agenda item ids by position; new schema must preserve statuses and explain identity derivation rather than advertise baseline as full fidelity.
- Public credentials or authorized mutation access not supplied. No remote writes, outreach, procurement or credential handling performed.
