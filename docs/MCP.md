# MCP reference, candidate 0.1.0.dev3

The implementation uses the official Python SDK **mcp 2.3.0**, not hand-written
JSON-RPC framing. Both transports call the same engine operations as Python,
CLI and REST. Tool arguments are `{"request": <shared engine request>}`.
The full result envelope is returned as `structuredContent` and JSON text.
Failed/unsupported operations set MCP `isError`; partial is not failed or complete.
Fetched source text is untrusted data, never an instruction to the service.

## Implemented and tested revisions

| Transport | Revision | Executed behavior |
|---|---|---|
| stdio subprocess | 2026-07-28 | Official modern client, version metadata, full read/import/export and mocked plan/commit/readback/receipt, progress/cancellation |
| stdio subprocess | 2025-11-25 | Official legacy client, initialize/initialized negotiation, identical workflow, cancellation notification |
| Streamable HTTP socket | 2026-07-28 | Official modern client, per-request version/capabilities, mirrored-header rejection, no session, disconnect cancellation |
| Streamable HTTP socket | 2025-11-25 | Official legacy client, initialize/initialized, SDK sessions, identical workflow and explicit cancellation |

These are the revisions actually tested for this candidate. The SDK may
advertise other backwards-compatible revisions; no test claim is made for
those. Unsupported HTTP revisions and header/body mismatch are rejected.
No deprecated HTTP+SSE endpoint or experimental Tasks API is exposed.

Modern MCP does **not** use `initialize`, session IDs, standalone GET streams
or DELETE termination. Version and capabilities are per-request `_meta`
fields, mirrored into HTTP headers as required. A modern client may use
`server/discover` to learn supported versions. Closing a response SSE stream
cancels the request.

Legacy MCP uses initialize/initialized negotiation. Subsequent HTTP requests
carry the negotiated `MCP-Protocol-Version` and SDK-issued `Mcp-Session-Id`.
The SDK binds sessions to authenticated principals and owns GET/DELETE
semantics, expiry and teardown. Losing a legacy response connection is not
itself cancellation; clients send `notifications/cancelled`.
Sessions do not authorize access to another caller's records or plans.
Keep one worker or use sticky routing for legacy sessions.

## stdio

```powershell
quorumrelay mcp --database C:\app\connector.sqlite --config C:\app\trusted-principal.json
```

The host launches and terminates the process. Stdout is MCP only.
Process-owner configuration supplies trusted `principal`, `client_id`, consumer
`tenant`, allowed operations/source namespaces, and private upstream credentials.
stdio does not run HTTP OAuth. Default process policy is read-only.
Never copy HTTP provider credentials into model tool arguments.

## Streamable HTTP and authentication

Set `service.mcp=true` in trusted service configuration. REST and `/mcp` share
the configured engine and state. The service binds loopback by default and
requires explicit authenticated configuration for non-loopback use.
Host and Origin allowlists apply before dispatch.

When bearer policies are configured, MCP requires `public_url` (service root)
and `issuer_url` (operator-owned external OAuth authority). The official SDK
serves protected-resource metadata for `public_url + "/mcp"` and challenges
unauthenticated requests with its metadata URL. Resource/audience validation
is enabled. The built-in verifier accepts only explicitly provisioned opaque
service tokens in the trusted map; it is not a JWT signature verifier.
For existing OAuth infrastructure, Python deployments may supply both
`mcp_token_verifier` and `mcp_principal_resolver` to `create_app`. The official
TokenVerifier must return validated resource-bound AccessTokens; the trusted
resolver maps those claims to a Principal. Never trust an unverified tenant
header. This project does not issue OAuth tokens, host a login page, or provide
a general authorization server. Actual external login flows are not acceptance
claims of the synthetic tests.

Upstream provider credentials remain distinct private context. A service token
is never forwarded to provider URLs. Scoped actor/client/tenant state and
optional source-namespace policy apply in the engine, not only tool annotations.

## Capabilities, cancellation and writes

Available tools mirror all shared operations, including status/cancel and the
exact plan/commit/receipt contract. Advertising a tool is not a grant: trusted
caller operation policy and engine capability checks still reject disallowed
calls. The server does not request sampling, roots, elicitation or model access.

The server keeps SSE responses and legacy sessions enabled:
`json_response=False`, `stateless_http=False`. The SDK documents that changing
these can disable cancellation on the modern or legacy leg respectively.
SDK cancellation sets the synchronous engine context's cancellation event.
Workers stop cooperatively between bounded units. An already in-flight network
request cannot be forcibly reversed; completed or uncertain writes remain in
durable receipts for reconciliation. Cancellation never deletes provider data.

`write:plan`/`write:commit` are trusted saved-policy grants. Commit contains only
the exact immutable scoped plan ID/hash. The service never manufactures a grant
from that hash. Examples refuse to commit unless the planned adapter is mock.
Mock receipts retain `live_acceptance: "NOT_RUN"`.

## Large exported files

For input files, use `upload_begin(filename, content_type, byte_length)`, append
base64 chunks of at most 256 KiB with `upload_chunk(upload_id, offset, content_base64)`,
then call `upload_finish(upload_id)`. Each returns the shared structured envelope.
The final result contains an immutable scoped `file_handle`, length and SHA256.
Pass that handle to `import_preview` or `import_bundle` with the neutral `format`
(`json`, `jsonl`, or `zip`). This does not grant a provider write. Wrong-scope,
expired, altered and oversized input is rejected. `upload_abort` discards an
unfinished upload. Complete native provider capture normalization continues to
use its documented parser input contract.

Export with `stream: true` or `delivery: "storage"` returns an opaque
`artifact_id` and manifest instead of large base64 data. The MCP tool also
returns a resource link, `civic-artifact://ARTIFACT_ID/0`.
Read that resource with `resources/read`: each JSON resource contains at most
256 KiB of decoded bytes, an offset, total length, SHA256, and `next_offset`.
Follow offsets until null, decode each base64 chunk, and check the final hash.
Every read rechecks scope, expiry, current source authorization and attachment
grant. This is bounded chunk delivery, not an unframed binary stdout stream.
HTTP clients may instead use the authenticated `/v1/files/ARTIFACT_ID` stream.
Use these paths for large files; inline result/event sizes also depend on the
MCP client's configured SSE event limit.

## Executable synthetic examples

`examples/mock_workflow.py` starts an engine with the real write adapters and
an injected synthetic upstream transport that never opens a provider socket.
`examples/mcp-client.py` runs the shared workflow through an actual stdio
subprocess or configured HTTP service, in modern or `--mode legacy` mode.
See `examples/README.md`. No live provider acceptance is implied.

Official references checked on 2026-11-11:

- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md
- https://py.sdk.modelcontextprotocol.io/whats-new/
- https://py.sdk.modelcontextprotocol.io/run/legacy-clients/
- https://py.sdk.modelcontextprotocol.io/handlers/cancellation/index.md
