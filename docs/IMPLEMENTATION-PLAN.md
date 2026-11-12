# QuorumRelay — bounded implementation plan

Owner: Scott. Planning date: November 11, 2026, America/Denver.

Status: implementation authorized and resumed by Scott on November 11, 2026. Build QuorumRelay under Townlight with coordinated Sol, Terra and Luna agents, preserving the full scope and every acceptance requirement. Naming and earlier pause decisions below are retained as history; this resume supersedes the pause only.

Revision: November 11, 2026 — Astra source-review findings and technical clarifications, added at Scott's request. This revision preserves every original scope commitment and acceptance requirement. It authorizes no implementation. The inventory details the full existing commitment; it is not a selection gate for a smaller release. All 31 source families, all 34 baseline formats, every specified interface, all four reference integrations, and every verified supported outbound operation within the agreed data domain remain required. A missing credential or test environment leaves the applicable work blocked and incomplete; it does not make the work optional or establish that the provider lacks the feature. Scope reductions require Scott's explicit approval.

## Approved organization and project naming

Scott approved these decisions on November 11, 2026:

- **Umbrella organization: Townlight.** Use the existing Townlight organization for the project family. The family includes the Townlight municipal suite, CivicCast, CivicCast Brief, TownRecord, TownReporter, Describer Workbench, and QuorumRelay. The umbrella organization and the Townlight municipal suite are distinct concepts; each product retains its own identity.
- **This project: QuorumRelay.** This is the name of the independent civic-data connector project specified in this plan. Its intended repository home is `townlight/quorumrelay`. Repository creation, existing-product transfers, package reservations and public branding changes have not been performed by this planning update. Package/import/CLI identifiers will be recorded when established during authorized implementation; the project name is settled.
- **Independence remains required.** Townlight organization membership introduces no requirement to install the Townlight suite or use its database, runtime, authentication or other products. QuorumRelay retains every standalone interface and external-developer acceptance outcome below.
- **Organization membership does not change integration scope.** The four required reference integrations remain Townlight, TownReporter, CivicCast Brief and TownRecord. Including CivicCast and Describer Workbench in the umbrella family does not add new reference integrations or reduce any existing obligation. Repository transfers and an umbrella website reorganization are not added to this connector implementation plan.
- **Full scope and acceptance are preserved.** All 31 source families, all 34 baseline formats, every specified interface, all four reference integrations, and every verified supported outbound operation within the agreed data domain remain required. All work-package acceptance criteria, documentation and delivery requirements, exclusions and incomplete/blocker semantics below remain unchanged.
- **Implementation remains paused.** The next execution step, only after Scott lifts the pause, is the existing repository/capability-inventory work package using the approved name. No implementation jobs are started by this update.

## Outcome and scope

Build an independent, reusable civic-data connector project that any product can use to identify configured provider sources, discover available records, retrieve and search information, import records, export information, and write back through supported provider interfaces.

The first release covers all 31 existing source families and preserves all 34 existing input-format combinations. It supplies Python, CLI/JSON, HTTP/OpenAPI, and MCP interfaces, a TypeScript HTTP client, schemas, examples, and an extension interface. No Townlight installation, Townlight database, newsroom application, or model provider is required to use it.

Townlight, TownReporter, CivicCast Brief, and TownRecord are four reference integrations included in this plan. They prove practical interoperability; they do not define which products may use the project. An unrelated developer must be able to build a fifth client from the public package, API, and documentation alone.

The bounded data domain is meetings/events, agenda items, agendas/packets/minutes, other linked meeting documents, recordings/media metadata and supplied captions/transcripts, and their source relationships. Include structured motions, votes and related fields only when a source supplies them. This is not a commitment to implement every record type or administrative feature inside each vendor's entire platform.

Licensing is excluded from this plan at Scott's direction.

## Verified starting point

- Townlight's `meeting_imports.py` contains the 34-reader registry, version-1 normalized JSON, tenant namespaces and capture hashes. `meeting_import_fetch.py` contains public-network fetching, redirect/DNS checks and document retrieval. Four original JSON readers currently call Townlight Core; that dependency must be extracted too.
- The released Townlight workflow saves canonical meetings and supports its documented module handoffs. The new project must preserve those identities and calls while replacing the underlying implementation with a pinned standalone package.
- CivicCast Brief has an opt-in Townlight subprocess reader and existing source configuration/discovery. Its current configuration includes sources beyond this project's 31; those remain functional without adding them to the new library's target count.
- TownReporter has configured PrimeGov retrieval, document processing, source/scan jobs and newsroom-specific evidence storage. Its existing auth, editorial workflow, model settings and scheduler remain the owning systems.
- TownRecord has an implemented PrimeGov records adapter, sync/download/extraction jobs and authenticated local API. Its README still describes a specification-only project. Integration must follow the implemented code, preserve existing records/jobs and correct the directly affected stale documentation.

These are source findings, not a new installed acceptance claim for any consumer.

### Additional source findings from the November 11 review

The review inspected current default-branch source for Townlight's readers, fetcher, import routes, persistence and Core normalization; TownReporter's PrimeGov retrieval; CivicCast Brief's source configuration, importer client and selected discovery implementations; and TownRecord's adapter, dispatch and sync jobs. It also checked official Legistar API and MCP transport documentation. It did not run the applications, repeat installed acceptance or perform the 31-provider capability investigation required by package 1. These observations guide implementation; they do not satisfy the later acceptance requirements. Pin the actual source revisions when implementation begins.

- **Extraction foundation:** Core's four original JSON mappings reside in a small normalization module with data classes and validation. The inspected module does not require an application database. The shared reader's version-1 output is a narrower contract than the richer record envelope proposed below: preserving selected normalized fields and a capture hash does not yet preserve every original value, extension or revision.
- **Retrieval foundation:** Townlight's public fetcher validates DNS addresses used by the actual socket, checks redirects and enforces deadlines and byte limits, with optional streamed output. Its general fetch operation uses GET; provider POST requests, authenticated sessions and broader pagination are additional work. Preserve those network safeguards as request capabilities grow.
- **Discovery reuse:** Brief already follows CivicClerk pagination, submits an eScribe calendar date range using POST, and obtains Laserfiche folder listings through its browser integration. Its lookback windows, result caps, cancelled-meeting filters and preferred document types reflect the Brief workflow. Reuse the retrieval mechanics while expressing those choices through the shared bounds and result contract. Existing implementations are reusable source evidence, not proof of complete discovery for every tenant.
- **Partial results:** TownReporter's PrimeGov portal reader carries independent upcoming/archive failures and marks partial catalogs. Some convenience calls return only the meeting list. Preserve failure and coverage information through the complete new consumer path, including convenience interfaces, so a partial read cannot silently become a complete result.
- **TownRecord coupling:** Its adapter types use integer meeting IDs and PrimeGov document template/compile-output fields; `adapter_for` directly constructs a PrimeGov adapter. Its sync maps meetings to durable records and queues document/caption/alignment work while retaining individual failure reasons. Generalizing the adapter also requires compatible job payloads and persistence mappings, rather than only changing dispatch.
- **Townlight identities:** Import persistence derives its source key from connector, namespace and external meeting ID, and separately hashes the normalized meeting. It creates canonical records transactionally and reports unchanged, changed-source or missing-destination outcomes on repeat imports. Retain these semantics and existing destination IDs through extraction.
- **Different input meanings:** The original Legistar export reader expects `MeetingId`, `MeetingName` and `MeetingDate`; the documented event API uses fields including `EventId`, `EventBodyName` and `EventDate`. The existing export reader must remain supported while live API responses receive their own explicit mapping. The current Tyler reader skips cancelled/adjourned entries; the richer shared model must retain supplied status information needed for revision tracking while the compatibility adapter preserves existing import behavior.

## Fixed provider roster

Every row participates in capability research, discovery implementation where available, normalized import, local search, neutral export, and the assessment/implementation of supported outbound paths. The input column describes the existing baseline, not a claim of complete live discovery today.

| # | Provider/source family | Existing supported input formats |
|---|---|---|
| 1 | Legistar | Townlight Core meeting-export JSON |
| 2 | PrimeGov | Core meeting-export JSON; public portal meeting-list JSON |
| 3 | Granicus | Core meeting-export JSON; ViewPublisher HTML |
| 4 | NovusAGENDA | Core meeting-export JSON |
| 5 | CivicPlus Agenda and Meeting Management Select | Public Events JSON |
| 6 | CivicPlus Agenda Center | Listing HTML |
| 7 | Municode Meetings | Meetings HTML |
| 8 | BoardBook | Public organization HTML |
| 9 | eSCRIBE | Calendar JSON |
| 10 | Simbli | Meeting-list HTML |
| 11 | iCompass CivicWeb | Meeting-type listing HTML |
| 12 | iQM2 | Meeting-list HTML |
| 13 | Granicus Swagit | Video-archive HTML |
| 14 | SuiteOne Media | Meeting-archive HTML |
| 15 | Granicus Peak | Agenda-center/ViewPublisher HTML |
| 16 | Utah Public Notice Website | Notice-detail HTML |
| 17 | Destiny AgendaQuick | Meeting-list HTML |
| 18 | Town Hall Streams | Archive HTML |
| 19 | TelVue | Playlist HTML |
| 20 | CHAMP | Event JSON |
| 21 | Hyland OnBase Agenda Online | Agenda Online HTML |
| 22 | Laserfiche WebLink | Saved dated-folder HTML |
| 23 | TownCloud | Saved agenda-table JSON; agenda-detail HTML |
| 24 | Digital Towpath | Meeting-detail HTML |
| 25 | ClerkBase | Meeting-document HTML |
| 26 | Municipality-published calendar | Public iCalendar feed |
| 27 | Wistia | Public media JSON |
| 28 | Boardable | Public meeting-detail HTML |
| 29 | gWorks FrontDesk | City-meetings JSON |
| 30 | Diligent BoardDocs | Unencrypted printed numbered-agenda PDF |
| 31 | Tyler Meeting Manager | Saved public-calendar JSON |

There are 34 combinations because PrimeGov, Granicus and TownCloud each have two existing formats. Discovery may require additional provider response formats; add those when necessary without changing the fixed list of 31 families or losing any baseline reader.

## Shared architecture and developer contract

One connector engine owns provider-specific identification, discovery, retrieval, normalization, export mappings and write adapters. Thin interfaces call that engine. Consumers own their application records, staff/editor roles, editorial/publication decisions and business workflows.

The project supplies an optional local capture/search store and a storage extension interface. A product may use that store or map records into its own database. Installing the library must not require a hosted service, central city directory, AI model, vector database or application-specific database.

### First-release interfaces

| Interface | Required behavior |
|---|---|
| Python SDK | Typed records and operations usable in-process without an HTTP server or Townlight runtime. |
| CLI | JSON request/result contract; stdin/stdout, saved-file input, JSONL for bulk records, stable exit/error codes. Machine output on stdout; diagnostics on stderr. |
| HTTP API | Versioned JSON REST endpoints, OpenAPI, multipart/file-handle inputs and streamed file downloads where needed. Loopback default; explicit authenticated deployment configuration for network use. HTTPS can terminate at an existing reverse proxy. |
| MCP | stdio and Streamable HTTP transports exposing the same engine operations and capability limits; conform to the negotiated supported protocol version. |
| JSON schemas | Versioned record, source, query, capability, error, change-plan, receipt and interchange-manifest schemas. Examples validate against those schemas. |
| TypeScript client | A small HTTP client and generated record types, proving a non-Python application can use the service. Other languages use HTTP/JSON, OpenAPI or CLI. |
| Connector extension interface | Documented registration and typed hooks for identification, discovery, fetch/parse, native search, export and write-back; fixtures and a conformance test helper. A new connector must not require changes to all transports. |

HTML, JSON, PDF and iCalendar are provider input formats. They are not separate developer transports. Where a provider needs POST requests, cookies, pagination, a signed download or a browser-generated capture, its connector handles the supported path or reports exactly what input/access is needed. No generic unrestricted HTTP proxy is exposed.

### Common operations

Use equivalent SDK calls, CLI commands, HTTP routes and MCP tools for:

- List providers/formats and inspect capabilities.
- Identify a provider/source from a URL; validate an explicitly configured tenant/body.
- Discover records within explicit source/date/type bounds, with pagination/checkpoints.
- Fetch a record or attachment and normalize a saved capture.
- Search selected sources/captures with dates, body, record type, exact terms and phrases.
- Preview an import, then return a normalized bundle for a consumer to save.
- Build an interchange/provider-specific export and return its manifest.
- Plan a supported provider write, commit an authorized plan, and read its receipt/status.
- Query progress/results and cancel bounded long operations. Consumers can also call the engine synchronously from their existing job system.

An operation reports completed, partial, cancelled, failed or unsupported explicitly. A failed fetch or incomplete discovery never becomes a successful empty search result. Search responses identify the searched sources, dates, available text, failures and truncation.

The record envelope keeps schema version, provider, tenant namespace, external ID, record type, relationships, source/citation URLs, capture timestamp/hash and source revision. Preserve original field values and unknown extensions. Unknown time zones, missing agenda items, absent minutes and unsupported fields stay explicit. A short-lived signed download URL does not replace the durable citation.

### Technical clarifications for the existing contract

**Identity and revisions.** Define source identity, source revision, capture identity and application record identity separately before expanding the interfaces. Source identity includes the provider, stable tenant namespace, record type and provider identifier, plus parent identity where the provider scopes identifiers to a parent. Keep legacy identity mappings explicit: adopting the richer envelope must not change existing Townlight source keys or duplicate existing consumer records. A capture hash identifies captured bytes; a normalized-content hash detects normalized changes; neither alone establishes an upstream revision or permission to overwrite a destination. Keep provider-supplied revision values when available and identify locally derived change indicators as such.

**Representing available evidence.** Preserve original fields and supplied relationships alongside normalized values. Retain supplied cancellation/adjournment state and distinguish missing time zones from known offsets. Where a reader derives an identifier from position, a URL or another fallback, document that derivation and its stability limits rather than presenting it as a provider-issued ID. Search coverage and export losses are described against the actual captured fields and text. The version-1 compatibility adapter supplies the existing application contract without making its narrower representation the ceiling of the new model.

**Consumer and service ownership.** For each reference product, document whether it calls the SDK, CLI or HTTP service and who owns service startup/shutdown, configuration, authentication and the pinned version. The TypeScript client must connect to an explicitly configured service with a usable deployment path. Preserve existing application schedulers and roles. Define how the existing storage extension carries captures, checkpoints, change plans and receipts when a consumer uses its own database/jobs; identify the owner of that state. The optional capture/search store must remain optional. A caller using external storage still receives the same progress, cancellation and receipt semantics.

**Request bounds and large files.** Separate parser-input limits from streamed document/media-transfer limits. Townlight's current parser cap is 16 MiB; TownRecord's adapter defines separate HTML/PDF limits and a configurable packet limit defaulting to 200 MiB. These are existing implementation choices to map deliberately, not a single shared limit to impose on every operation. Reused browser/session retrieval must retain tenant boundaries, explicit dependencies and the existing network/file safeguards. Report pagination caps, date coverage, failed pages and unavailable attachments through every transport and consumer.

**Protocol versions.** Record the MCP protocol versions actually implemented and checked, including the applicable transport, authentication, cancellation and compatibility behavior. Interpret the interface table's negotiation requirement according to the supported protocol revision; do not assume every revision uses identical initialization or session mechanics. Keep these protocol details in developer documentation rather than product workflows.

## Bounded work packages

### 1. Establish the repository and capability inventory

**Issue:** Existing reader counts do not establish discovery, search or outbound support.

**Work:** Select collision-checked repository/package/CLI names; create the independent repository when implementation is authorized. Pin the source baseline and identify reusable code from the four products. For each of the 31 providers, inspect official API/import/export documentation and up to two representative public tenant installations where available. Record required account tiers, credentials, formats, entity/field support, pagination, restrictions, evidence URLs and observation dates. Reuse existing captures. Vendor onboarding, paid procurement and indefinite outreach are not automatic project work.

**Done:** All 31 rows have separate entries for identify, discover, fetch, parse, native search, local search, neutral export, vendor-file export and create/update write-back. Each has implementation status and evidence level. Unverified and credentials-blocked operations remain visibly incomplete; lack of credentials alone cannot be relabeled as an unsupported vendor feature. A genuinely unavailable operation has a concrete documented reason. The inventory supplies the finite connector backlog for the remaining packages.

**Inventory detail, preserving scope:** Expand each provider's outbound entries into the explicit entity, operation and field mappings within the agreed domain, including create/update/upload where supported. Associate each entry with its evidence, tenant/account prerequisites, authorized test environment or missing access, and required readback/receipt. This enumerates the existing obligation; it does not authorize choosing an easier subset, restricting writes to Legistar, or moving supported operations out of the first release. Evidence discovered during implementation that establishes another supported operation within the agreed domain belongs in this inventory and the existing acceptance obligation. Unresolved research stays unverified until resolved; it cannot be converted to unsupported merely to close the list.

### 2. Extract the standalone engine without losing behavior

**Issue:** Current readers ship inside Townlight Runtime and four depend on Townlight Core.

**Work:** Move readers, relevant Core normalization, safe retrieval, schemas and fixtures into the new package. Preserve the current normalized JSON contract through a compatibility adapter. Keep provider namespaces stable and separate canonical upstream identity from application database IDs. Transfer reusable discovery/document logic from existing consumers where it improves coverage rather than maintaining duplicate implementations.

**Done:** A clean environment with no Townlight installation can install the package and run all 34 baseline combinations. Equivalent captures produce compatible IDs, records and provenance. No import from Townlight, TownReporter, Brief or TownRecord is required by the core. Existing application calls remain operable through their adapters.

### 3. Implement discovery and retrieval across the roster

**Issue:** Parsing supplied files is not automatic discovery.

**Work:** Add provider recognition, tenant configuration, available listing/detail/document/media retrieval, pagination, date filtering and incremental checkpoints. Implement available public/API paths for every provider. Use account-backed retrieval when the documented endpoint requires an authorized account. Accept saved responses as an explicit fallback. Reuse existing application schedulers; do not build a new scheduling platform.

**Done:** Every provider has a tested discovery/retrieval path for the operations it actually exposes, with a live representative public check where available and deterministic fixtures for repeatable checks. Dates, boundaries and incomplete results are reported. Saved-file-only or credentials-blocked cases are labeled as such. Source changes produce revisions/reviewable changes; retries do not create duplicates. An unavailable attachment does not discard the rest of a meeting.

### 4. Deliver search and reusable imports

**Issue:** Developers need searchable, attributable information and a safe handoff into their own data model.

**Work:** Index normalized metadata and text supplied by captures, HTML, text PDFs and provided captions/transcripts. Supply exact-term/phrase and date/body/type filters across selected sources. Add upstream search only where a provider offers a verified usable route. Keep original files and page/timestamp anchors when present. Search and import preview use the same schema. Consumers decide what to persist and how to resolve changed captures.

**Done:** All 31 providers' imported records are searchable over their actual available fields. Metadata-only content is identified; a scanned/unreadable PDF does not count as fully searched. Results contain citation, revision/hash and matching field/page/timestamp when available. Round-trip import of the same neutral bundle preserves identities and does not duplicate records. Existing consumer OCR/transcription can feed text back with provenance; building a new OCR, ASR or semantic-search system is outside this release.

### 5. Implement exports and supported write-back

**Issue:** Exporting a file, importing it into another product, and changing an upstream provider are different operations.

**Work:** Provide versioned JSON, JSONL and a ZIP interchange bundle containing records, optional authorized attachments and a hash manifest; CSV projections for meetings/items; and iCalendar for meeting/event metadata. Explain projection losses. Implement provider-specific import files where a documented usable format exists. Implement create/update and attachment/media submission for the supported entities and fields found in package 1. Legistar is an evidenced initial candidate, not the assumed only write adapter.

Each remote write has a target provider/tenant/resource, field mapping, validation, a before/after plan and expected upstream version where available. Use the caller's established authorization or saved policy; bind commit to that exact plan. Validate credentials and supported fields server-side. Use idempotency where supported; otherwise reconcile remote identity/readback before repeating an uncertain create. Preserve per-operation results for partial batches. Do not automatically delete records to undo a partial result.

**Done:** Neutral bundles round-trip without losing supported schema data. CSV/iCalendar/provider mappings disclose omitted fields. Every verified supported outbound operation in the agreed data domain is implemented and exercised in an authorized test tenant or equivalent provider test environment, with readback and a receipt. Tests cover duplicates, changed upstream records, partial failures, permission denial and ambiguous network outcomes. A mocked write proves adapter behavior, not live provider acceptance. Missing test access is an explicit remaining blocker. No silent downgrade from a promised supported write to a file download.

**Boundary:** No automatic bidirectional synchronization, deletes, procurement/award decisions or arbitrary vendor administration. Write-back covers explicit create/update/upload operations, not every API endpoint the vendor publishes. Provider capabilities can differ by account/tenant. A calendar feed does not imply its hosting CMS accepts writes.

**Access dependency:** Official API documentation establishes a route to investigate, not usable credentials, permission, conflict semantics or live acceptance. Resolve and record test-access dependencies early. If a required operation remains blocked by access, continue independent authorized work and retain that operation as incomplete. The exclusion of automatic procurement/vendor outreach does not waive the operation or authorize claiming the full release complete. Any proposed scope reduction or separate delivery would require Scott's explicit decision. The existing requirement to bind commit to the exact authorized plan applies equally to SDK, CLI, HTTP and MCP calls, including retries after an ambiguous network outcome.

### 6. Complete API, MCP, SDK and extension access

**Issue:** The engine must be usable by unrelated applications and languages.

**Work:** Implement the interface table above, one schema/error model, bounded pagination/downloads, progress/cancellation and actionable examples. Use current MCP transports/security requirements. Keep local/application credentials separate from upstream-provider credentials. Authentication and capability checks apply in the engine/service, not just in UI controls or MCP annotations. Local file access is explicitly scoped; fetched source text is data, not tool instructions. Preserve DNS/redirect/TLS safeguards and streaming size limits; distinguish small parser inputs from large document/media transfers.

**Done:** An external Python example, a Node/TypeScript example, curl/JSON requests, CLI piping, a stdio MCP client and a Streamable HTTP MCP client all complete the same representative discover/search/import/export sequence. Supported writes use the same plan/commit/receipt contract through those interfaces. Unauthorized writes, cross-client/tenant access, private-network fetches and unsafe paths are rejected. A small example connector passes the extension conformance helper without transport modifications. OpenAPI/schemas match actual responses.

### 7. Integrate the four reference products fully

| Product | Work | Done when |
|---|---|---|
| Townlight | Replace embedded reader implementation with a pinned library and compatibility wrapper. Expose supported providers, source discovery/search/import/export and authorized write-back in the relevant Meetings/evidence flows. Preserve existing staff roles and canonical handoffs to Core, Records, Notice, Access, Station, Code, Boards, Contracts, Procurement, Zoning, Planning, Permitting and Inspections. | One new Windows candidate uses the standalone library, preserves existing imported identities and saved links, and passes the affected setup/import/export/write-plan controls and cross-module handoffs. Verify transition from the released 1.8.1.1 profile/records where the extraction changes persistence or identifiers. Sign and independently verify any Windows installer distributed as the new candidate. The currently released MSI/tag/assets remain intact. |
| TownReporter | Add provider source configuration and shared discovery/search/retrieval to the existing source/scan/evidence paths. Map normalized records into newsroom-specific captures/leads/citations. Add evidence export and expose provider write-back only through an explicitly configured authorized operation. Preserve existing editorial decisions and model/provider settings. | In an isolated working newsroom, configure and discover a source beyond PrimeGov, ingest/search its documents, save/reopen cited evidence, and export it. Verify multiple-newsroom isolation and existing PrimeGov regression cases. Test authorized outbound planning/commit when supported; ingestion never publishes an ordinary story or edits a vendor record by itself. |
| CivicCast Brief | Replace dependence on Townlight's Python executable with the standalone package/client. Generalize source selection/discovery to all 31 capabilities. Carry available documents/media through existing capture/review paths. Add reusable export and supported outbound actions without bypassing producer approval. | A configured provider beyond PrimeGov/Granicus yields a meeting with traceable evidence and usable documents/media where supplied. It reaches the existing review workflow; unsupported media/text is explained. Export and supported write-back remain separate from episode publication. Existing non-library source kinds remain working. |
| TownRecord | Implement a shared-library adapter behind its existing records interface; generalize PrimeGov-only dispatch/jobs for the31 providers. Preserve source health, downloads, page extraction, video/meeting links and authenticated local API. Add shared search/export/outbound access as appropriate while preserving current callers. | A fresh configured source beyond PrimeGov syncs to durable records, downloads an available document, exposes searchable cited content through the existing UI/API, and exports a valid bundle. Repeat sync is idempotent, old jobs/PrimeGov IDs/citations remain valid, large packets respect configured limits, and supported write-back has explicit authorization/readback. Any schema change has a tested non-destructive migration. Correct the affected stale README/manual claims. |

For every product, all 31 providers appear through shared capability/configuration data and all 34 format paths have adapter-contract coverage. Each product also gets an actual end-to-end run beyond its old provider coverage, a saved-capture/limited-capability case and failure/retry checks. This avoids duplicating 34 full manual browser walks in every product while still proving each application's real persistence and workflow wiring. A source that lacks agenda text or usable media must not be advertised as completing a downstream writing or transcription workflow.

### 8. Verify, document and deliver

**Issue:** Code and green unit tests alone do not establish a usable external library or integrated product workflow.

**Work:** Run affected connector/transport/consumer checks and repository-required CI. Reuse the 34-format corpus; add meaningful tests for newly implemented discovery/search/export/write behavior. Use Windows for installed/runtime acceptance; no Linux/macOS release work is included. Keep one coherent candidate and pinned library version across reference clients. Use synthetic records and authorized test tenants for writes; never mutate public city data as a test.

Update the new repository README/landing page, provider capability matrix, quickstarts, SDK/OpenAPI/JSON-schema/MCP references, configuration/authentication guide, connector-author guide, export/write-back limitations and release notes. Update affected README, setup/source UI help, API docs, manuals, maintained mirrors, downloadable editions and public landing pages in the four consumer products. Preserve old release documentation as historical evidence.

**Done:** A developer can install the published library and use each public interface without installing a reference product. All31 provider rows have honest implemented/unsupported/blocked status with proof, all 34 baseline readers pass, all implemented writes have the required acceptance, four reference integrations pass their defined outcomes, required CI passes, and maintained docs agree with the shipped artifacts. Push/merge/tag/package publication and consumer delivery follow the authorization given for implementation; this planning request itself performs none of those actions. Verify public packages/downloads/docs after authorized delivery. Publish one concise handoff identifying versions, source commits, evidence, limitations and any remaining blockers; do not claim completion while an agreed supported operation is still blocked.

## Execution order and stopping boundary

Execute serially: repository/capability inventory; core/schema extraction; discovery/search/import; exports/write adapters; HTTP/MCP/developer clients; four reference integrations; affected acceptance/docs/delivery. Interface design begins with the core schema so adapters do not invent incompatible contracts. Ship one coordinated first release rather than repeatedly rebuilding Townlight while connectors are still changing.

Implementation sequencing clarification: within that serial sequence, exercise the existing representative discover/retrieve/search/import/export acceptance path early through one Python consumer and TownReporter's TypeScript boundary as the needed operations become available. This is incremental execution of the already-required interface and consumer checks, not an additional release, review stage or substitute for the full roster and four integrations. It exposes schema, persistence and service-deployment mismatches before all connectors depend on them. Reuse unaffected evidence for final acceptance; the coordinated public release and every original final acceptance requirement remain unchanged.

No new providers beyond the31, hosted SaaS platform, global municipality directory, payment/billing system, automatic two-way synchronization, new model/OCR/transcription system, or unrelated product completion is part of this plan. Existing product features outside the connector integration are preserved. No licensing work is included.

Completion means the bounded outcomes above are delivered with truthful per-operation coverage. It does not mean every tenant exposes the same information, that every vendor permits writes, or that an access-blocked operation has somehow passed. New provider requirements, vendor negotiations or additional product features require an explicit scope decision.

## Source references used for this plan

- Existing shared 31/34 matrix and interfaces: https://townlight.github.io/manuals/meeting-imports.html
- Townlight engine: https://github.com/townlight/townlight/blob/main/desktop/runtime/python-services/townlight_runtime/meeting_imports.py
- TownReporter PrimeGov source path: https://github.com/scottconverse/TownReporter/blob/main/src/lib/news/primegov.ts
- TownRecord adapter and implemented sync: https://github.com/scottconverse/townrecord/blob/main/core/src/townrecord/adapters/base.py and https://github.com/scottconverse/townrecord/blob/main/core/src/townrecord/records/sync.py
- CivicCast Brief source settings and shared client: https://github.com/scottconverse/civiccast-brief/blob/main/src/civiccast_brief/sources.py and https://github.com/scottconverse/civiccast-brief/blob/main/src/civiccast_brief/townlight_imports.py
- Official example of upstream create/update endpoints: https://webapi.legistar.com/Help
- MCP transports and security: https://modelcontextprotocol.io/specification/latest/basic/transports and https://modelcontextprotocol.io/specification/latest/basic/security_best_practices

Additional sources inspected for the November 11 technical clarifications:

- Core normalization: https://github.com/townlight/core/blob/main/townlight_core/connectors/imports.py
- Townlight safe fetcher and import routes: https://github.com/townlight/townlight/blob/main/desktop/runtime/python-services/townlight_runtime/meeting_import_fetch.py and https://github.com/townlight/townlight/blob/main/desktop/runtime/python-services/townlight_runtime/meetings_bridge.py
- Townlight import identity and persistence: https://github.com/townlight/meetings/blob/main/townlight_meetings/imported_meetings.py
- Brief discovery and browser-assisted retrieval: https://github.com/scottconverse/civiccast-brief/blob/main/src/civiccast_brief/citybuild/platforms.py and https://github.com/scottconverse/civiccast-brief/blob/main/src/civiccast_brief/citybuild/laserfiche.py
- TownRecord adapter dispatch and job payloads: https://github.com/scottconverse/townrecord/blob/main/core/src/townrecord/records/portal.py
- Legistar event fields and create route: https://webapi.legistar.com/Help/Api/POST-v1-Client-Events
