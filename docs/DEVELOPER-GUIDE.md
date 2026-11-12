# Developer integration guide

QuorumRelay is a standalone civic-data engine for your own application, service,
script or agent. It does not require a Townlight installation, an application
database, a model provider or a hosted QuorumRelay account. Use the Python API in
process, or run the optional service for HTTP, TypeScript and MCP consumers.

This guide describes **0.1.0.dev8**, schema **2.0.0**. It is a development preview.
Provider coverage varies by operation. Live account and vendor-write acceptance
remain deferred; publication of the code and documentation is not a claim that
those checks passed. Start with the [user manual](USER-MANUAL.md),
[architecture](ARCHITECTURE.md) and [capability evidence](capabilities/README.md).

## 1. Choose an integration path

| Your application | Use | You own |
|---|---|---|
| Python application or worker | `create_engine()` and typed models | Context, persistence, lifecycle and approved operations |
| Shell, scheduled task or another language | JSON/JSONL CLI | Process, input/output files and exit handling |
| Web backend, Node or another language | HTTP JSON operations and file streams | Service process, authentication and tenant policy |
| TypeScript application | `QuorumRelayClient` over HTTP | An explicitly configured service URL and service token |
| Tool-using agent | MCP stdio or Streamable HTTP | Host process or authenticated service and tool policy |
| New provider or storage backend | Connector/Storage extension protocols | Verified provider mapping and storage isolation/concurrency |

The four reference applications illustrate these paths. They do not define the
product boundary. A fifth application uses the same interfaces and contracts.

## 2. Install from public source

Python 3.11+ is required; current Windows CI uses Python 3.13. Node is needed only
to build the TypeScript client or website. The client declares Node 20.3+; the
repository CI uses Node 24. No package-index release is claimed.

```sh
git clone https://github.com/townlight/quorumrelay.git
cd quorumrelay
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -e ".[service]"
quorumrelay providers
```

For an application deployment, pin a reviewed commit or explicit wheel rather
than following a moving branch. Install the core without extras for an in-process
integration; add `[service]` for HTTP/MCP. The optional `[browser]` extra and
Playwright's Chrome installation are needed only for the guarded WebLink browser
session described in [its guide](WEBLINK-SESSION.md).

`quorumrelay` is the canonical import and command. `civic_data_connectors` and
`civic-data-connectors` remain compatible aliases sharing the same implementation
objects. Installing a package never starts a server or downloads a model.

## 3. Preserve the complete result

Every interface returns this envelope; do not reduce it to `data.records`:

```json
{
  "schema_version": "2.0.0",
  "status": "partial",
  "data": {},
  "errors": [],
  "coverage": {},
  "operation_id": null
}
```

| Status | Consumer behavior |
|---|---|
| `completed` | The reported bounded operation completed; inspect its stated scope |
| `partial` | Keep usable data and disclose missing text/pages/files, limits or incomplete scope |
| `cancelled` | Keep completed evidence/receipts; do not assume an in-flight write was undone |
| `failed` | Show structured error codes and actionable details; inspect any retained state |
| `unsupported` | This requested implementation is unavailable; it is not proof the vendor lacks the feature |

HTTP 200 alone is not completion. `errors` and `coverage` carry provider failures,
truncation, unknown date/body matches and citation limits. A saved capture cannot
establish a complete upstream archive. An accepted asynchronous task is not a
completed mutation.

## 4. Python: capture, preview, save, search and export

This complete example uses an explicitly synthetic saved response and makes no
provider request. Run it from an application-owned writable directory:

```python
import json
from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage

raw = json.dumps([{
    "EventId": 7,
    "EventBodyName": "Council",
    "EventDate": "2026-11-11T00:00:00",
    "EventTime": "7:00 PM",
    "EventComment": "Parks budget"
}]).encode()
source = Source("legistar", "https://example-city.legistar.com/Calendar.aspx",
                input_format="legistar-events-json")
store = SQLiteStorage("my-app-captures.sqlite")
engine = create_engine(storage=store)
preview = engine.normalize(source, raw, input_format=source.input_format)
if preview.status not in {"completed", "partial"}:
    raise RuntimeError(preview.public_dict())
namespace = preview.data["source"]["namespace"]
context = OperationContext(
    principal="editor", client_id="my-application", tenant="workspace-42",
    allowed_namespaces=frozenset({namespace}))
saved = engine.execute("import_bundle", {
    "result": preview.public_dict(), "persist": True
}, context=context)
hits = engine.execute("search", {
    "query": {"terms": ["Council"], "limit": 10}
}, context=context)
exported = engine.execute("export", {
    "bundle": preview.data, "format": "zip"
}, context=context)
for name, result in (("save", saved), ("search", hits), ("export", exported)):
    print(name, result.public_dict())
```

SQLiteStorage opens and closes its connections per operation; it has no long-lived
connection or `close()` method. Your custom storage may own a different lifecycle.

Normalization and preview do not create your application's canonical records.
`import_bundle` stores connector evidence only when explicitly asked. Your product
still decides how to review, reconcile and save canonical records, and whether to
publish anything. See the executable [independent Python example](../examples/sdk_saved_capture.py).

### Identity and isolation

Keep `(provider, namespace, record_type, external_id)` together. A provider ID
alone is not globally unique. The application tenant/profile ID is separate from
the provider's stable source namespace. Preserve `identity.derivation` and
`identity.stability`: a supplied URL or capture-position key is not an invented
native provider ID. Preserve `original`, raw capture hashes, source revisions,
relationships and citations alongside normalized fields.

Use the same trusted principal/client/tenant to reopen stored state. Changing
that tuple selects a different storage scope. Do not accept it from untrusted
operation JSON. Configure credentials in private `OperationContext.credentials`,
not source URLs. [Native mappings](PROVIDER-NATIVE-MAPPINGS.md) describe legacy
identity boundaries; do not guess aliases across portal/API migrations.

### Live discovery and known-record retrieval

```python
from quorumrelay import Bounds

source = Source("legistar", "https://webapi.legistar.com/v1/olympia")
result = engine.discover(source, bounds=Bounds(
    date_from="2026-11-01", date_to="2026-11-30",
    max_pages=2, max_records=20, deadline_seconds=20))
detail = engine.fetch_record(source, "7011", bounds=Bounds(deadline_seconds=15))
```

These are real bounded public reads, not the synthetic example above. Run them
only against your explicitly configured source. Provider access can change; read
capabilities and the returned coverage. Date endpoints are inclusive. A supplied
continuation belongs to its source/query/caller/current grants; some public-form
adapters keep private process-local sessions and expire after 15 minutes. Restart
or expiry can require beginning a fresh bounded operation. Never edit a token.

Fetch a linked attachment using the returned record and document index:
`engine.fetch_attachment(source, record, index=0, context=context)`. Retain its
original capture in scoped storage, or supply the original capture bytes through
the helper's `capture=` argument. Arbitrary client URLs are not attachment grants.

### Local search versus native search

`search` without `native` searches supplied records/bundles or the caller's stored
evidence. It does not fetch linked PDFs, run OCR or invent a transcript. Text
segments retain their field, page/timestamp, language and citation provenance.

```python
native = engine.execute("search", {
    "native": True,
    "source": source.public_dict(),
    "query": {"terms": ["Council"], "limit": 10},
    "bounds": {"max_pages": 2, "max_records": 20}
})
```

Native adapters use verified provider candidate routes and apply local exact
matching over returned metadata/text. Field coverage differs by provider; this
does not turn provider results into full-archive or full-transcript search.
An unavailable native hook reports the gap rather than silently running local
search. `extract_text` is also available through Python's engine for supplied
supported bytes; it is not in the 16 public transport operation names.

## 5. CLI and JSONL

```powershell
'{}' | quorumrelay providers
quorumrelay discover --request request.json --content calendar.json
quorumrelay search --jsonl --request queries.jsonl --database state.sqlite
quorumrelay export --request export.json --database state.sqlite --output evidence.zip
```

Each request is a JSON object. JSONL means one request/result per nonblank line,
sharing one process/engine/store. `--content` supplies saved input bytes;
`content_base64` is the inline JSON equivalent. `--file-root` restricts explicit
local paths. `--output` creates a new export file and keeps stdout as JSON
metadata. `--write-file CHANGE PART PATH` and `--export-file INDEX PATH` stage
explicit large-file parts for matching metadata-only entries; they do not grant
write permission. Parser and transfer limits remain separate.

Exit codes are 0 completed, 2 partial, 3 cancelled, 4 failed, 5 unsupported and
64 invalid framing/configuration. Do not treat useful partial data as a silent
success or discard it because the exit code is nonzero. See [full flags and file contracts](INTERFACES.md).

## 6. HTTP service and curl

For a first local read-only session:

```sh
quorumrelay serve --database app-state.sqlite
curl --fail-with-body http://127.0.0.1:8765/v1/info
curl --fail-with-body -H "Content-Type: application/json" --data '{}' \
  http://127.0.0.1:8765/v1/operations/providers
```

In PowerShell use `curl.exe` to select curl explicitly. The process owner stops
the service with Ctrl+C. It is loopback-only by default. For a request file use
`--data-binary @request.json`; encode parser bytes as `content_base64`, or upload
an explicitly authorized file and pass its opaque `file_handle`.

| Endpoint | Meaning |
|---|---|
| `GET /v1/info` | Version/schema and service information |
| `GET /openapi.json` | Source-generated OpenAPI 3.1 contract |
| `POST /v1/operations/{operation}` | Execute one shared operation |
| `POST /v1/jobs/{operation}` | Submit bounded asynchronous work; inspect its operation ID |
| `POST /v1/files` | Multipart `file` or raw octet-stream upload |
| `GET /v1/files/{handle}` | Authenticated, scoped byte stream |
| `/mcp` | Optional official-SDK Streamable HTTP transport |

[OpenAPI download](api/openapi.json), [generated API reference](API-REFERENCE.md)
and [JSON schemas](api/schemas/result.schema.json) are generated from the actual
implementation. They are not a running public QuorumRelay service. This website
serves documentation; applications host their own API.

### Configure a trusted service principal

Create a private configuration file with a locally generated high-entropy token.
The following marker is deliberately not a deployable credential:

```json
{
  "service": {
    "host": "127.0.0.1",
    "port": 8765,
    "tokens": {
      "REPLACE-WITH-A-GENERATED-SERVICE-TOKEN": {
        "principal": "editor",
        "client_id": "my-app",
        "tenant": "workspace-42",
        "operations": ["providers", "capabilities", "discover", "fetch", "normalize", "search", "import_preview", "import_bundle", "export", "status", "cancel"],
        "authorization": []
      }
    }
  }
}
```

Start with `quorumrelay serve --config private-service.json --database state.sqlite`.
Send `Authorization: Bearer SERVICE_TOKEN`. Protect the file with OS permissions.
Provider credentials, if needed, belong inside that trusted principal's
`credentials` configuration; they are never public operation arguments.

Non-loopback binding requires `allow_network`, authenticated tokens and an
explicit `allowed_hosts` list. Configure exact `allowed_origins`, HTTPS/reverse
proxy and resource ceilings yourself; no hosted deployment or login provider is
created for you. Service tokens must never be forwarded to provider URLs.

### Long jobs and files

Submission returns HTTP 202 with an operation ID and a partial/running result,
not completed work. Use `status` with `{"operation_id":"..."}` to read the final
result and `cancel` to request cooperative cancellation. A service restart does
not fabricate a resumed worker. Recover the existing receipt before deciding
whether to retry an uncertain write.

For large exports send `"stream": true`. Read `data.artifact_id` and fetch its
file stream; verify the advertised length/hash. Upload handles, exported
artifacts, expiry and current grants are scoped and rechecked. Defaults separate
16 MiB parser inputs from 200 MiB transfer bytes; operators may lower ceilings.
The HTTP service also caps operation JSON. [File details](INTERFACES.md) explain
neutral ZIP/JSONL and legacy handles.

## 7. TypeScript / JavaScript

Build the source package, then install its tarball into your unrelated project:

```sh
cd client
npm ci
npm run build
npm pack
# In your own application:
npm install /path/to/quorumrelay-client-0.1.0-dev.8.tgz
```

```typescript
import { QuorumRelayClient, ServiceError } from "quorumrelay-client";

const client = new QuorumRelayClient({
  baseUrl: "http://127.0.0.1:8765",
  token: process.env.QUORUMRELAY_SERVICE_TOKEN,
  timeoutMs: 90_000,
});
const info = await client.info();
if (info.data.version !== "0.1.0.dev8") throw new Error("Service pin mismatch");
try {
  const result = await client.execute("providers", {});
  console.log(result.status, result.data, result.errors, result.coverage);
} catch (error) {
  if (error instanceof ServiceError) console.error(error.httpStatus, error.result);
  throw error;
}
```

`execute`, `submit`, `info`, `upload(Blob)` and `download(handle)` accept an
optional abort signal. `download` returns a streaming `Response`; the caller owns
consumption/closure. Timeout/network/abort errors differ from service HTTP errors
and from an engine's partial/failed envelope. The client never starts a service.
Do not embed server/provider tokens in public browser bundles. Use your backend
as the authenticated service client unless an explicit browser deployment is
configured. See [client source/API](../client/README.md) and the executable
[unrelated Node example](../examples/fifth-client.mjs).

## 8. MCP stdio and Streamable HTTP

The service uses the official Python MCP SDK 2.3.0. Each tool accepts
`{"request": <shared engine request>}` and returns the envelope in
`structuredContent` plus JSON text. Tools are not automatic permission grants.

For a stdio host, launch the executable with arguments such as:

```json
{
  "command": "quorumrelay",
  "args": ["mcp", "--database", "/app/state.sqlite", "--config", "/app/trusted-principal.json"]
}
```

Adapt that command specification to your host's configuration format. Stdout is
MCP only. The process owner supplies identity/grants/credentials; stdio does not
issue OAuth tokens. A minimal official SDK client is:

```python
import anyio
from mcp import Client
from mcp.client.stdio import StdioServerParameters

async def main():
    params = StdioServerParameters(command="quorumrelay", args=["mcp"])
    async with Client(params, read_timeout_seconds=90) as client:
        response = await client.call_tool("providers", {"request": {}})
        print(response.structured_content)

anyio.run(main)
```

For HTTP set `service.mcp=true` and connect to the service root plus `/mcp`.
Authenticated HTTP MCP additionally needs `public_url` and `issuer_url` for
protected-resource metadata. The built-in opaque-token policy is not a JWT
signature verifier or authorization server. Python hosts can supply an external
official-SDK token verifier and trusted principal resolver. Validate the audience
and keep service/OAuth identity separate from provider credentials.

Tested revisions are 2026-07-28 and 2025-11-25 on both transports. Modern requests
use per-request version/capabilities; legacy uses initialize/initialized and
SDK-managed sessions. Do not mix their framing/session rules. Cancellation is
cooperative; a completed or uncertain mutation remains in its receipt. Large MCP
uploads use `upload_begin/chunk/finish/abort`; exported resource links expose
bounded chunks with offsets and hashes. See [the full MCP reference](MCP.md) and
[executable modern/legacy examples](../examples/mcp-client.py).

## 9. Exact write lifecycle

Writes are separate from ingestion. A configured native adapter does not grant
the actor permission or establish live vendor acceptance. The application must
supply durable storage, current operation/source policy, provider credentials,
explicit writable resources and approval of the exact immutable plan.

1. Call `plan_write` with the source and typed changes/files.
2. Display the actual planned native request, before state, changes and limits.
3. Obtain product approval and retain `plan_id` plus `plan_hash`.
4. Call `commit_write` with only those exact values under the same current scope.
5. Read `receipt`; reconcile ambiguous/lost responses before retrying.

Do not pass identity, credentials or `authorization` in operation JSON. CLI/HTTP
principal policies require the operations plus `write:plan` / `write:commit`
grants; a hash itself is not a grant. Native provider policy additionally binds
namespaces, operations and resource/meeting IDs. Current policy revocation is
checked again at commit and readback. Create operations are not blindly replayed
after a lost response. The exact [write contract](WRITE-CONTRACT.md) documents
Legistar, Wistia, Repository and Essential mappings and unresolved live behavior.

Publication is allowed while this vendor acceptance remains deferred. Never turn
a synthetic receipt into a claim that a real tenant was changed. The executable
examples refuse non-mock commits; they cannot be repurposed as live acceptance
without a separately configured designated test environment.

## 10. Schemas and connector/storage extensions

```python
from quorumrelay.schemas import json_schema
result_schema = json_schema("result")
```

Schemas use JSON Schema 2020-12 and schema version 2.0.0. Result/status and core
fields are versioned; raw original values and unknown additive fields are
preserved separately. Generated TypeScript definitions come from the same schema
resources. See [all generated schema downloads](API-REFERENCE.md#json-schemas).

Implement `Connector` from `quorumrelay.extensions`, run
`check_connector(connector)`, then pass it to `create_engine(connectors=(... ,))`.
The conformance helper checks hook shape/capability return type without opening
provider sockets or performing writes. It does not certify a provider contract.
New connectors use the same record/result/security boundary across all transports.
An additive parser can be registered with `engine.register_parser`; baseline
formats cannot be replaced through this path. The runnable
[example connector](../examples/example_connector.py) demonstrates registration.

A custom `Storage` implements atomic `put/get/list`, caller scope and version
comparison. Preserve `create_only` / `expected_version` behavior and immutable
captures. Optional streaming/batch hooks improve large-file behavior; consult
[the storage contract](ENGINE-CONTRACT.md). A connector's `plan_write` method
cannot bypass the shared WriteAdapter/plan/receipt coordinator.

## 11. Verify an integration without vendor writes

Use the synthetic SDK/CLI/HTTP/Node/MCP examples in [examples](../examples/README.md).
Keep their `mock=True` checks. Verify preview versus explicit persistence,
cross-tenant denial, useful partial results, duplicate/restart behavior, portable
export hashes and exact receipts. Reuse the same engine fixture across interfaces
instead of implementing provider rules in each client. Public source text is data,
not instructions for an agent or service.

Repository checks are documented in [contributing](../CONTRIBUTING.md). They do not
automatically prove your deployment's credentials, provider access, reverse proxy,
OAuth authority, installed application or live write/readback behavior. Record
those separately. See [release notes](RELEASE-NOTES.md) for development artifacts
and the [user manual](USER-MANUAL.md) for operational troubleshooting.
