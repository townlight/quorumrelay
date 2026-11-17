# QuorumRelay: developer, forum, trial and sandbox investigation
November 16, 2026. All 31 original provider families checked. This supersedes the earlier targeted access check.

The useful result is gWorks' public development editor: it supplies previously missing meeting save/readback and agenda/minutes structures. Concrete evaluation paths also exist for OnBase, TownCloud, Boardable, Town Hall Streams, Laserfiche and Wistia. Sol's record contains developer research, but these specific leads were either missing or not followed through.

The initial research phase used local records/Git, public vendor sources, indexed primary pages and static client source. Later authorized evaluation and implementation work is recorded below. No purchases, direct vendor outreach or releases occurred. “Not located” below means this search did not locate a usable path, not that none exists.

## Current implementation and access status

The 31-family goal remains incomplete. Current local work includes gWorks meeting/editor/media upload and library paging, MinuteTraq SOAP and media transfer, Laserfiche multipart recovery, and Boardable current-builder item writes with files plus native single-meeting and weekly-series creation/metadata updates. The current weekly-series candidate passed 3,042 Python tests with zero failures/errors/skips. All 703 frozen source/test/project input hashes were verified before receipt bookkeeping. The subsequent capability metadata update passed 25 focused tests and the validator returned zero errors. Native trial actions and synthetic adapter tests are recorded separately.

Boardable's general Document Center contract is now captured: multipart upload201, metadata update200, exact JSON detail GET200 and original-byte SHA256 match before/after title changes. This research is pinned; no Document Center adapter has been integrated.

TownCloud's trial request was submitted successfully; there is no application dashboard. Scott ended further pursuit. Its existing draft writes and public ingestion remain available,39 affected tests passed, and a fresh public-engine check normalized6items and verified search plus JSON roundtrip. Storage-upload and parent-association request fields were recovered; the editor configuration, complete save form and created attachment readback remain missing.

TelVue's archived official v1 multipart upload endpoint and authentication were recovered. Successful response/media-ID mapping and stored-original/readiness lookup remain missing, so no upload adapter is claimed. Novus's exact archived demo/pilot/form chain was followed; it offers historical evaluation through contact capture and supplies no missing write schema. Essential response envelopes and API offset progression remain unresolved.

Wistia evaluation signup reached vendor account verification and supplied no token. Boardable's authorized trial is open. No payments, direct outreach or releases occurred. The following matrix retains the original research findings; dated continuation entries supply later implementation and access evidence.

## Results across all 31
Developer and forum columns distinguish machine documentation from support/user communities. Trial/sandbox columns record an actual offer where found; a sales demo is not counted as a usable sandbox.

| # | Family | Developer / API path | Forum / support path | Trial / sandbox path | Effect on missing contracts |
|---|---|---|---|---|---|
| 1 | Legistar | [Public API reference](https://webapi.legistar.com/Help), already captured | [Legistar troubleshooting](https://support.granicus.com/articles/Knowledge/Troubleshooting-Common-Legistar-Issues) | No current self-service developer enrollment located | Media field documentation clarifies MediaManager clip IDs. Does not supply missing file-import bytes or publication semantics. |
| 2 | PrimeGov / OneMeeting | [Current OneMeeting product](https://granicus.com/product/agenda-management-onemeeting/); public portal configuration help | [Roles and permissions](https://support.granicus.com/customersupport/s/article/Administration-Roles-and-Permissions), provisioned customer access | Sales demo; partner AgendaLink has a separately licensed sandbox (below) | Partner sandbox cannot supply PrimeGov's own payloads. No new native write schema recovered. |
| 3 | Granicus MediaManager | Official [platform-api-net SDK](https://github.com/Granicus/platform-api-net), WSDL, Java counterpart | [SDK issues](https://github.com/Granicus/platform-api-net/issues) | No specific free MediaManager API sandbox enrollment located | Existing SOAP mappings remain useful. No new template/publication/readback contract recovered. Granicus govDelivery APIs are a different product. |
| 4 | NovusAGENDA | Legacy [vendor blog](https://novusagenda.wordpress.com/) | Legacy help and current Granicus support | Old blog offers a pilot/self-guided demo; links no longer establish current enrollment | Historical lead, not a current usable test environment. [EOL planning](https://granicus.com/iqm2-and-novusagenda-end-of-life-planning/) explains why old access links need caution. |
| 5 | CivicPlus Select / CivicClerk | Existing tenant OpenAPI evidence; [Select documentation](https://www.civicplus.help/meetings-select) | Product help and support | No independently usable API sandbox located | Event-create gap remains selected template/publication/media defaults. General trial marketing would not answer those defaults. |
| 6 | CivicPlus AgendaCenter | [Web Central API documentation](https://www.civicplus.help/municipal-websites-central/docs/api-and-web-central) and API samples | CivicPlus product help | No AgendaCenter-specific test program located | Listed Web Central API modules do not establish AgendaCenter write endpoints. Calendar APIs cannot be substituted. |
| 7 | CivicPlus Essential / Municode Meetings | [Public API guide](https://www.civicplus.help/meetings-essential/docs/public-application-programming-interface-api); published Postman collection | CivicPlus support token route; no public developer forum with the missing responses located | No Essential API trial/sandbox enrollment located; saved Drupal sandbox tutorial is another product | Meeting/item GET schemas and collection paging remain the specific gap. Existing public PublishPage path already retrieves meeting details. |
| 8 | BoardBook | [FAQ](https://www.boardbook.org/faq) describes document formats and conversion | Vendor help / training | [Demo registration](https://www.boardbook.org/sign-up-for-a-demo) | Demo is informational. No external agenda-import or write payload recovered. |
| 9 | eSCRIBE | Existing public PublishingService WSDL; [help center](https://help.escribemeetings.com/) | [Product page](https://www.escribemeetings.com/products/) advertises a customer forum | Personalized demonstration; no API trial entitlement located | Customer forum is a useful next access route. Public follow-up did not settle remaining upload/chunk semantics; direct product-page access returned 403, indexed vendor text was available. |
| 10 | Simbli | [Official product](https://eboardsolutions.com/simbli-board-management-software/) and existing public meeting clients | [Helpdesk](https://helpdesk.eboardsolutions.com/) | Personalized demo; no open API sandbox located | No new administrative/write contract. Existing public readers remain the executable route. |
| 11 | iCompass / CivicWeb | Existing Document.asmx contract | [LeadOn community](https://www.icompasstech.com/) and [Diligent training](https://connect.diligent.com/s/community-icompass-training?language=en_US) | Customer login/coaching; no free API sandbox located | Real customer community exists. Diligent GRC developer schemas do not map CivicWeb writes. |
| 12 | iQM2 / MinuteTraq | [Official downloads instructions](https://support.granicus.com/s/article/IQM2-Downloads-MinuteTraq-and-Quick-Support) and user guides | Granicus legacy product support | Client downloads/support, not verified trial licensing; current EOL planning applies | Official MSI statically inspected without installation; SOAP meeting/item/media request contracts recovered and implemented, including chunk transfer and original-byte readback. See dated continuation evidence. |
| 13 | Swagit | Existing player clients; api.swagit.com search result is a default Rails page | Granicus support; vendor integration announcements | No developer trial/sandbox located | “Open API” integration claims alone contain no payloads. Generic Granicus API results are often govDelivery. |
| 14 | SuiteOne | [Technical page](https://getsuiteone.com/technical/) and [Liberty upload workflow](https://getsuiteone.com/uploading-your-liberty-meeting-recorder-dcr2video-and-or-bookmarks-to-suiteone/) | Vendor implementation/support | No primary-source free API trial located | Official DCR2 producer exporter recovered: classic_content.HTML uses StartMeUp(native marker index), with media association/processing described in the March2021 guide. Current staff import/save/readback contract remains missing. |
| 15 | Peak | [Product FAQ](https://support.granicus.com/s/article/Peak-Frequently-Asked-Questions?c=&p=Agenda+PE+%28Peak+Agenda%29) / product demo | Granicus support | Sales demonstration; no API sandbox located | Public workflow material adds no missing write schema. Direct FAQ extraction returned no readable text. |
| 16 | Utah Public Notice | [Publisher help](https://secure.utah.gov/pmn-admin/help.html) | [Official training](https://archives.utah.gov/transparency-services/public-notice-website/) | Registration followed by owner approval for posting; no separate sandbox located | This is a state service. Publisher access is an actionable route, but it is live publishing access, not a free anonymous API playground. |
| 17 | AgendaQuick / Destiny | [Product](https://www.destinysoftwareinc.com/agendaquick/) and integration pages | Vendor support | [Hosting/pricing options](https://www.destinysoftwareinc.com/hosting-options-and-pricing/), hosted or installed; no developer trial located | No new agenda write/import schema. |
| 18 | Town Hall Streams | Existing public player and scheduling workflow | Vendor support | [Vendor explicitly offers a free trial by contact](https://townhallstreams.com/about.php) | Missed evaluation route. Could expose scheduling/editor requests when access is later authorized. No contact made. |
| 19 | TelVue Connect / CloudCast | [Connect API docs](https://telvue.com/telvue-knowledge-base/connectcloudcast-kb/connect-apis/) | Historical TelVue forum link found through [Drupal integration discussion](https://groups.drupal.org/node/261283); old forum unavailable | No verified developer trial; viewer paywall trials excluded | Public API documentation is usable now. Old server-API forum is not automatically a Connect contract. |
| 20 | CHAMP | [CHAMP help](https://help.champds.com/) and existing player code | Vendor knowledge base | Live-player documentation includes a demo embed; no developer enrollment found | Demo player helps public-reader testing, not staff write access. CHAMP is champds.com, not AgendaPal. |
| 21 | Hyland OnBase | Community SDK/sample resources and Unity REST Swagger already in record | Hyland Community | [REST API sandbox hands-on lab](https://university.hyland.com/courses/e5243), 90 minutes | Strong new route for REST testing. Need an eligible training account and an Agenda-enabled environment for the specific outstanding Agenda/EIS contract. |
| 22 | Laserfiche | [Developer center](https://developer.laserfiche.com/), schemas, SDK, Swagger | [Developer community](https://developer.laserfiche.com/docs/Community/) explicitly directs API questions to Answers | [Free evaluation agreement](https://lfxstatic.com/dist/acs/latest/EULA_trial.pdf); account required. Sandbox also a pricing add-on | Specific forum threads reveal import options and timeout behavior; see below. Existing documented APIs already support substantial implementation without a trial. |
| 23 | TownCloud | Existing public application clients | Vendor support; no public developer forum located | [Agenda product free trial](https://towncloud.com/website-and-agenda/) leads to [active signup page](https://towncloud.com/sign-up/) | Trial request submitted; confirmation awaits provisioning, with no application dashboard. Further pursuit ended at Scott’s request. Public-client upload request fields pinned; existing draft/public/detail checks39 passed. |
| 24 | Digital Towpath | [Cooperative website](https://digitaltowpathny.gov/) and existing public site forms | Cooperative support | Membership/account provisioning route; no anonymous developer sandbox found | Public demo/test content is not an API test account. No new write payload recovered. |
| 25 | ClerkBase | [Vendor site](https://clerkbase.com/), product/help material | Vendor support | Product demonstrations; no developer trial located | ClerkMate and OnBoardGOV are distinct products. Their demos do not establish legacy ClerkBase write compatibility. |
| 26 | Public iCalendar | [CalConnect developer guide](https://devguide.calconnect.org/publishing/) and standard format | CalConnect resources | Local fixtures require no account; server testing depends on the actual destination | A format family, not a vendor. ICS publication/subscription does not establish CalDAV mutation rights or endpoints. No new integration added. |
| 27 | Wistia | [Developer plan](https://wistia.com/pricing/developer-plan), [API token instructions](https://docs.wistia.com/docs/making-api-requests) | Developer documentation / support | Advertised free starting allowance, then billing thresholds | Evaluation account reached vendor verification; no API token available. Existing mapped APIs remain documented; no verification workaround or vendor contact. |
| 28 | Boardable | [Official site advertises an open API](https://boardable.com/); public help center | Boardable knowledge base | [14-day Professional trial](https://boardable.com/plans/) / [Get Started](https://boardable.com/get-started/) | Authorized trial open. Current-builder item/file writes, native single meetings and weekly-series metadata/create adapters are integrated. Current series full regression passed 3,042 tests; final metadata passed 25 focused tests. General Document Center upload201/title-update200/detail GET200 and original-byte hash verified natively; that contract is pinned without a new adapter. Other recurrence patterns, publication and import remain open. |
| 29 | gWorks FrontDesk | [Indexed development editor entry](https://portal.dev.gworks.cloud/plugin/cms/am.html), linked JavaScript and both editors publicly readable | Product support / builder material | Public static development client; no test account needed to inspect source | **New concrete contract recovered:** detail GET, create/update methods, serialized fields, response ID, section/item structure and publish flags. Implementable source evidence, detailed below. |
| 30 | Diligent BoardDocs | [BoardDocs product resources](https://www.diligent.com/lp/boarddocs) | [Diligent Connect support](https://www.diligent.com/support), BoardDocs-specific support listed | Demo/contact; no BoardDocs API sandbox enrollment located | Diligent developer portal was already checked. Its GRC APIs remain a different product; no new BoardDocs write schema recovered. |
| 31 | Tyler Meeting Manager | [Meeting Manager product](https://www.tylertech.com/products/meeting-manager) | [Tyler Community](https://www.tylertech.com/welcome/tyler-community) forums, wikis and libraries; product availability varies | Product demo; no specific Meeting Manager developer sandbox located | A real forum route. Enterprise ERP API catalog is not a Meeting Manager contract. |

## Leads followed beyond the previous record

**gWorks:** The previously attempted Galena minutes editor returned 404. Search instead located the vendor's development application. Its linked agenda and minutes editors and shared code returned HTTP 200. The actual declared API origin is `https://api.dev.gworks.cloud`; the development client must not silently be treated as the production deployment.

The [editor script](https://portal.dev.gworks.cloud/plugin/cms/js-app/meeting-editor.js?v=21-MM-DD-000DEV000) establishes:
- GET and PUT `/cms/secure/city/meeting/{id}`; create POST `/cms/secure/city/meeting/`.
- Save response uses flattened `cms_meeting.id` and `cms_meeting.mod_ts`.
- Detail contains section and file arrays; writes encode those arrays as JSON strings in the outer JSON request.
- Sections contain titles and ordered items. Items contain agenda text, minutes text and file descriptors.
- Agenda and minutes publication are explicit actions with separate flags/dates.
- Item positions carry no native IDs; original fields must be preserved.

The declared core client supplies Bearer authentication and JSON transport. These exact sources now provide concrete work instead of another speculative endpoint search.

**OnBase:** [REST sandbox lab](https://university.hyland.com/courses/e5243) explicitly offers temporary REST experimentation and lists Foundation releases. [Generic sandbox lab](https://university.hyland.com/courses/p1942) warns not all modules are licensed. [Account instructions](https://university.hyland.com/learn/article/a5149) describe customer/partner enrollment. The next useful access question is Agenda-module availability, not whether Hyland has any sandbox.

**Laserfiche:** [Generate Pages discussion](https://answers.laserfiche.com/questions/216833/Laserfiche-API--Generate-Pages) points to request-body options hidden by the Swagger presentation. [Import timeout discussion](https://answers.laserfiche.com/questions/235341/API-Import-timeout-500-unknown) reports an entry created despite a 500 during page generation; a reply recommends ImportUploadedParts for longer uploads. This is useful for field discovery and uncertain-result handling. It is not a request to add OCR scope.

**AgendaLink / JustMeetings partner:** The prior record saw the sandbox FAQ category. Following [the actual article](https://support.agendalink.app/hc/en-us/articles/22022766295693-How-do-I-get-access-to-a-sandbox) established sales provisioning, an extra license fee and existing-login reuse. It is not PrimeGov's own sandbox and is not a 32nd family in this report.

**TownCloud, Boardable and Town Hall Streams:** These were concrete trial leads. Later authorization allowed evaluation accounts: Boardable is active; TownCloud submitted a request and further pursuit was ended by Scott; Town Hall Streams requires direct vendor contact, which remains prohibited.

## Historical inspection and source provenance
Inspected current checkout `C:\Users\scott\Documents\Codex\qr9\integrated` at `897442bf99dff40c4bd03126009083ad9fd485a3`, its capability evidence and local Git history; original library documentation; Essential research folders; cumulative state; and the full November 16 handoff.

Examples of prior research: Hyland Community/Swagger evidence in commit `9f375b4`; Laserfiche documentation in `59f6ba0` and `957bd14`; Diligent developer portal explicitly discussed in cumulative state; partner sandbox-category evidence in `b0a80c3`. Git records do not identify which model performed every action.

No matching saved research was found for the exact OnBase REST sandbox lab, the gWorks development editor, Boardable open-API claim, the two Laserfiche forum threads or Town Hall Streams free-trial page. TownCloud's product page was present, but its trial path was not followed in the examined record.

gWorks static captures are retained under the current chat's `work/vendor-access` directory. SHA256:
- `gworks-am.html`: `1e443e22095f9e7bf712afd876bdcea738bb25f8f36722321e1c029ccc8c2716`
- `gworks-editor.js`: `0c277bee76c897e0b34313ecf64b1384b5f05496954064f07b8dcc635bee9f1f`
- `gworks-editor-agenda.html`: `ab27ecf59d9a6b14713bc3f8491e9c7fc0b7291dbfcfaddca7a3ee5c3ed6c7bd`
- `gworks-editor-minutes.html`: `205c1e9fe469e2d2d3e1da9775dcdcdb741c3c50c8e23127d6bae63c392c35a2`
- `gworks-2.js` (core): `0826615bc22075396540a3251c724655100223d26afd973db96dc069ea28e920`

Research outcome: all 31 covered; one new substantive machine-contract source recovered, several concrete evaluation routes identified, and the remaining gaps named by product. Implementation progress is recorded separately from this research snapshot.


## Implementation completed after the research

Following Scott's direction to get it working, implemented `gworks-editor-meeting-json` and its selected GET in the current integrated checkout. It maps meeting identity, sections, agenda/minutes text and raw file descriptors; preserves unknown values; and uses a separate development namespace with tenant/city/origin-scoped credentials. It is registered in the existing SDK/fetch/parser path.

Verification: **89 gWorks tests passed (30 new), plus 104 shared discovery/evidence tests; lint and capability validation passed.** SQLite reopen/search and JSON/JSONL/ZIP round trips were exercised. Synthetic responses follow the captured vendor client. Create/update routes were recorded but writes remain unfinished. Essential response/pagination remains unfinished. No accounts, contact, payments, live API calls or releases.

Candidate: local uncommitted changes on `897442bf99dff40c4bd03126009083ad9fd485a3`, under `C:\Users\scott\Documents\Codex\qr9\integrated`. Source: `src/civic_data_connectors/providers/gworks_editor.py`; usage: `docs/GWORKS-EDITOR.md`; exact verification bindings: `docs/verification/gworks-development-editor-2026-11-16.json`. No jobs remain running.

## Continuation: gWorks writes and Essential follow-up

**gWorks writes implemented locally:** draft or published-agenda meeting creation; metadata, agenda and minutes updates; section/item additions; explicit agenda/minutes publication. The source is the captured development editor. The adapter preserves existing file descriptors and unknown fields, checks the before-state immediately before update, persists the returned ID and verifies detail readback. Uncertain sends reconcile without repeating POST/PUT. All operations use the existing plan/hash approval and durable receipt flow.

**125 affected cases passed:** 94 combined gWorks/read/shared-write cases,6 additional response-boundary cases,25 capability/evidence cases. Full Ruff, capability validation and diff checks passed. Exact receipt: `docs/verification/gworks-writes-2026-11-16.json`. Usage: `docs/GWORKS-EDITOR.md`. Production applicability and new-file upload association remain outside this mapped development write contract.

**Essential remains unfinished.** New work recovered the archived vendor Vue client and eight archived legacy portal bundles, and inspected two current open-source clients. They contain public-player/Drupal/HTML behavior, not the missing authenticated response envelopes and offset rules. No guessed schema or pagination was added. Captures, hashes and the precise remaining fields are saved in this chat's `work/essential-followup-20261116/assessment.json`.

All changes remain local on base `897442bf99dff40c4bd03126009083ad9fd485a3`. No accounts, payments, contacts, live API writes or releases. No jobs remain running.

## MinuteTraq downloads and Laserfiche application — November 16 continuation

MinuteTraq official full MSI downloaded and statically extracted. Its LMClassicServiceClient.dll contains concrete SOAP declarations for agenda/minutes reads, Word-byte imports, dataset updates and agenda publication. M2Common3.5.dll contains the typed DB_1_0 schema. The endpoint and custom authorization construction are present in client source. No vendor application was installed/run and no credentials were used. Next implementation work must finish tracing dataset serialization and actual import/update call sites. This is recovered contract evidence; the new MinuteTraq adapter is not implemented yet.

Laserfiche's recommended uploaded-parts route and uncertain-result no-replay behavior already exist in the implementation. DeepSeek authored four focused regressions covering import500 after server-side create, final multipart-import500 with no taskID, successful multipart task reference, and PDF option validation. All4passed; existing shared write suite7passed; targetedRuff and diffchecks passed. Added usage/recovery documentation. No production behavior change was necessary for those findings.

Worker policy for this goal: DeepSeek v4.1 Flash1017 via Ollama, think low, primary worker. Coordinator handles research, assignment, integration and verification. No primary product coding was performed. Worker prompts/responses and verification retained in work/workers; MinuteTraq source hashes in work/minutetraq/source.json. No active jobs at checkpoint. Goal remains active; no accounts/payments/vendor contacts/releases.

## MinuteTraq saved SOAP reader implemented

DeepSeek authored the registered iqm2-minutetraq-soap-xml parser for captured AgendaGet/MinutesGet responses. It normalizes selected meeting, agenda/minutes and item identities, titles, parent/order/date fields, retains raw XML/unknown fields and separates agency-specific staff namespaces from public sources. SQLite reopen/search and JSON/JSONL/ZIP roundtrips are tested.96affected tests passed; after final removal of an unverified revision projection,29parser tests passed again. Full lint, capability validator and diffcheck passed. Exact receipt: integrated docs/verification/iqm2-minutetraq-soap-2026-11-16.json.

Native SOAP retrieval, dataset writes and file transfers remain next work. Goal remains active. No accounts/payments/contacts/releases or live vendor calls. No jobs remain running at checkpoint.

## MinuteTraq native SOAP retrieval verified

Selected AgendaGet/MinutesGet POST retrieval is now implemented with private tenant/origin/agency/ID-scoped existing-session credentials, explicit file-date thresholds and response/cancellation/size guards. Saved and fetched datasets can omit the Meeting table: document/items retain the supplied meeting reference without fabricated meeting records.130affected tests and25capability/evidence tests passed; fullRuff, capability validator and diffcheck passed. Native receipt: integrated docs/verification/iqm2-minutetraq-native-2026-11-16.json. Source evidence is now included in the capability inventory.

Dataset writes, chunked file transfer and the remaining meeting/recording operations remain unfinished. DeepSeek authored the code and corrections. No live vendor call, account, payment, contact or release. No jobs running at checkpoint.

## Additional gWorks media contract recovered

Followed the development editor's linked CMS plugin and media-library snippets. Public source `https://portal.dev.gworks.cloud/plugin/cms/js/city.plugin.js?v=21-MM-DD-000DEV000` returned HTTP200 and exposes POST `/cms/secure/media` with filename/MIME/size metadata. Shared client then PUTs the selected file bytes to the returned signedUrl. The media-list route supplies file IDs and descriptors; meeting-level attachments use `{name,id,size,type}`, while agenda-item attachments use `{filename,usetype}` with an explicit official/public selection. Source hashes and captures are retained in `work/vendor-access/gworks-media-source.json`.

This is new implementable source evidence. Upload/association code is not yet implemented; durable uncertain-upload recovery, exact returned-file identity and signed-destination guarding remain required implementation work. No credentials, account, upload or release was used to recover it.

The media-list follow-up resolved its transport and paging: the captured CMS plugin delegates to the shared DataTables adapter, which sends a form-encoded POST to `/cms/secure/media/list` with start/length/draw and column/filter parameters. The linked DataTables1.10.21 library was captured, and its [official server-side protocol](https://datatables.net/manual/core/server-side) identifies draw, recordsTotal, recordsFiltered and data in the response. This enables bounded media-list/readback work. Upload association must verify the exact file and native ID; the client UI's first-row selection and upload-success toast are not sufficient implementation checks.

## MinuteTraq writes integrated and verified

The local candidate now implements selected agenda/minutes item-title updates and native meeting creation/update. Seventy affected checks passed: 41 title-update, 22 meeting, and 7 shared write cases. Independent System.Data fixtures deserialize the actual outbound requests and check native row states, identities, original/current values and preservation. The adapter uses durable intent, exact readback and read-only reconciliation without replaying uncertain writes. Source-bound verification is in integrated docs/verification/iqm2-minutetraq-writes-2026-11-16.json.

The preceding full suite ran 2,916 cases: 2,915 passed and one MCP cancellation timing test failed. A timing probe isolated prompt progress-send cancellation from slower terminal SQLite persistence; a test-only correction preserves the 300ms unblock assertion and separate durable completion checks. Its follow-up is in progress. No blanket full-suite pass is claimed. Recording transfer and broader MinuteTraq imports remain unfinished; gWorks media work remains in scratch. No accounts, payments, contacts, live vendor writes or releases.

## gWorks upload and attachment association verified

Development media upload and existing meeting/agenda-item attachment association are now integrated locally. The flow allocates media, PUTs exact bytes to an approved signed destination, pages the library for exact native identity, verifies downloaded bytes, saves the intended association and checks the result. Durable receipts preserve uncertain steps without repeating mutations. All97affected tests passed, including15media tests and existinggWorks/shared cases. Usage and source-bound receipt are in integrated docs/GWORKS-EDITOR.md and docs/verification/gworks-media-writes-2026-11-16.json. Production applicability remains separate. No live uploads/accounts/payments/contacts/releases.

## MinuteTraq recording upload integrated and verified

Native M2 BigFiles recording creation/replacement is implemented locally. All **80 affected checks passed in 185.49 seconds**, including actual System.Data outbound request validation, public file handles, exact metadata/original-byte verification, cancellation and recovery without replaying uncertain writes. Trusted BigFiles configuration is required. The **25 metadata tests passed**, and capability validation passes with 469 evidence records, 190 outbound mappings and zero errors. The final full Python regression run is active. No live vendor writes, accounts, payments, contacts or releases.


## Final available-contract verification

The final frozen candidate passed **2,963 Python tests**, zero failures or skips, in352.48seconds. All725snapshottedfiles remainedunchanged. Metadata25tests, capabilityvalidation and requiredRuffscope pass. Allownedjobs areterminal. The available-contract work is complete locally; unresolved vendor contracts and evaluation access are listed in QUORUMRELAY-COMPLETION-2026-11-16.md. Noaccounts/payments/contacts/livevendorwrites/releases.

## Boardable trial execution — November 16

Scott completed registration with the authorized permanent evaluation address. The **QuorumRelay Evaluation** tenant is active; the dashboard displayed **13 days remaining**.

The current trial opens a separate **Agenda Builder** at `agendas.boardable.com`. Its native API lives under `https://app.boardable.com/api/agenda-approvals`, uses the signed-in session and an exact numeric `Organization` header, and differs from the legacy editor already mapped in QuorumRelay.

Executed in this evaluation tenant:

- Created a synthetic agenda item using JSON POST; HTTP 201 returned native item identity.
- Updated its title and uploaded a synthetic text attachment using multipart POST with `_method=PUT`; HTTP 200.
- Independently read the item and verified the attachment's native ID, organization and agenda association.
- Downloaded the original file through the document viewer: **134 bytes**, SHA-256 `ecbaade25c53d0d336960fab9b3c451f28bc43e4260ef0f6da5c7358a9818c15`, exactly matching the input.
- Captured meeting-list `data/counts/links/meta` pagination, current meeting detail, nested agenda, packet status and recording metadata responses.

The current-builder implementation is in scratch verification. The first affected run found a missing preflight conflict check and an incorrect test expectation after a temporary download fault cleared; corrections are underway. No current-builder completion claim yet. No publication, invitations, payments, vendor contacts or releases.


### Current progress: Boardable integrated; TownCloud pending submission
- Boardable current-builder adapter integrated into the existing dirty candidate at qr9/integrated (no release). Explicit current_agenda_builder selects current item create/update + associated file uploads, separate from legacy mode. Exact tree/item/parent/owner/presenter/approval-tree/upload association and original-byte hash verification; preflight, durable intent and read-only no-replay recovery.
- DeepSeek LOW jobs 6116/66463/80811 terminal. Corrected inconsistent fake tree/detail owner/upload snapshots against independent live current-meeting capture. Scratch 78 passed. Integrated affected run 62973 terminal: 105 passed, 0 failed,18.84s. Metadata 25 passed0.82s; repository-config Ruff and git diff--check passed. Validator470 evidence/190 outbound/0errors after runtime sync. No running coding/test jobs.
- Exact source hashes: builder1a99fc89894eb8379378b7b6f912625a3918d0585b4d482239aec01646d06013; wrapper5ae88f11bb887806f8a25eca1ed7cbacc439662a86cf917932ebaed1925866c3; newtestb6c5b5c960513d15bdfaafc897e0bbb8ea3f47212a0cf79c4af4a148a422cfe4. Receipt docs/verification/boardable-current-builder-2026-11-16.json and pinned docs/capabilities/evidence/boardable-current-builder/. Adapter tests synthetic; separate browser trial create201/update+upload200/exact134byte download already verified. Meeting forms/recurring/publication/import gaps remain.
- Scott supplied TownCloud phone/address/population and approved visible window. TownCloud Chrome tab200074925, organization QuorumRelay Evaluation. User subsequently changed address to1750 30th Street,173 andpopulation104000, selectedGiveMeEverything in additionAgenda; preserve these user changes. Form initially rejected name despite displayed value; actual keyboard reentry cleared errors. CAPTCHA reset. User asked to complete CAPTCHA and submit Terms-bound StartTrial, pending. Do not submit legal terms without action-time confirmation. Current CUA vars townTab/townBrowser/townFs. Handoffmarked; do not run completion_summary until observed outcome.
- OnBase new primary lead: Hyland Workflow action Create or Update Agenda Item From Document (Foundation22.1) supports AgendaItemPrimaryKey0=create/nonzero=update; required AgendaItemType/MeetingType/Title; EForm/keyword/WorkflowProperty mapping, AttachRelatedDocuments and returned AgendaItemPrimaryKey property. Requires Agenda license/configured client and Core/UnityWorkflow. Exact configured task IDs / callable API schema still open. MediaPublisher Windows service config is not an Agenda REST write contract. Next research owning Workflow API and current provider code.
- SuiteOne Liberty official PRM0420r02b2030 ZIP/MSI statically extracted (never executed/installed). Help supports media/PDF conversion, no required *_content.HTML schema. MediaManager official DownloadMinutes sample produces local SimpleMeetingDocument XML, not generated-template/file bytes contract. Essential unchanged missing-response schemas. All31 goal remains incomplete.


### TownCloud signup ended; public-contract work completed within available evidence
Scott requested abandoning signup. No account confirmed; do not resume it. Current public application is byte-identical to pinned bundle (1758089bytes SHA180588c9245d1e9b195b2ec81887346af77c88bcfe2492baf28240e0e377b8ae). Recovered exact presigned POST201 + PDF validation + item attachment association fields; pinned upload.extract.js/upload-source.json and documented required runtime editor config, full form, created ID/original-byte/recovery gaps.39 affected tests passed3.50s. Existing draft/public/detail behavior retained.


### OnBase Workflow route recovered
Hyland documents a native Create or Update Agenda Item From Document action and a programmable Workflow path. A configured API Task maps user JSON paths to Workflow properties; its task can operate on a Virtual E-Form. A separately published ad-hoc task accepts a document handle and scoped Name/Value properties. This provides a concrete route to Agenda item creation/update when the destination is configured.

The remaining contract can be obtained from that deployment's `restservice.svc/help`: Hyland says it exposes operation URLs, HTTP methods and example JSON/XML requests and responses. The universal Agenda endpoint search should therefore also follow configured Workflow services. No configured service URL/task definition or Agenda readback response is available in current evidence, so this route has not been coded or executed.

Primary references:
- [Creating API Tasks](https://docs.hyland.com/r/OnBase/Workflow/English/Foundation-22.1/Workflow/Studio-Workflow-Configuration/Creating-API-Tasks)
- [API Task Properties](https://docs.hyland.com/r/OnBase/Workflow/English/Foundation-22.1/Workflow/Studio-Workflow-Configuration/Creating-API-Tasks/API-Task-Properties)
- [Published Workflow operation](https://docs.hyland.com/r/OnBase/Web-Services-Publishing/Foundation-26.1/Web-Services-Publishing/Configuration/Web-Services-Publishing/Creating-a-Web-Operation/Workflow-Execute-workflow-ad-hoc-task)
- [Workflow XML nodes](https://docs.hyland.com/r/OnBase/Enterprise-Integration-Server/Foundation-25.1/Enterprise-Integration-Server/Enterprise-Integration-Server-Configuration/Configuration-Overview/Adapters-Operations-and-Schemas/Schemas/Outbound-Operations/Workflow)
- [REST help with request/response examples](https://docs.hyland.com/r/OnBase/Web-Services-Publishing/Foundation-26.1/Web-Services-Publishing/Configuration/Web-Services-Publishing/Consuming-Web-Services/REST-Web-Services)

TownCloud fresh public acceptance2026-11-16: current Woodford agenda452 fetched headlessly (4763bytes SHA13322460a2f37b8b9cd46724b665ef61eafcf379dbe431043793e08809fbf5e3), existing engine normalized6agenda items, captured-content search for Mitigation returned1hit, JSON export/import roundtrip exact. No editor/account/write. Receipt docs/verification/towncloud-public-current-2026-11-16.json.

TownCloud update: Scott reported signup working/logged in. Observed Chrome200074925 now https://towncloud.com/trial-thanks/ confirms successful trial request, text Someone will be in touch with you soon. No TownCloud application dashboard tab found in selected Chrome. Asked for dashboard URL if opened elsewhere. Screenshot outputs/towncloud-trial-request-confirmed.jpg. Signup is submitted; account/application access remains pending dashboard route or provisioning. Do not repeat signup or contact vendor.


### TelVue official legacy upload route recovered
Followed a2015Drupal forum lead through InternetArchive after the current thread503. Exact archived vendor documentation establishes POST https://connect.telvue.com/api/v1/assets/upload, HTTPBasic, multipart files[], optional published/syndicated/syndication_groups[]. This resolves the missing endpoint for a distinct legacy API path. Current browser source also consumes asset_ids; legacy response equivalence is not established. The remaining implementation inputs are exact v1 response/media identity, original-file hash/readiness and association. Recording metadata updates remain missing. No endpoint probing/mutation or new integration was added. Source pinned under docs/capabilities/evidence/telvue-legacy-upload/, usage docs/TELVUE-WRITES.md.
TownCloud final instruction: Scott confirmed no more information available there; leave request submitted, do not repeat signup, move on to remaining vendors.


### Novus archived evaluation chain followed
Recovered the exact historical official demo and free90-day pilot pages, then the demo's linked CoreMotives form. The form captures name/email and exposes no application URL or API schema. Saved primary pages and hashes under docs/capabilities/evidence/novus-archived-evaluation/. No contact, submission or account. Current Novus write contract remains unresolved. TelVue follow-up inspected the separate Firstturnmedia/media_telvue_connect Drupal module at1d13b18: it parses public player IDs and MRSS, with no upload response consumer. It does not resolve v1 upload response/media identity.
TownCloud source/document status corrected: successful request submitted, no dashboard; further pursuit ended per Scott.


### Current candidate regression completed —2026-11-16
Full Python exec98701 terminal exit0:2984passed,0failed,0errors,0skipped in2073.56s, one upstream Starlette/AnyIO deprecation warning. Started14:10:17-07:00, JUnit work/trial-access/boardable-candidate-full.xml. Verified the three Boardable source/test hashes still exactly match docs/verification/boardable-current-builder-2026-11-16.json; full receipt and JUnit hash added there.105 Boardable affected checks and39 TownCloud affected checks passed separately. Current metadata25passed0.78s, validator31providers/34formats/341operations/190outbound/471evidence/297URLs/0errors. Repository Ruff and diffcheck passed; unchanged client build/test evidence reused. HEAD897442bf99dff40c4bd03126009083ad9fd485a3 plus preserved dirty local work. No owned background jobs remain, no release.
Remaining next work: recover executable missing contracts for Essential response/offsets, TelVue response/media-ID/original readiness and remaining provider write/import gaps; Boardable meeting forms/recurrence/publication/import remain open. TownCloud pursuit ended per Scott; do not repeat signup/contact. All31 goal remains incomplete.


### Boardable native meeting form contract recovered —2026-11-16
Authorized trial created/edited private meeting526572 through UI. Exact minimal API fixture526577 separately confirmed POST /{org}/meetings201 rawnativeobject, POST /{org}/meetings_v2/{id}200 rawnativeobject, GET returnedcanonicalURL?format=json200 {meeting}. Title update changes slug/URL while retainingnativeID. Numeric detail probe404; never invent numericreadback. No invitations/publication/video/guests. Native single-meeting dates/timezone/owner/public flags and JSON responses pinned under docs/capabilities/evidence/boardable-meeting-form; server-rendered inline form logic extracted with embedded JSON record initializers removed.
Owned implementation draft job: exec85230, owner current Codex goal, expected work/workers/boardable-meeting-files.json, model existing deepseek-v4.1-flash:1017-cloud thinklow; headroom~33.6GiB available. Started per boardable-meeting-job.json. CancellationCtrl-C85230. Output scratchonly; next poll then inspect and execute affected checks beforeintegration. Prior fullsuite2984pass applies to candidate before this draft; no new productcode integrated yet.

### Boardable meeting adapter integrated —2026-11-16
Native single private unpublished meeting create/update is now implemented locally, with title, description, location, IANA timezone and single date/time range. Exact native IDs and changed canonical URLs are retained before readback; recovery never replays POST or matches titles. Windows timezone runtime dependency added.131 affected tests passed in19.31s; separate combined all-field update passed with independent Denver UTC expectations. Metadata25passed1.22s, repository Ruff and diffcheck passed; validator31providers/34formats/341operations/190outbound/472evidence/298URLs/0errors. Existing legacy/current Agenda Builder paths retained.

Required full Python regression is running as owned exec5136 (work/trial-access/boardable-meeting-full-job.json, started2026-11-16T22:11:29Z; cancelCtrl-C5136); its result is not yet claimed. Receipt docs/verification/boardable-meeting-write-2026-11-16.json pins new source/tests/dependency hashes; previous2984-pass receipt remains historical. Recurrence, multi-day, scheduler, draft preparation, publication, invitations, imports and general Document Center uploads remain open. No payment, vendor contact or release. All31 goal remains incomplete. TownCloud request remains submitted; pursuit ended per Scott.

### Boardable meeting candidate verified —2026-11-16 final state
Exec5136 TERMINAL exit0:3010passed/0failed/0errors/0skipped in256.23s, one upstream Starlette/AnyIO deprecation warning. FullJUnit work/trial-access/boardable-meeting-full.xml; jobrecordpassed. Verified all four new meeting source/wrapper/test/pyproject hashes still match receipt docs/verification/boardable-meeting-write-2026-11-16.json, then pinned full regression/JUnit hash. Separate131affectedPASS19.31s, all-field updatePASS,25metadataPASS1.22s, RuffPASS,diffcheckPASS. Final validator31providers/34formats/341operations/190outbound/472evidence/298URLs/0errors; runtime synced. Client unchanged, prior evidence reused. Earlier draft coding jobs20388/5593 also terminal; NO owned background jobs remain. HEAD897442bf99dff40c4bd03126009083ad9fd485a3 plus preserved dirty local candidate; no commit/push/release.
Boardable single private unpublished no_remote meeting create/update is locally implemented and verified. Recurring/multiday/scheduler/draft preparation/publication/import/general Document Center remain incomplete. Next authorized work remains missing API contracts across the original31vendor list, especially Essential exact GET envelopes/offset progression and TelVue exact uploadresponse/native media identity/original readiness. TownCloud ended per Scott; leave request submitted, no signup/contact attempts. Goal remains active and all31 incomplete.

### SuiteOne producer format and TelVue media identity recovered —2026-11-16
This continuation made concrete contract-research progress. Previous goal turn was progress (Boardable meeting adapter plus3010passing tests). No current product implementation changed this continuation; prior3010pass evidence remains attributed to that candidate.

SuiteOne: followed the official DCR2 Player5.0 build9583 download from BIS Digital (14784116byte ZIP SHA2560d56d9ca75c9b48a2842921c92d5a6ceeca4fe2fdf234ef5047a6ae1ee898027). Statically extracted MSI/CAB/CHM and inspected selected managed HCWordAddIn exporter classes with existing ILSpy; no installation/application execution. Actual classic_content.HTML controls contain caption/name and StartMeUp(native marker index), optional FILETIME clock caption, and special before/after indices. Playback positions are separate companion/player data; modern HTML5ChgPlayPos(seconds) is a different output. Native producer structure is now known.

Crucial SuiteOne primary follow-up: public WordPress media index revealed official March2021 post-recording guide. It specifies uploading the matching exportedWMV, then_content.HTML through Minutes HTML/importandBookmarks, and says bookmarkduration times fill aftermedia processing. This supplies the missing historical media/marker connection. It is distinct from August2021 Bookmarks-tab instructions; current staff request/save/readback and parser applicability remain unmapped. Sources: https://bisdigital.com/software and https://getsuiteone.com/wp-content/uploads/2021/03/LMR-S1_PostMeeting_Step-by-Step-Guide_Video-Bookmarks2021.pdf . Evidence docs/capabilities/evidence/suiteone-dcr2-export/source.json. Official59s demo inspected; Examples.zip contained only24minutesPDF/transcriptTXT files, no nativeHTML/DCR. Four declared public SuiteOne scripts fetched200, no bookmark importer consumer. Intermediates work/suiteone-dcr2-static/.

TelVue: current vendor uploader's populateNewEpisodeForm reads response.medium_id for episodes/new; summary separately reads asset_ids. Nested nonempty episode medium title/short_summary/episode_identifier fields also recovered. ArchiveCDX32JSrows led to two2015application scripts; September2015 confirms same consumers. It still takes runtime fileUrl; no concrete api/v1 initializer surfaced. Scoped evidence docs/capabilities/evidence/telvue-upload-identity/. Do not assign the episode response to unmatched legacyv1upload. No upload sent.

Essential saved Postman/client/archive assessment re-read: exact authenticated GETenvelopes andoffset progression still missing. PrimeGov declared Renoportal GET now403; stopped that access path, no bypass. TownCloud remains parked per Scott. No accounts/contact/payment/release this continuation.

Final metadata validator PASS:31providers/34formats/341operations/190outbound/474evidence/300URLs/0errors; runtime synced. Allowned commands terminal, no backgroundjob. HEAD897442bf99dff40c4bd03126009083ad9fd485a3 plus preserved dirty candidate. All31goal ACTIVE/incomplete. Next pursue another applicable missing contract/access lead; do not repeat exhausted Essential public-client chains or mistake SuiteOne index asseconds. No new synthetic/remote acceptance claimed for recovered producer facts.


### Boardable recurrence and current MediaManager schema — 2026-11-16

TownCloud remains parked at the submitted trial request, per Scott. Boardable trial
created private weekly series12615 with two occurrences526612/526613 (November16/23,
5:30–6:30pm America/New_York). Independent canonical JSON reads200 verified shared
seriesID, separate nativeIDs and recurrenceIDs; series collection POST
/meeting-series/12615/data with empty JSON returned can/meeting/past/today/future/
unpublished. No invitations/publication. Whole-series /edit/all uses original
meeting endpoint meetings_v2/526612 with editType Series, series_choice subsequent.
Initial series time defaults differed from persisted occurrence times; no edit saved.
Create request/response evicted before capture, so persisted series.data is readback,
not a claimed exact submitted payload. Recurrence adapter remains unimplemented.
Pinned minimized recurrence captures + followup-2026-11-16.json under existing
boardable-meeting-form evidence. Screenshot outputs/boardable-private-series-verified.jpg.
CUA completed; boardTab200074887 markedHandoff, former agenda tab200074893 is gone.

Public current MediaManager WSDL GET200,91440rawbytes pinned as
granicus-platform/current-2026-11-16.wsdl with separate followup manifest. Compared
against pinned PHP WSDL:11additionaloperations,3changedtypes. Current structured
PublishClipData/Result confirm existing implementation. MinutesDocumentData unchanged
five fields, no templateGUID/originalfileURL. Exact additional upload-registration/
assignment signatures recovered (BeginFileUpload/EndFileUpload/AssignClipUpload/
AssignClipUploadWithDuration/registerFileUpload); actual byte-transfer destination,
protocol, readiness/hash mapping unresolved. No SOAP credential/mutation invoked.

Original pinned source manifests preserved byte-exact; new evidence is in separate
followup files, retaining existing synthetic acceptance bindings. Metadata25PASS2.41s;
validator31providers34formats341operations190outbound474evidence300URLs0errorsPASS.
No product source/test/dependency changes this continuation; prior3010pass fullsuite
remains applicable to unchanged code. Candidate HEAD897442bf plus preserved dirty
work. No accounts/payments/vendorcontacts/releases this continuation. No owned jobs.
All31 goal active/incomplete. Next: recover exact recurrence submission/status and
series update/readback semantics before implementation; follow current MediaManager
upload methods only through matching primary client/transfer evidence. Do not repeat
TownCloud signup or exhausted Essential public-client/archive chains.


### Weekly Boardable series implemented; current full regression running
Exact weekly create201 and minimal series metadata update200 contract is implemented
in boardable_series_write.py, explicitly selected by current_meeting_form and
current_meeting_series. Native original leader/series binding, complete occurrence
reads, predecessor/schedule verification, preflight conflict checks, narrowed series
grants, durable identity and no-replay recovery. Single and both agenda modes retained.
134 affected scratch checks PASS333.19s before two localized creation publication
guards; final guards plus both native-capture replay cases4PASS13.46s. Integrated
independent combined title/description/location update PASS, both native IDs and
literal14:00Z dates preserved, one mutation. RuffPASS,diffcheckPASS. Current metadata
validator31providers34formats341operations190outbound475evidence300URLs0errorsPASS.
Scoped receipt docs/verification/boardable-series-write-2026-11-16.json. Prior receipts
remain historical; they are not rewritten to claim the newly changed wrapper.

Owned full Python exec26962 ACTIVE, started2026-11-16T23:14:02.9500314Z, expected
work/trial-access/boardable-series-full.xml, cancellationCtrl-C26962; jobrecord same
prefix-full-job.json. Headroom~32.3GiB before launch. Source/tests/pyproject frozen,
703 input hashes in boardable-series-candidate-hashes.json. All coding workers
82240/57929/13515 terminal; earlier scratch test jobs terminal. Only owned full26962.
Next poll SAME26962 and inspect actual terminal JUnit, verify source hashes, then
update receipt/runtime metadata and final report. Full regression result not claimed.
No payment/contact/release. TownCloud parked. All31 goal remains active/incomplete.


### Boardable Document Center native contract recovered; series regression remains active
Authorized evaluation document1270573 created with exact native root-folder multipart
POST /quorumrelay-evaluation/documents201. Fields file,title,body,disable_downloads,
folder0. Native raw JSON returns ID, UUID slug4456b3ae, canonical URL and original
download URL. Metadata multipart save POST /documents/1270573 returned200; automatic
navigation evicted its response body, explicitly not claimed. Exact separately
declared JSON title-only POST returned200 with raw document. Client method disclosed
GET /documents/4456b3ae/data; independent GET200 before/after title update confirms
same ID/URL/title/file metadata. Original download200118bytes SHA256
6255a5838ad4f46e2efc7f78d040e688d0b3f58d1fe646d36ca474fba13b6d9b
matches synthetic uploaded bytes both before and after update. Native automatic PDF
conversion completed; original and converted-PDF URLs are distinct.
Nine sanitized contract/fixture files plus manifest pinned separately at
docs/capabilities/evidence/boardable-document-center/. No new adapter integrated and
no existing evidence manifest/receipt rewritten for this research. Replacement UI
inspected then cancelled on its irreversible annotation-loss warning; no replacement
request sent. No notifications/sharing/invites. Screenshot
outputs/boardable-document-center-verified.jpg. CUA finished, boardTab200074887 marked
handoff on canonical document page for authorized continuation.

MediaManager follow-up: official GitHub search BeginFileUpload/registerFileUpload
returned no code results. Public tenant login only declares generic jQuery/Bootstrap.
Current GetTemplates/GetTemplate returns numeric TemplateData.ID; generated minutes
requires templateUid string. No mapping between these identities recovered, no byte
transfer schema or generated-file readback added. Public eSCRIBE help adds workflow
and file-size rules, no matching DocumentUpload chunk assembly contract.

Owned exec26962 full Python regression still ACTIVE, last live output40%, no failure
reported. Same frozen703 src/tests/pyproject inputs. Continue polling same handle,
then work/finalize-boardable-series.py verifies terminal job/JUnit/source hashes and
updates only receipt/inventory. Sync runtime and run affected25metadata checks after
that bookkeeping; no duplicate full regression. No other owned jobs. TownCloud
parked at Scott's request; no payments/vendor contacts/releases. All31 goal incomplete.


### Boardable weekly-series candidate verified — final 2026-11-16 state
Owned full exec26962 TERMINAL exit0:3042passed,0failures,0errors,0skipped,
2119.37s console /2119.263s JUnit; one upstream Starlette/AnyIO deprecation warning.
Started23:14:02Z, finished23:49:24Z.703 frozen src/tests/pyproject hashes verified
unchanged before receipt/runtime bookkeeping; scoped receipt file bindings also
verified. Full JUnit SHA256
1c5736eddb169805de54aaeec38c5cacc948abbc0c3000a6f2adf44bcbab35e3.
Receipt docs/verification/boardable-series-write-2026-11-16.json and corresponding
inventory evidence now pin the full regression. Only generated runtime capability
metadata changed afterward; focused25metadata tests PASS1.04s. ValidatorPASS:
31providers,34formats,341operations,190outbound,476evidence,301URLs,0errors.
Runtime sourceSHA3e4136a2d5196a7c2a21bb296d450e131e1a8fb15716bc9e552edc374f9be720.
Repository diffcheckPASS; prior RuffPASS reused with unchanged Python source/tests.
Client unchanged; prior client checks reused. HEAD remains
897442bf99dff40c4bd03126009083ad9fd485a3 plus preserved dirty local candidate.
No commit/push/payment/vendor contact/release. No owned background jobs remain.

Implemented/verified: native private unpublished owner-only weekly interval1 series
creation and original-leader whole-series title/description/location updates, complete
occurrence ID/date/UTC verification, trusted grants, preflight conflict detection and
durable no-replay recovery. Native trial requests separately executed on series12616
and IDs526618/526619. Other recurrence patterns, schedule changes, multi-day/scheduler,
publication/invitations/import are not claimed by this scoped adapter.

New research: root Document Center upload201, metadata updates200, exact detailGET200
and original-byte hash verified on document1270573; separate native-only inventory
entry boardable-document-center-native-2026-11-16 pins source/fixtures, no adapter
acceptance claim. Canonical screenshot outputs/boardable-document-center-verified.jpg.
Root Document Center evidence does not by itself settle the existing meeting_document
association requirement; preserve that distinction before proposing product changes.

Additional eSCRIBE Windows-app lead followed: current Microsoft listing
https://marketplace.microsoft.com/en-us/product/escribe_software.escribe_windows_app
offers Contact me and requires appropriate licensed eSCRIBE access module. No public
installer recovered, no contact sent. MediaManager transfer/template-UID linkage and
Essential authenticated response/offset contracts remain unresolved as recorded.
TownCloud remains parked at Scott's request. All31 goal remains incomplete/active.
Next action: continue an applicable original missing-contract lead; reuse this passed
candidate evidence, avoid exhausted Essential archive/client chains and TownCloud.
Do not turn untested native replacement/publication/import subflows into new mandatory
requirements or describe root-file upload as meeting association.


### Meeting-document native contract recovered; isolated implementation draft active
Previous goal turn made progress: weekly-series candidate3042PASS and25metadataPASS,
plus new Document Center native contracts. Current continuation recovered the actual
original meeting_document:upload path, distinct from general Document Center files.
On private meeting526577/org46098/owner403839, native POST /attachments/upload200
text/html EMPTY response; multipart attachments[0][file],attachments[0][type]=upload,
attachable_type=meeting,attachable_id=526577,folder_id0,original_token=undefined string.
Read-only native POST /attachment-list raw items/folders/current_folder/breadcrumbs;
current client has no pagination for this list. First attachment684953118bytes; second
controlled before[684953],after[684953,684954],141bytes. Independent canonical meeting
JSON200 resource.attachments gains exactly same native ID with explicit association.
GET /documents/{uuid.short_slug}/data200 confirms meeting/org/owner; original download
200141bytes SHA256785229e6354d8899d43e6c9bc083204360c51593717c738aca05c00dcc513ab5.
Old row unchanged; native meeting raw diff only display times, resource attachment list.
No publication/invites/notifications; no replacements. Screenshot
outputs/boardable-meeting-document-verified.jpg. CUA completed; trial tab200074887
marked handoff. Nine sanitized capture/fixture files + manifest pinned separately at
docs/capabilities/evidence/boardable-meeting-documents/. Existing proof manifests intact.

Owned isolated coding draft exec60288 ACTIVE, started2026-11-17T00:01:34.4875100Z,
existing authorized DeepSeek1017LOW, headroom~33GiB. Expected
work/workers/boardable-meeting-documents-files.json; jobrecord same prefix-job.json;
cancelCtrl-C60288. NO code integrated, prior3042PASS candidate unchanged. Next poll
SAME60288, inspect new module/tests + tiny wrapper edits, run meaningful affected
checks in scratch before integration. Requirements: exact trusted meeting grants,
root one-file upload, complete native-ID delta across canonical/list views, durable
identity before cancellation/readback, exact association+original-byte hash, no title
lookup or upload replay. Empty response is expected; zero/multiple new IDs uncertain.
Do not implement unrelated root Document Center entity, folders, replacement, publish
or invitations. All31goal active/incomplete. TownCloud remains parked; no payments,
vendor contacts, commits/pushes/releases. No other owned background job.

### Boardable meeting-file contract recovered — November 16

The trial exposed the actual meeting Materials upload, separately from the general
Document Center. Two synthetic files were uploaded to private meeting526577. The
second controlled upload added native attachment684954 while preserving684953.
Both native upload requests returned HTTP200 with an empty body. Independent
meeting JSON, the root attachment list and exact document detail confirmed the new
attachment's meeting, organization46098 and owner403839. Downloading the original
returned the exact141sourcebytes, SHA256
`785229e6354d8899d43e6c9bc083204360c51593717c738aca05c00dcc513ab5`.

The native request, before/after responses, detail, client logic and source bytes
are pinned in the repository's `boardable-meeting-documents` evidence directory.
The upload adapter is integrated after 196 passing affected coordinator/SQLite
tests. Its required full Python regression subsequently passed all 3,102 tests;
all 725 frozen inputs matched the tested candidate. No publication, invitations,
replacement, vendor contact or release.
TownCloud remains parked at Scott's instruction.

### Legistar client-distribution follow-up

The official [Legistar Technical Solutions Guide](https://support.granicus.com/articles/en_US/Knowledge/Legistar-Technical-Solutions-Guide)
confirms that its Windows launcher downloads application files before sign-in.
The official troubleshooting guide identifies `Legistar5.exe` and
`LegistarLaunch.xml`, but the retrieved material supplies no public installer or
application-file URL. Targeted searches for those exact filenames and installer
names did not recover a distributable client. This follow-up adds a concrete
client-distribution lead, but supplies no new file-import or recording-byte contract.
No application was installed or executed.

### Meeting-document adapter integrated; required full regression active
Combined isolated regression66262 TERMINAL PASS196/0fail/0error/0skip,593.09s.
Exact three files integrated: boardable_meeting_documents.py, boardable_write.py
routing and test_boardable_meeting_documents.py. Source hash6e8871a8f90ff32b92b95b3956f3d7418d93c424574c6805310da03c6340c21a;
wrapper b6f08b5bbbf398c498fcd25b17c480c1bbe6ddd06d9ad2edabd0c58f8c222380;
test2de2825d7d428b10f0d8b95a1de521e9ba76075ea20cf15615c9ebbc5372254c.
Usage docs appended, scoped new receipt docs/verification/boardable-meeting-documents-2026-11-16.json;
older manifests/receipts preserved as historical. Inventory upload and meeting_document
mapping updated from actual native captures and local acceptance. Added only exact
new Boardable/meeting_document/upload tuple to validator's existing attribution set;
first edit application failed due CRLF, diagnosed and normalized exact-match safely.
Validator PASS31providers34formats341ops190outbound477evidence302URLs0errors;
25metadataPASS0.99s; required Ruff src/tests/scripts/examplesPASS; diffcheckPASS.
Runtime source f76377f6754c0b7c4e5ac7c59786e82d1cc9dd79060519504ba170558814775b.
All worker/coding and affected jobs terminal. Owned full Python exec80608 ACTIVE,
started11/17/2026 00:58:13, headroom33.4GiB; expected
work/trial-access/boardable-documents-full.xml and .log; jobrecord same prefix-full-job.json;
cancelCtrl-C80608.725 source/test/script/example/config input hashes frozen in
boardable-documents-candidate-hashes.json. Next poll SAME80608, inspect terminal
JUnit and verify frozen hashes, update receipt/runtime bookkeeping and affected
metadata only afterward. Full result NOT claimed. Client unchanged; prior evidence
reused. No payment/contact/commit/push/release. TownCloud parked. All31 goal remains
active/incomplete. Native browser upload/hash executed independently; adapter live
execution remains false (no exported browser credentials used).
### Boardable advertised API access checked against the trial

The current [official pricing page](https://boardable.com/pricing-details/) lists
API access under Professional and advertises a Professional+ trial. In the active
QuorumRelay Evaluation account I inspected Organization Settings, Subscription and
User Settings → Integrations. Organization Settings has six configuration tabs;
Integrations offers Zoom, Microsoft and Google Drive. These inspected pages expose
no API-key creation control or developer reference link. Subscription's in-app
feature comparison also has no API row. No plan selection, payment, credential
creation, integration connection, settings save or vendor contact was performed.
The recovered native meeting, agenda, series and supporting-file contracts remain
the executable integration route obtained from this trial.


### Simbli staff-client contracts recovered — November 16 follow-up

The official public [Angular entry point](https://simbli.eboardsolutions.com/SB_Assets/AngularOutput/main.js)
names staff work-in-progress, workflow, meeting-item and minutes-administration
modules. Following those exact imports recovered additional staff behavior in
the [meeting client](https://simbli.eboardsolutions.com/SB_Assets/AngularOutput/chunk-XH3WJOAC.js)
and [shared service client](https://simbli.eboardsolutions.com/SB_Assets/AngularOutput/chunk-5FTFBQVD.js):

- Selected agenda-item save posts to `/Services/api/MeetingView/SaveAgendaItem/`
  with `{EncrID, itemDetailsDTO, itemContentDTO}`. The native editor starts from
  the fetched details/content and reads the item again after saving.
- Item creation fetches its initial model from `/Services/api/AddItem/` and
  posts the populated model to the same route with an explicit insertion position.
- Tree reordering posts the full changed tree to `/Services/api/SaveAgendaTree/`.
- Minutes save clones the model and encodes its Minutes field with
  `btoa(encodeURIComponent(...))` before posting `/Services/api/SaveMinutes/`.
- Publication posts the complete publish model to
  `/Services/api/SaveMeetingPublishDetails/`, including authorized/public dates
  and nested agenda/field visibility.

These routes require the native page's session, encrypted identifiers and user
context. Item editing also calls `GetItemEditAccess` and the host's
`ReleaseItemEditing` function. An earlier saved host page supplied the missing release request and initial lock
DTO. Lock acquisition posts JSON to `/api/Workflow/GetItemEditAccess/`; release
posts the same native lock model to `/api/Workflow/ReleaseItemEditing/` using
`application/x-www-form-urlencoded`. The model contains SessionID, UserID,
Username, ItemID, MeetingID, SiteID, LastActivity and Access. The published Angular
bridge explicitly maps null to an empty string and other values with String().
There is no new Simbli write adapter yet; these recovered contracts now support
scoped implementation with native-lock handling and independent item readback. Public selected-item
response data was already recovered and supported by the existing reader.

The public meeting page returned HTTP200 with its full host page once, then
returned a smaller access page on repeat requests; retries stopped. Its declared
master and voting scripts supplied no lock-release implementation. Static assets
and their hashes are retained in the investigation work folder. No staff API call,
account creation, vendor contact or publication occurred.


### Latest verified Boardable candidate

The integrated meeting-document adapter passed the required full Python suite:
**3,102 passed, zero failures/errors/skips**, 1,741.85 seconds. All 725 frozen
source/test/script/example/config inputs matched before proof bookkeeping. The
receipt and capability inventory now record that result. The subsequent 25
capability/evidence tests and capability validator passed; required Ruff and
diff checks also passed. Runtime inventory source SHA256 is
`6500fdcbc7ec186feb4083a105615f73100248837fbdbc329d644dfc394323ce`.
The adapter's executed acceptance uses captured native responses and synthetic
transport through Engine/SQLite; the browser's native uploads and original-byte
checks are separately recorded. No adapter request used exported trial credentials.

TownCloud remains parked. The full 31-vendor goal remains incomplete. Simbli's
newly recovered staff-client contracts are research findings awaiting scoped
implementation; other unresolved vendor contracts remain listed above.
