# External interfaces, candidate 0.1.0.dev8

This candidate is local development software. Synthetic acceptance never proves
live provider acceptance. No interface publishes stories or starts provider
writes as part of ingestion.

## Service ownership and startup

The consuming application or its deployment operator owns service startup,
shutdown, exact version pins, trusted configuration, database backups, tokens,
and any reverse proxy. A TypeScript client does not start or stop a server.
Install the standalone package with its service extra, pinned to the same
candidate as the client:

```powershell
py -m pip install "C:\connectors\quorumrelay-0.1.0.dev8-py3-none-any.whl[service]"
quorumrelay serve --config C:\app\connector-service.json --database C:\app\connector-state.sqlite
```

The package has not been published by this work. Replace the example wheel path
with the candidate whose hash you verified; it does not use a package index.
For checkout development use `pip install -e ".[service]"` from this repository.
`python -m quorumrelay` is equivalent to the console entry point.
Keep the service in its own supervised process; Ctrl+C shuts it down locally.
Restart it using the same database, config, and exact version. Check
authenticated `GET /v1/info` after startup and compare `version`/`schema_version`
with the consumer's pinned deployment requirements before ingesting.

`examples/service.mock.json` contains clearly synthetic, non-deployable tokens
for two newsrooms. Replace them with separately generated high-entropy tokens
for real deployment. Protect configuration with OS filesystem permissions.
`tokens` maps each bearer to trusted `principal`, `client_id`, consumer `tenant`,
`operations`, and optional write `authorization`. Select the bearer from the
owning newsroom's server-side configuration. Never select it from an arbitrary
request field or send it to an upstream provider.

Caller identity is never accepted in operation JSON or headers such as
`X-Tenant`. Consumer tenant scopes captures/jobs/plans/receipts. Provider source
namespace remains the provider's stable source identity, not a newsroom ID.
Upstream credentials belong in private trusted engine context, separate from
service authentication. Do not put them in source URLs or public requests.

The default bind is loopback `127.0.0.1:8765`. No network deployment is started
by these examples. Non-loopback binding requires explicit `allow_network`,
authenticated token policy and an explicit Host allowlist. Restrict
`allowed_origins`; an unexpected Origin is rejected even on loopback.
Terminate HTTPS at an operator-owned reverse proxy. MCP authenticated network
deployment additionally requires OAuth protected-resource metadata and an
externally supplied, audience-validating token verifier; see MCP documentation.

## JSON operations and CLI

`POST /v1/operations/OPERATION` accepts exactly the shared engine request object.
Common operations and schemas are in `ENGINE-CONTRACT.md`; writes are in
`WRITE-CONTRACT.md`. `/openapi.json` is the actual OpenAPI 3.1 document.
Every response preserves the full schema 2.0.0 envelope. Inspect `status`,
`errors`, and `coverage`, including partial records, failed pages and truncation.
An unknown implementation is `unsupported`, not an empty successful search.

```powershell
'{}' | quorumrelay providers
quorumrelay discover --request C:\captures\request.json --content C:\captures\calendar.json
quorumrelay search --jsonl --request C:\captures\queries.jsonl --database C:\app\connector-state.sqlite
```

Requests come from stdin unless `--request` selects a saved file. `--jsonl`
means one complete request/result per nonblank line, not an array silently
split into records. `--content` selects saved parser bytes explicitly.
`--file-root` restricts requested local input paths, resolving symlinks/junctions.
The CLI does not expose server-side paths over HTTP.

For large provider submissions, declare a file part's `part`, `filename` and
`content_type` in the selected change, then use
`--write-file CHANGE_KEY PART C:\captures\document.pdf` with `plan_write`.
The CLI stages that explicit local file within `--file-root`, binds its hash and
length into the scoped plan, and enforces transfer limits. It does not base64
encode the file into request JSON or commit the plan. This requires configured
durable storage and the caller's existing write policy. Each option must match
one metadata-only file part; existing inline/handle inputs cannot be overwritten.
`--config` is trusted process-owner policy; operation JSON cannot grant access.
JSONL shares one engine/store within the process. Stdout contains JSON only;
diagnostics go to stderr. Exit codes: completed 0, partial 2, cancelled 3,
failed 4, unsupported 5, invalid framing/configuration 64. Bulk returns the
highest observed code while preserving each result.

## Files and long operations

`POST /v1/files` accepts multipart part `file` or `application/octet-stream`.
The service returns an opaque `file_handle`, never a local path.
Pass that handle in an operation request instead of `content_base64`.
Handles are scoped to authenticated principal/client/tenant. Retrieval uses
`GET /v1/files/HANDLE` and streams bytes with a safe fixed filename.
Parser inputs default to 16 MiB; uploaded/downloaded documents default to
200 MiB. A large authorized download is not evidence that it can be parsed.
Both limits apply to actual bytes, not solely Content-Length.

For a neutral interchange file, call `import_preview` or `import_bundle` with
`{"format":"zip","file_handle":"..."}`. ZIP and JSONL inputs use the transfer
ceiling while each metadata document/JSONL line retains its parser ceiling.
The handle is resolved in the authenticated caller's storage scope and its bytes
are verified before import. CLI equivalents use `--content C:\captures\bundle.zip`
with `{"format":"zip"}` as the JSON request. Parser-only source captures retain
their original limit. A `plan_write` caller may stage attachment inputs without
receiving fetch, download or commit permission.

JSON and JSONL exports resolve stored original captures into portable inline
bytes, validating their recorded hash and size. Text-format parser limits still
apply; ZIP carries large original files separately. Export never silently drops
originals to fit a text format.

`POST /v1/jobs/OPERATION` submits bounded work and returns HTTP 202 with a
`partial` envelope, `operation_id`, and running data state. This is not
completed acceptance. Poll shared `status` with that ID; final results remain
in its data. Use shared `cancel` to request cancellation. Cancelled work keeps
already completed steps and write receipts; it never deletes provider data.
State uses the configured scoped store. After process restart a previously
running job may need consumer review/retry, rather than a fictional resumed
worker. Writes reconcile uncertain intents according to their core contract.

## TypeScript and an unrelated fifth client

The package is `quorumrelay-client@0.1.0-dev.8`. For local development
use a `file:` dependency to `client/`. To use it without this checkout or any
reference product, build and `npm pack` the client, then install its `.tgz` in
your own project. Generated types come from the packaged core schemas.

```typescript
import { QuorumRelayClient, type RecordEnvelope } from "quorumrelay-client";
const client = new QuorumRelayClient({
  baseUrl: process.env.CIVIC_CONNECTOR_URL!,
  token: process.env.CIVIC_CONNECTOR_TOKEN,
});
const result = await client.execute("providers", {});
if (result.status !== "completed") {
  console.error(result.errors, result.coverage);
}
```

Service HTTP failures throw `ServiceError` with the complete envelope.
Engine partial/failed/unsupported results remain envelopes, not stripped arrays.
Abort/timeout/network failures remain distinct native errors. Provide `{signal}`
to public client methods when the consumer owns cancellation.
Check the service version before use and pin both deployment artifacts.
