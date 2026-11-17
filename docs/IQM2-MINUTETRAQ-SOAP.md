# MinuteTraq SOAP captures

The saved-response format `iqm2-minutetraq-soap-xml` reads selected AgendaGet or MinutesGet SOAP1.1 responses from the captured MinuteTraq8.11.3 client contract. Saved normalization makes no network calls. Bounded native retrieval, selected item-title updates, and native meeting create/update are implemented below.

Configure provider `iqm2`, the exact HTTPS tenant endpoint `/MinuteTraqService/Data_1_0.asmx`, and source options `minutetraq_agency`, `meeting_id`, `document_id`, and `document_kind` (`agenda` or `minutes`). The source namespace includes both host and agency, separate from public iQM2 pages. IDs for the selected meeting and document are positive signed32-bit values, as declared by these GET methods. Item IDs are signed64-bit. Credentials belong in private operation context, never source options.

The reader handles the wrapped method result, inline schema and Microsoft DiffGram DB_1_0 current rows. It maps meeting/document/item identities, supplied titles, parent IDs, ordering and meeting date. The date retains its supplied timezone information. Before/deleted/error rows do not become current normalized items. Raw XML bytes, unknown rows/fields, nil/empty distinctions and file fields remain captured. File fields are not assumed to be document URLs or plain text, and local file markers are never followed. DTD/entity declarations are rejected without external schema loading.

Source provenance: official https://downloads.iqm2.com/Downloads/MinuteTraq_8_11_3_1452015_Full.msi, SHA256 F685268823F757FA3512A1238A04A9904881A6689A4AF85B96928C21EEF1F927. Static extraction only, no vendor application execution or installation. LMClassicServiceClient.dll SHA2566B7091F9F2AC83E78B1CA0191249D29E59F248CA82AA5D171FD063ECF622752D contains SOAP method declarations; M2Common3.5.dll SHA256B221B7504A83914B861A130222B7CFE18F77DE20E2195861B6288ECC8DA53587 contains typed tables and serialization. Extracted source/hashes remain in the current research workspace `work/minutetraq/source.json`.

DeepSeek v4.1 Flash1017 through Ollama at LOW authored the implementation and tests. The coordinator inspected source, reproduced defects, applied worker corrections and ran verification. Synthetic fixtures model the captured wire declarations; no authenticated vendor calls were made.

The client import UI writes generated/finalized/publication fields before optional text parsing. File upload is conditional and may use a separate chunk protocol with recovery/deletion behavior. Those operations require their own mappings and durable write verification; these read paths do not invoke them.

## Selected native SOAP read

The selected native read posts exactly one AgendaGet or MinutesGet SOAP1.1 wrapped-literal request to the configured Data_1_0.asmx endpoint. The request supplies the selected AgendaID or MinutesID, MeetingID, and explicit `minutetraq_file_since` and `minutetraq_public_file_since` XML-schema dateTime values from the caller request. No timezone is invented. The SOAPAction is the quoted SERVICE_NS method, and Content-Type is `text/xml;charset=utf-8`.

Native read credentials are trusted private operation-context configuration only. The configured tenant, exact source origin, agency and namespace allowlist must match the selected source. Meeting and document allowlists must include the selected IDs, and `document_kind` must match. The caller supplies an existing-session vendor authorization header; this read never logs in, hashes passwords, reads browser or machine credentials, or persists the session. The header is validated as the bounded eight-segment vendor contract with escaped agency suffix, 32-hex password hash, 1-to-16-hex connection ID, allowed source-address prefix, literal MinuteTraq, and four-component version. The MinuteTraqVersion header must equal the private configured client version. Response ConnectionID headers are discarded after the single call.

Transport is the existing guarded public transport with exact origin, no redirects, response URL equality, byte and deadline boundaries, cancellation checks, HTTP 200, and XML media type. HTTP 401/403 are permission failures; other HTTP failures and malformed SOAP are generic redacted failures and are never parsed as data. Attachments and inferred upload/download routes are rejected. The saved parser remains unchanged and the native read does not perform writes.

Tests use synthetic guarded transports and the existing saved-response parser fixtures. They model the captured wire contract; no authenticated vendor call was made and no live API success is established by the fixtures.

## Selected agenda/minutes item title updates

The local write adapter maps existing item titles through `AgendaUpdate` or `MinutesUpdate`. It uses the same selected source and private existing-session binding as reads. The trusted `iqm2` credential configuration additionally supplies `permissions` containing `agenda_item:update_title` or `minutes_item:update_title`, and an `item_ids` allowlist (a list, or a map keyed by document kind). The normal SDK `write:plan`/`write:commit` grants and exact immutable plan hash remain required.

A change uses entity `agenda` or `minutes`, operation `update`, and resource_id equal to the selected document_id. Its fields are exactly `updated`, `items`, `minutetraq_file_since`, and `minutetraq_public_file_since`. Each item is `{ "item_id": "9001", "title": "Revised title" }`; explicit null clears the selected title. The caller supplies all three dateTime values. File parts, creation, deletion, reordering, publication, arbitrary fields and foreign relationship metadata are rejected by this mapping. Other recovered MinuteTraq operations remain separate unfinished work.

Preparation reads the selected dataset, preserves its schema and unknown fields, and builds a sparse modified-row DiffGram with original and current values. It retains the parent Updated field and exact selected item IDs. Commit compares a fresh snapshot against the planned before-state, persists the known document ID, sends one update, and reads the selected document again. The preflight comparison is not an atomic server-side compare-and-swap. A lost response or uncertain outcome is reconciled with read requests only; commit does not replay the update.

The captured typed dataset leaves DateTimeMode at the .NET default UnspecifiedLocal. Its Updated revision comparison therefore uses the native clock value, preserving raw date text separately. The independent fixture uses System.Data to generate the baseline and deserialize the actual adapter request, checking modified rows, IDs, original/current values and preserved fields. It does not load or execute any vendor assembly. The reusable fixture is `tests/fixtures/iqm2/dataset-wire-fixture.ps1` and is exercised by `tests/test_iqm2_write.py` on Windows. Verification results for this increment are recorded after its affected checks finish.


## Native meeting creation and updates

Integrated verification: 70 affected tests passed (22 meeting, 41 title-update, 7 shared write tests), including independent System.Data wire validation. No live vendor requests were made.

Select provider `iqm2`, input format `iqm2-minutetraq-meeting-soap-xml`, the exact HTTPS tenant `/MinuteTraqService/Data_1_0.asmx` endpoint, and source options containing only `minutetraq_agency`. Credentials remain in private operation context. The tenant, origin, agency and allowed namespace must match; the existing-session authorization header and client version use the same binding rules as the agenda/minutes adapter.

Use entity `meeting` with operation `create` or `update`. Creation omits resource_id; update requires the selected positive MeetingID. Required fields are `meeting_date`, `resolution_due_date`, `meeting_type_id`, `meeting_location_id`, `meeting_status_id`, `department_id` and `meeting_get`. The latter supplies explicit `date_from`, `date_to`, `meeting_status` (string or null), and `department_id` for the native five-argument MeetingGet. ResolutionDueDate cannot be later than MeetingDate. Optional `timestamp_start` and `timestamp_start_delta` are independently optional; omitted timestamps are not invented. Native dates follow .NET UnspecifiedLocal wall-clock semantics.

Private credentials require `meeting:create` or `meeting:update` in permissions and explicit department, meeting-type and meeting-location allowlists. Updates also require a meeting-ID allowlist. SDK planning and commit grants plus the immutable plan hash apply normally.

Creation sends one inserted Meeting row with native temporary ID -1, then persists the positive returned ID before checking cancellation and performing readback. If acknowledgement is lost before an ID is known, recovery remains uncertain and does not repeat creation or match by date. Updates retain original/current row values and unknown fields, compare the fresh before-state, and verify the planned target after one send. This preflight is not atomic upstream concurrency control. Reconciliation only reads.

The independent PowerShell fixture uses System.Data to generate a real baseline and deserialize actual prepared create/update requests. It checks row states, IDs, field types, original/current dates, and preserved unknown fields without executing vendor assemblies. Files, deletion, media transfer and publication are separate operations.

## Native M2 recording upload

The `iqm2-minutetraq-media-soap-xml` write source supports `recording:upload` for the selected `meeting_id`. Omit `resource_id` to create a recording; supply an explicitly allowed native MediaID to replace that recording. Fields require an explicit `published` XML date/time and accept `started` (defaults to the supplied publication time). Supply exactly one file through the shared `content_base64` or caller-scoped `file_handle` interface.

The trusted `iqm2` credential configuration must include `bigfiles_enabled: true`, permission `recording:upload`, the allowed meeting, and any allowed existing media IDs, alongside the existing tenant/origin/agency/session binding. This maps the native M2 BigFiles path; deployments using another storage workflow need their corresponding contract.

Planning reads upload information and the selected existing recording. Commit uploads 512,000-byte chunks, saves the native Media dataset, persists the positive returned MediaID, then verifies metadata and the original downloaded file's length and SHA256. Existing recording changes preserve parent identity and unknown fields. Chunk intent and acknowledgments are durable. A lost append acknowledgment remains uncertain across reopen; reconciliation performs reads only. An unknown new MediaID is never inferred from the meeting or timestamp. Automatic deletion, restart, FTP transfer and transcoding administration are outside this operation.

The integrated affected run passed 80 cases, including actual System.Data deserialization of the outbound BigFileAppend and MediaUpdate requests, new/replacement uploads, public file handles, configuration denial and uncertain-result recovery. The final full Python regression passed 2,963 tests with zero failures. Exact source/test bindings are in `verification/iqm2-minutetraq-media-2026-11-16.json`.
