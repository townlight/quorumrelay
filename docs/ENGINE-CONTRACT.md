# Engine contract, candidate 0.1.0.dev9 / schema 2.0.0

Implementation layout: core `models.py`, `engine.py`, `extensions.py`, `compat.py`, `normalization.py`, `fetch.py`; discovery `providers/`; storage/search/export `storage.py`, `search.py`, `interchange.py`, `imports.py`; writes `writes.py`; transports `transports/`, TypeScript `client/`.

## Public boundary

```python
from quorumrelay import Engine, Source, Bounds, Query, OperationContext, OperationResult
from quorumrelay.models import Record, Identity, CaptureBundle, Error
from quorumrelay.extensions import Storage, StoredValue, StorageConflict
from quorumrelay.engine import canonical_hash, source_identity_key

engine = Engine(storage=None, connectors=())
result = engine.execute(operation, request, content=None, context=None)
result.public_dict()
engine.normalize(source, content, input_format="meeting-export", bounds=None, context=None)
engine.fetch_record(source, external_id, bounds=None, context=None)
engine.register_operation(operation, handler)
# handler(engine: Engine, request: dict, content: bytes | None,
#         context: OperationContext) -> OperationResult
engine.register_connector(connector)
```

Engine construction does not start services, open a database, fetch data, or write anything. Storage is optional. Owner modules expose `register(engine) -> None` to register handlers; composition calls those functions once. No transport has provider-specific parsing. Built-in names are `providers`, `capabilities`, `normalize`; additional names are `identify`, `validate_source`, `discover`, `fetch`, `search`, `import_preview`, `import_bundle`, `export`, `plan_write`, `commit_write`, `receipt`, `status`, `cancel`.

Public entry points use `from quorumrelay import create_engine`: `create_engine(*, storage=None, connectors=(), provider_transport=None, provider_browser=None, write_adapters=None, write_approval=None)`. This registers every standard module once. `write_adapters=None` includes real built-in adapters but grants no credentials/authorization; an explicit empty dictionary disables them. No implicit database or service starts.

Native additive input formats require `create_engine()` or `providers.register(engine)`; an unextended bare `Engine()` supports only the 34 baseline formats.

Missing implementation returns `unsupported` with reason explicitly distinguishing unavailable implementation from unsupported vendor capability. Unsupported fields/invalid input return `failed` plus typed errors. Every convenience call preserves the complete result envelope, not only its record list.

## Common serialization

`OperationResult`: `schema_version`, `status` (`completed|partial|cancelled|failed|unsupported`), `data`, `errors`, `coverage`, `operation_id`. Error: `code`, `message`, `retryable`, `source`, `details`. Public JSON never serializes OperationContext or credentials.

`Source`: `provider`, `url`, optional `namespace`, `body`, `input_format`, `options` object. Namespace must equal evidenced provider-derived namespace, not an arbitrary user tenant label. `url` is a durable source/citation, never credentials. Options contain only provider-documented configuration, never arbitrary fetch targets or secrets.

Source rejects recognized credential keys in URL queries and recursively in options, including case, hyphen and underscore variants. Errors identify the key path without its value and direct callers to private `OperationContext.credentials` using the provider-specific documented shape (for example, `legistar_token` for Legistar reads and nested provider objects for native writes). Generated record and text citations strip credential query parameters (and signed-transfer authentication); original captures and unknown upstream fields remain lossless.

`Bounds`: optional inclusive `date_from`/`date_to` (`YYYY-MM-DD`); `max_records=1000`, `max_pages=25`, `parser_bytes=16777216`, `transfer_bytes=209715200`, `deadline_seconds=45`, optional `checkpoint`. Date filtering uses a source-supplied local calendar date when supplied, otherwise known scheduled date. Unknown dates remain explicit partial coverage, not silently excluded. API-specific ge/lt ranges must map the inclusive caller end date to the correct exclusive next-day boundary without inventing unknown time zones.

`Query`: arrays `terms`, `phrases`, `namespaces`, `providers`, `record_types`; optional `body`, `date_from`, `date_to`; `limit=100`. Exact terms/phrases are not semantic search. Sources and failures are named in coverage.

`OperationContext`: caller-only `principal="local"`, `client_id="sdk"`, `tenant=None`, `authorization=frozenset()`, `cancellation=threading.Event()`, optional `progress` callback, private `credentials` dict, optional `operation_id`. `scope` is SHA256 of canonical `[principal,client_id,tenant]`; cross-client/tenant access never shares that state. Credentials are resolved server-side, not returned.

`tenant` is the consumer's newsroom/city/profile authorization-state tenant, not an upstream source namespace. Trusted `allowed_operations: frozenset[str] | None` and `allowed_namespaces: frozenset[str] | None` restrict engine operations and upstream targets separately. Neither comes from request JSON. `None` permits trusted in-process reads, but writes still need explicit write grants and exact-plan approval. Direct SDK normalization respects policy. Only a currently executing trusted `discover`, `fetch` or `import_preview` handler may internally delegate normalization without exposing a public normalize grant; the exact engine/context must match and namespace policy remains enforced.

Coverage remains an extensible object: `sources`, requested `date_from/date_to`, `date_inclusivity="both"`, `actual_dates`, `truncated`, `failures`, `checkpoint`, record/page counts, unavailable attachments/text and scope/completeness. Reducing partial results cannot discard failures. A checkpoint must bind provider, namespace, body/type/date/query, scope and request semantics; reject changed bindings. A checkpoint token is not a general URL.

## Normalize request and data

```json
{"source":{"provider":"legistar","url":"https://example.org"},"input_format":"meeting-export","content_base64":"...","bounds":{}}
```

SDK may supply `content` bytes instead. `data` is a `CaptureBundle`: `schema_version`, `source`, `records`, `capture`, `compatibility`, `extensions`. Preview does not persist. `compatibility` is the exact v1 preview for legacy callers, not the rich model ceiling. Raw bytes are base64 in `capture.content_base64`, with sha256/timestamp/length/input format/source URL and decoded `original_values` for JSON. A store may replace inline bytes with a lossless scoped retrievable reference, but export must resolve it.

`Record`: `schema_version`, `identity`, `normalized`, `source_url`, `citation_urls`, `capture_sha256`, `captured_at`, `normalized_sha256`, `source_revision`, `original`, `relationships`, `text`, `extensions`. Preserve these dicts and all additional unknown keys losslessly when store/import/export pass dictionaries around. Typed `from_dict` helpers will preserve unknown top-level keys; dictionaries remain the interchange source of truth.

`Source`, `Identity`, `Record`, `CaptureBundle` and `OperationResult` supply `from_dict`/`public_dict` helpers. Unknown fields survive both top-level and nested typed round trips. JSON serialization uses arrays, not Python tuples. Known-offset timestamps, a supplied calendar TZID, and unknown zones are distinct; a supplied named zone never invents a UTC offset.

Identity: `provider`, `namespace`, `record_type`, `external_id`, optional `parent` identity, `derivation`, `stability`. Only the first five form source identity. Capture hash, normalized hash, upstream revision and application destination IDs are different. `source_revision` has `kind` and `value`, provider mappings may add provenance; do not call local hashes upstream versions. Unknown revisions are `{"kind":"not_supplied","value":null}`.

Normalized fields retain original v1 values, adding explicit timezone/agenda availability and supplied status. Unknown data stays original. HTML/PDF originals remain exact capture bytes with references. Rich Tyler and iCalendar records retain cancelled/adjourned entries even where compatibility filters them.

Tyler saved-calendar normalization hashes the final rich normalized record, including supplied `source_status.canceled` and `source_status.adjourned`. A status-only change therefore keeps the same native identity while producing a different normalized digest and an import-preview `changed_source` outcome. Capture hashes identify the exact input bytes; no vendor revision is invented. Supplied reschedule, visibility and unknown fields remain in `original` without inferred status semantics. The compatibility reader and its filtering remain unchanged.

Text segment: `field`, `text`, `citation_url`, optional `page`, `timestamp`, `language`, `provenance`, `completeness`. Supplied captions/notice text are initial segments. An extraction failure or scanned PDF is not complete text search. Durable source/citation URLs remain separate from short-lived attachment transfer URLs.

## Storage contract

```python
put(collection: str, key: str, value: dict, *, scope: str,
    expected_version: str | None = None, create_only: bool = False) -> str
get(collection: str, key: str, *, scope: str) -> StoredValue | None
list(collection: str, *, scope: str) -> list[StoredValue]
# StoredValue(key: str, value: dict, version: str)
# StorageConflict(ValueError) on failed atomic compare/create
```

Use collections `captures`, `records`, `checkpoints`, `operations`, `write_plans`, `receipts`, owner may add internal collections. Every put is atomic. `create_only=True` fails if present. `expected_version` requires the exact current version; do not overwrite a newer value. Reads/lists return snapshots, not mutable aliases. SQLite implementation owns transaction/concurrency/restart durability and capture streaming. Capture key may be content hash; records key uses `source_identity_key(identity)`, with revisions retained separately rather than discarded.

Write plans/receipts need create/CAS before sending requests. Persist exact immutable plan and digest, actor/client/tenant scope, exact intended target/fields/version and authorization. An ambiguous outcome must persist uncertainty and reconcile before repeat create, including after restart. Never use unconditional last-writer-wins for these state transitions. Multi-record operations report each durable step and incomplete siblings.

## Connector extension

`Connector` protocol in `extensions.py` declares provider, `capabilities`, `identify`, `discover`, `fetch`, `parse`, `native_search`, `export`, `plan_write`, `commit_write`. `check_connector()` validates signatures/callability without network actions. Unsupported hooks return explicit `OperationResult.unsupported`, not fake success. Registration requires no transport edits. Provider discovery owner can expose richer orchestration through registered operation handlers while implementing these hooks.

Registered custom source providers dispatch identify/discover/fetch/parse directly; `search` with `native:true` invokes native search, and `export` with `provider_specific:true` invokes provider export. Restricted custom requests require an explicit configured namespace. Write hooks cannot bypass the shared write coordinator: register a typed WriteAdapter as well for supported writes. The synthetic example connector proves read registration without transport changes.

## Safe request extensions

`fetch.request_public(url, *, byte_limit, method="GET", body=None, headers=None, allowed_origins=None, destination=None, deadline_seconds=45)` returns the compatibility `(final_url, bytes, media_type)` tuple and rejects non-2xx status. `request_public_response` has the same arguments and returns internal `PublicResponse(url, content, media_type, status, headers)`, retaining bounded non-2xx bodies and lower-case allowlisted protocol metadata for conflicts/chunk uploads. This object has no public serializer. Cookies/authorization are excluded from response metadata and cross-origin request headers are stripped.

New requests default to the exact original origin; cross-origin GET redirects need an explicit origin allowlist, request bodies never redirect across origins, and HTTPS cannot downgrade. DNS resolution has a bounded 8-slot daemon resolver and shares the total deadline. Every DNS answer is validated and the actual socket uses that validated address while TLS retains the original host. Streamed transfer caps, declared-length checks, response deadlines and a maximum 5-hop request sequence apply. Local parser caps remain separate.

## Legacy result projection

`legacy.legacy_previews(result, *, identity_mappings=(), new_source=False)` returns a full OperationResult with `data.previews`. It retains partial/errors/coverage and projects only selected rich record identity/capture pairs. Only original 34 baseline format pairs count as authoritative v1 pages; additive API convenience previews never prove old-ID equivalence. Rich cancelled records remain retained but the legacy workflow's original filters still apply.

For a genuinely new configured source, explicit `new_source=True` keeps its validated durable URL namespace and provider-issued external IDs without claiming a legacy transition. Existing-source transitions need `LegacyIdentityMapping(provider, upstream_namespace, legacy_source_url, external_ids, evidence)` with explicit per-ID mappings; no hostname/client resemblance invents an alias. Missing evidence returns an actionable mapping-required failure rather than duplicating records.

## Historical extraction verification (dev1)

Core validation: 132 tests PASS on Windows Python 3.13, including exact independent original-output hashes for all 34 formats/31 families, raw capture retention, unknown typed round trips, conformance signatures, scoped delegation, source projection and streamed 200 MiB/+1 boundaries. The unchanged original local-parser validator also reports 34 PASS through a test-only compatibility alias. Owned-module lint passes. The independent validator reports the frozen baseline wheel's full-JSON 34-format comparison passes in a clean environment with no reference-product imports.

Frozen early extraction artifact: `dist/core-baseline/civic_data_connectors-0.1.0.dev1-py3-none-any.whl`, SHA256 `00f911a2ec2038fea1114424e7650617d7cec9e4a3c2fff0d0208addd9114f02`. Later source changes require a distinct final artifact and rerun; this early artifact stays intact. That extraction snapshot used synthetic writes. It does not define the later authorized implementation scope. These historical checks do not establish current live-provider or installed-consumer release acceptance; see `ENGINE-COVERAGE.md` and current receipts.

## Single-record detail and source formats

`fetch` accepts `external_id` for an evidenced provider detail adapter. It cannot be combined with attachment selection or saved content. The Legistar adapter issues one fixed event-detail route with items/notes/attachment expansion flags and rejects response IDs that differ from the requested EventId. It uses the same exact source identity as event discovery. Missing/unimplemented detail adapters remain explicit, rather than returning a catalog or successful empty result for a specific record request.

`providers.data.providers[].additional_formats` lists registered additive parser hooks independently of the preserved 34 baseline formats. This is runtime parser availability, not a live provider acceptance claim.

## Current source-only Granicus Platform mappings

These additions are local source, not the frozen dev8 distribution. Select the explicit `granicus-platform-soap-xml` format and tenant URL `https://{tenant}.granicus.com/SDK/User/index.php`. Server-owned `context.credentials.granicus` binds `username`, `password`, application `tenant`, exact `origin` and `namespace`; credentials never belong in requests. Grant only the needed `permissions`, `resource_ids`, `meeting_ids`, `foreign_ids` or `folder_ids`. MediaVault additionally requires an explicit HTTPS `media_origin` matching the folder's vendor descriptor. General contacts, vendor administration and deletes are excluded.

All mutations use the existing `plan_write` → approve exact `plan_id`/`plan_hash` → `commit_write` → receipt sequence. No ingestion implicitly publishes media.

- `recording_publication` / `update`: existing clip `resource_id`, `meeting_id`, all seven native `PublishClipData` fields including explicit boolean `Public`; requires separate `recording_publication:update`. Receipts independently verify clip identity/default visibility, label other publication fields submitted-only, and retain Pending/missing-acknowledgement uncertainty without replay.
- `agenda_tree` / `create`: target Event/Clip `resource_id`, `meeting_id`, fields `ParentType` and full `MetaDataData` root. `agenda_tree` / `update` imports `MetaData` array with explicit `AsTree` and `ClearExisting:false`. Every new node supplies all native fields, unassigned ID0/empty UID and a unique authorized ForeignID. Destructive clearing is vendor-supported but excluded by project scope. Readback checks provider IDs, fields and parent relationships.
- `generated_minutes` / `create`: existing clip `resource_id`, `meeting_id`, exact `clipUid`, `name`, `templateUid`, `isPublished`, `isDefault` fields. Both flags are mandatory. This creates upstream content; it is not a read/export. New UID/name/publication/default metadata are checked; template choice and generated file bytes remain explicitly unverified.
- `chunked_recording` / `upload`: no existing `resource_id`; explicit `meeting_id`, fields `FolderID`, `Name`, `Extension`, `ChunkBytes`, plus one approved audio/video `bytes` file part. `ChunkBytes` is caller-selected within the adapter's 7,000,000-byte per-chunk safety ceiling, not a vendor total-file cap. To assign uploaded bytes to an existing clip, use `update`, exact clip `resource_id`, and `ClipUID` instead of `Name`. Operation/resource/folder/meeting grants remain required. See the existing file-handle staging interface for exact authorized file bytes.

Chunk state is stored privately in `private_provider_uploads`, scoped to the caller and bound to source/approved plan. The application owns database protection and retention. Remote bucket GUIDs never enter public plans/receipts, and current login cookies remain ephemeral. A recorded state is not a promise of resumability: unknown Start/Chunk/Finish/Register/Assign outcomes never automatically replay. Vendor checksum algorithm, playable processing and remote original-byte equality are not inferred.

Record-shaped raw SOAP normalizes offline without provider credentials. Responses such as captions/attachments that contain no request parent ID use the existing neutral CaptureBundle fallback, preserving exact XML and supplied parent/records. Bare supporting XML fails explicitly rather than inventing identity. Read `provider-api-contracts.json` for pinned versions, method/outcome assessment and field-level qualifications; redundant convenience endpoints do not become additional requirements.
