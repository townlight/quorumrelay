# Interface design, candidate 0.1.0.dev1

Design checkpoint: 2026-11-11. Implementation and transport acceptance remain pending.
The frozen engine boundary is `ENGINE-CONTRACT.md`; writes use `WRITE-CONTRACT.md`.
No interface contains provider mappings or invents provider request fields.

## Dependencies and ownership

Official MCP Python SDK `mcp==2.3.0` installs and imports on isolated Windows
Python 3.13.5. Public `MCPServer`, `Context`, `Client`, `add_tool`, and
`streamable_http_app` signatures were inspected. The installed environment has
Starlette 0.52.1, uvicorn 0.54.0, python-multipart 0.0.33, jsonschema 4.26.0,
and httpx 0.28.1. Installation is not MCP conformance acceptance.

Proposed optional `service` dependencies: `mcp==2.3.0`,
`starlette>=0.52.1,<1`, `uvicorn>=0.54,<1`,
`python-multipart>=0.0.33,<1`, `jsonschema>=4.26,<5`.
TestClient requires test dependency `httpx>=0.28,<1`.
CLI entry point: `civic-data-connectors = civic_data_connectors.cli:main`.

The deploying application owns startup/shutdown, exact library/client pins,
durable store location/backups, trusted principal policy, upstream secrets,
and TLS termination where appropriate. Installing the SDK starts nothing.

## Common envelope and requests

Every operation calls `Engine.execute(name, request, content=..., context=...)`.
Responses retain `schema_version`, `status`, `data`, `errors`, `coverage`,
and `operation_id`. No convenience call drops partial coverage or errors.
Unknown implementation is `unsupported`, not an assertion about the vendor.

Operations: providers, capabilities, identify, validate_source, discover, fetch,
normalize, search, import_preview, import_bundle, export, plan_write,
commit_write, receipt, status, cancel. All interfaces use identical request
objects. Input JSON cannot supply identity, credentials, or authorization.

## CLI

`civic-data-connectors OPERATION` reads one JSON object from stdin.
`--request FILE` reads an explicitly selected JSON request.
`--jsonl` executes one complete request per nonblank line, writes exactly one
result per request, and preserves state within the process.
`--content FILE` supplies explicitly selected saved capture bytes.
`--file-root ROOT` limits paths when configured; no operation accepts an
arbitrary server-side path. JSON output is UTF-8 and stdout contains only
results. Human diagnostics use stderr.

Stable exits: completed 0, partial 2, cancelled 3, failed 4, unsupported 5,
invalid CLI/request framing 64. A JSONL run returns the highest severity
encountered, without hiding earlier results.

## HTTP and files

Starlette ASGI hosts versioned JSON routes and the official MCP app.
OpenAPI 3.1 at `/openapi.json` describes actual envelopes and file operations.
`POST /v1/operations/{operation}` accepts the core request object.
`POST /v1/files` accepts bounded multipart upload and returns an opaque handle.
`GET /v1/files/{handle}` streams bytes, with safe attachment names.
File handles are unguessable and bound to authenticated principal/client/tenant
scope, not local filesystem paths. A handle cannot be used in another scope.
Uploaded capture bytes can be supplied with a transport `file_handle` member
which is resolved before engine dispatch, never passed as provider options.

`POST /v1/jobs/{operation}` submits bounded background work and returns an
operation ID. Engine status/cancel handlers expose progress/results/cancellation.
The engine/storage operation owner owns persisted job semantics, rather than
the HTTP adapter inventing another receipt or status model.

Loopback `127.0.0.1` is the default. Non-loopback binding requires explicit
network enablement, authenticated policy, allowed Host/Origin configuration,
and an appropriate TLS/reverse-proxy deployment. Browser origins are denied
unless explicitly allowed. No arbitrary URL fetch or filesystem route exists.
Parser-input and file-transfer byte limits remain separate.

## Authentication and exact-plan approval

Service-local bearer policy resolves principal, client ID, tenant and operation
scopes from trusted deployment configuration. Caller headers cannot change
identity. MCP network authentication uses an externally configured OAuth token
verifier and protected-resource metadata, including resource/audience
validation; this project does not create an authorization server.
stdio uses its trusted process environment/configuration, not HTTP OAuth.
Upstream provider credentials remain private context and are never client
service tokens.

Authenticated saved policy may grant `write:plan` and `write:commit`.
Commit submits exactly immutable scoped `plan_id` and `plan_hash`. The engine
loads and verifies the exact plan under the same actor/client/tenant.
Transports never derive authorization grants from a supplied hash.
A stricter server-side approval callback can impose additional approval.
No discovery, import or export operation performs a provider mutation.

## MCP version-specific behavior

The selected official SDK documents support for modern `2026-07-28` and
legacy `2025-11-25`; these are intended test targets, not yet passing claims.
No deprecated HTTP+SSE endpoint is offered.

Modern: each request carries version/capabilities in reserved `_meta`;
HTTP mirrors metadata in required headers and rejects header/body mismatch.
No initialize handshake, MCP session, standalone GET stream or DELETE
termination exists. SSE disconnect cancels the request.

Legacy: initialize/initialized selects a mutually supported revision;
Streamable HTTP uses SDK sessions and subsequent version/session headers.
GET streams and DELETE session termination follow that revision.
Disconnection alone does not mean cancellation; clients send the protocol
cancellation notification. Sessions are not authorization.

Keep `json_response=False` and `stateless_http=False`: the SDK documents that
these options otherwise disable modern/legacy cancellation respectively.
Async handlers dispatch synchronous engine work through a cancellable worker,
set the core cancellation event on cancellation, and preserve completed work.
Progress maps to SDK request-scoped progress without inventing results.
Only implemented tools/capabilities are advertised; no sampling, roots,
elicitation, experimental tasks, or automatic tool-result execution.
The official SDK owns framing, initialization, negotiation and sessions.

## TypeScript boundary and fifth client

Package: `@civic-data-connectors/client`, candidate `0.1.0-dev.1`.
Development dependency may be `file:<connector-checkout>/client`; an unrelated
client must also be able to install a locally packed npm tarball, independently
of any reference application or repository layout.

```typescript
import {
  CivicConnectorClient, type OperationResult, type RecordEnvelope, type Source,
} from "@civic-data-connectors/client";
const client = new CivicConnectorClient({
  baseUrl: process.env.CIVIC_CONNECTOR_URL!,
  token: process.env.CIVIC_CONNECTOR_TOKEN,
});
const result = await client.execute("discover", request, { signal });
```

`baseUrl` is explicit and never guessed; the client does not spawn a service.
Generated public record types originate from the frozen schema and preserve
extensions. Runtime results retain the complete engine envelope.
Timeout, abort, service errors and engine failure are distinct.
Examples must run discover/search/import/export and exact plan/commit/receipt
against synthetic captures, not live vendor mutation.

## Sources checked

- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization.md
- https://py.sdk.modelcontextprotocol.io/whats-new/
- https://py.sdk.modelcontextprotocol.io/run/asgi/
- https://py.sdk.modelcontextprotocol.io/run/legacy-clients/
- https://py.sdk.modelcontextprotocol.io/handlers/cancellation/index.md
- https://pypi.org/pypi/mcp/json (reported 2.3.0; isolated install confirmed)

Remaining gates: implementation phase approval; representative operation
registration; response/OpenAPI tests; both protocol-era clients over both real
transports; authorization/isolation/cancellation tests; installed artifact and
Node parity; consumer integration acceptance. Live write acceptance is NOT_RUN.
