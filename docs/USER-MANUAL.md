# QuorumRelay user manual

Candidate <code>0.1.0.dev8</code> · schema <code>2.0.0</code>

QuorumRelay is a standalone engine for identifying configured civic-data sources, reading or parsing bounded captures, normalizing meeting records, searching captured material, preparing neutral exports, and executing a small set of explicitly authorized provider writes. It does not require Townlight, TownReporter, TownRecord, Brief, a hosted service, or a particular application database. Those projects are examples of consumers; the engine API is intended for other products as well.

This is a development candidate. The verified Python wheel is <code>quorumrelay-0.1.0.dev8-py3-none-any.whl</code>, SHA-256 <code>bcfe691b4d1eb0de162f5f94985d0242a97b5d3d89bd5eeb9306d1ef28caf692</code>, built from source commit <code>3862e5f4ad7064aee722e09bb438899c3566477f</code>. It is not published to a Python package index. The candidate verification proves package contents and fixture/baseline behavior; it does not prove live provider acceptance, complete provider catalogs, or live write acceptance. See [the development 08 receipt](verification/quorumrelay-development-08.json), [the baseline equality receipt](verification/quorumrelay-development-08-equality.json), and [the capability matrix](capabilities/README.md).

## 1. Install and verify the candidate

QuorumRelay requires Python 3.11 or newer. Use the public source checkout at the verified commit for this publication. The dev8 wheel is documented as verification evidence but is not a public download asset; use a wheel only if your operator already has the matching immutable artifact. Do not use a package-index install command for this candidate.

### Install from the public Git repository

~~~powershell
git clone https://github.com/townlight/quorumrelay.git C:\work\quorumrelay
Set-Location C:\work\quorumrelay
git checkout 3862e5f4ad7064aee722e09bb438899c3566477f
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
~~~

For the REST/HTTP and MCP service commands, install the optional service dependencies from the same checkout:

~~~powershell
py -m pip install -e ".[service]"
~~~

The <code>service</code> extra installs the MCP, Starlette, Uvicorn, multipart and JSON-schema dependencies. The core SDK can be used without these service packages.

### Install the verified wheel

This repository does not offer a public wheel download for the candidate. If your operator has already transferred the exact immutable wheel into an approved artifact store, verify its digest before installing it:

~~~powershell
Get-FileHash .\quorumrelay-0.1.0.dev8-py3-none-any.whl -Algorithm SHA256
py -m pip install .\quorumrelay-0.1.0.dev8-py3-none-any.whl
~~~

Use only the immutable artifact whose hash is recorded above; rebuilding from source produces a different artifact identity. To run the HTTP or MCP service from source, install the matching checkout’s <code>.[service]</code> extra as shown above.

### Verify the installed package

~~~powershell
py -c "import quorumrelay; print(quorumrelay.__version__)"
'{}' | quorumrelay providers
~~~

The version command should print <code>0.1.0.dev8</code>. The <code>providers</code> command returns the installed provider and format manifest as JSON. In an embedded deployment, also request <code>GET /v1/info</code> and compare the installed version and schema version with the application’s approved pin.

## 2. Choose a provider and input format

The package contains 31 canonical provider families. These are identifiers accepted by the engine; they are not claims that every tenant is reachable or every vendor feature is implemented.

| Canonical provider IDs | Canonical provider IDs | Canonical provider IDs |
|---|---|---|
| <code>legistar</code> | <code>primegov</code> | <code>granicus</code> |
| <code>novusagenda</code> | <code>civicplus-select</code> | <code>civicplus-agenda-center</code> |
| <code>municode-meetings</code> | <code>boardbook</code> | <code>escribe</code> |
| <code>simbli</code> | <code>civicweb</code> | <code>iqm2</code> |
| <code>swagit</code> | <code>suiteone-media</code> | <code>peak</code> |
| <code>utah-public-notice</code> | <code>destiny-agendaquick</code> | <code>town-hall-streams</code> |
| <code>telvue</code> | <code>champ</code> | <code>onbase</code> |
| <code>laserfiche-weblink</code> | <code>towncloud</code> | <code>digital-towpath</code> |
| <code>clerkbase</code> | <code>first-party</code> | <code>wistia</code> |
| <code>boardable</code> | <code>gworks</code> | <code>boarddocs</code> |
| <code>tyler-meeting-manager</code> |  |  |

Ask the installed engine for the authoritative provider-specific choices:

~~~python
from quorumrelay import create_engine

engine = create_engine()
manifest = engine.execute("providers", {}).public_dict()
for provider in manifest["data"]["providers"]:
    print(provider["provider"], provider.get("formats", []),
          provider.get("additional_formats", []))
~~~

The fixed compatibility baseline contains 34 provider/input-format pairs. The additive parser hooks expose 28 more provider-specific captured formats in this candidate. A baseline format keeps its exact historical reader behavior; additive formats replay other captured details or API responses. An additive parser is a saved-capture capability and does not imply that QuorumRelay can discover that provider live. Use the exact <code>input_format</code> returned for the provider. Do not choose a parser by guessing from a filename.

Use <code>capabilities</code> for the provider’s operation-level implementation and acceptance information:

~~~python
result = engine.execute("capabilities", {"provider": "legistar"})
~~~

Read its status fields separately. A documented provider feature, an implemented operation, a fixture-tested parser, a bounded public read and authorized live acceptance are different evidence levels. The inventory and [provider coverage map](ENGINE-COVERAGE.md) explain current limits.

## 3. Configure a source and caller

A source describes a provider and a durable HTTP(S) citation or route. It is not the consumer’s tenant identifier and must not contain credentials.

~~~python
from quorumrelay import Bounds, OperationContext, Source

source = Source(
    provider="legistar",
    url="https://webapi.legistar.com/v1/example-city/events",
    namespace="//webapi.legistar.com/v1/example-city",
    input_format="legistar-events-json",
)
~~~

Replace the example tenant with a verified source for your organization. Keep the configured namespace equal to the provider-derived namespace. It is the stable identity used for records and source grants. The application’s principal, client and tenant identify the consumer and scope its stored state.

For an in-process integration, create a context with the current user’s established authorization and source restrictions:

~~~python
context = OperationContext(
    principal="meeting-import-worker",
    client_id="your-application",
    tenant="your-configured-organization",
    allowed_operations=frozenset({
        "providers", "capabilities", "identify", "validate_source",
        "discover", "fetch", "normalize", "search", "import_preview",
        "import_bundle", "export", "status", "cancel",
    }),
    allowed_namespaces=frozenset({source.namespace}),
)
~~~

A default context is useful for local read-only SDK use. Production callers should set the real application principal/client/tenant and least-privilege operation and namespace policies. Provider credentials, when needed, belong in the private trusted <code>OperationContext.credentials</code> supplied by the application. Provider credential formats vary; follow the exact provider entry in [the SDK guide](SDK.md) and [native mappings](PROVIDER-NATIVE-MAPPINGS.md). Never put credentials in <code>Source.url</code>, operation JSON, a source option, or a citation.

<code>Source.options</code> contains only provider-documented configuration. For example, Tyler calendar requests require an observed tenant-specific API base; the configured API base must match that tenant’s observed client. An option is not an unrestricted request target. Set <code>Source.body</code> only where the provider mapping recognizes that body. Unmapped body assignments remain an explicit unknown instead of being guessed from a city or meeting label.

## 4. Read, parse and fetch

### Identify and inspect a source

<code>identify</code> compares a URL or capture pattern with registered source identities. It does not log in or prove access. <code>validate_source</code> checks a configured source using the operation supported for that provider; do not treat it as a universal health check. Use <code>providers</code> and <code>capabilities</code> before choosing a live operation.

~~~python
identified = engine.execute("identify", {"url": source.url}, context=context)
configured = engine.execute("validate_source", {"source": source.public_dict()}, context=context)
~~~

### Discover bounded records

Discovery is a live or explicitly saved source read, depending on the provider adapter. Supply date and volume bounds:

~~~python
result = engine.discover(
    source,
    bounds=Bounds(
        date_from="2026-11-01",
        date_to="2026-11-30",
        max_pages=5,
        max_records=200,
        deadline_seconds=30,
    ),
    context=context,
)
~~~

Dates are inclusive. The connector may support fewer filters than the shared model, may require explicit date or body information, or may report unknown dates. Check <code>status</code>, <code>errors</code>, and <code>coverage</code> before using any records. <code>partial</code> means the result may contain useful records with a known limit; it is not a successful-complete catalog. A provider returning an empty page does not by itself prove that the source has no records.

### Normalize a saved capture

Normalization parses the exact bytes supplied by your application and does not persist them or contact the provider.

~~~python
from pathlib import Path

capture_bytes = Path("captures/legistar-events.json").read_bytes()
preview = engine.normalize(
    source,
    capture_bytes,
    input_format="legistar-events-json",
    bounds=Bounds(max_records=250),
    context=context,
)
~~~

Or call the common operation explicitly:

~~~python
preview = engine.execute(
    "normalize",
    {
        "source": source.public_dict(),
        "input_format": "legistar-events-json",
        "bounds": {"max_records": 250},
    },
    content=capture_bytes,
    context=context,
)
~~~

The returned data is a <code>CaptureBundle</code> containing source identity, normalized records, compatibility projection, raw capture metadata and coverage. Original capture bytes and unknown provider values are retained. The normalized fields are a convenient shared view, not a replacement for the source record.

### Fetch one known record or a supplied attachment

Use a detail request only when the provider has a documented/evidenced detail adapter:

~~~python
detail = engine.fetch_record(
    source, "7011",
    bounds=Bounds(deadline_seconds=20),
    context=context,
)
~~~

To retrieve a document already linked from a captured record, select its captured index. This operation does not accept an arbitrary caller URL:

~~~python
record = result.data["records"][0]
document = engine.fetch_attachment(
    source, record, index=0, kind="documents",
    capture=capture_bytes,
    bounds=Bounds(transfer_bytes=50 * 1024 * 1024),
    context=context,
)
~~~

If the bundle is stored, the helper can resolve the stored capture instead of receiving <code>capture</code>. Keep durable citation URLs separately from short-lived signed download URLs. Check the attachment result for availability, hash, byte length, content type and errors.

A captured media player URL may return a player page instead of media. Where a provider captured a direct <code>video_url</code>, <code>audio_url</code> or <code>playback_url</code>, select that existing field with <code>kind="recordings"</code> and <code>url_field="video_url"</code> (or the verified field). QuorumRelay does not let the caller substitute a URL. An HLS fetch returns the manifest, not all segments; it is not proof that a recording is playable.

## 5. Import, persist, search and export

### Preview before persistence

Use <code>import_preview</code> to see which records would be new, unchanged or changed in the current QuorumRelay store. Preview does not write state.

~~~python
preview_import = engine.execute(
    "import_preview",
    {"result": result.public_dict()},
    context=context,
)
~~~

To persist explicitly, configure storage and pass <code>persist: true</code>:

~~~python
from quorumrelay.storage import SQLiteStorage

engine = create_engine(storage=SQLiteStorage("state/quorumrelay.sqlite3"))
saved = engine.execute(
    "import_bundle",
    {"result": result.public_dict(), "persist": True},
    context=context,
)
~~~

The import uses scoped atomic storage and reports conflicts rather than blindly replacing newer values. QuorumRelay storage is not your application’s canonical meeting database. Your application still owns destination record IDs, duplicate resolution, source transition decisions and user review. Do not infer that a source transition is safe from matching hostnames or similar IDs.

### Search stored captures or a provider

By default, <code>search</code> searches records in the configured QuorumRelay store. It matches normalized metadata and explicitly supplied text; it does not add OCR, transcription or missing provider text.

~~~python
from quorumrelay import Query

hits = engine.search(
    Query(terms=("budget",), phrases=("public comment",), limit=50),
    context=context,
)
~~~

A provider-specific native search is opt-in:

~~~python
native = engine.execute(
    "search",
    {
        "native": True,
        "source": source.public_dict(),
        "query": {"terms": ["Council"], "limit": 20},
        "bounds": {"date_from": "2026-11-01", "date_to": "2026-11-30",
                   "max_pages": 2, "max_records": 100},
    },
    context=context,
)
~~~

Only use this when <code>capabilities</code> says that provider has an implemented native search. Provider search typically selects candidate records; QuorumRelay then applies exact local matching to fields that were actually supplied. Check the response’s <code>coverage</code> for searched fields, candidate limits, omitted rows and checkpoint information. A native result is not a promise of full-text or catalog coverage.

### Export portable records

The neutral <code>export</code> operation emits JSON, JSONL or ZIP bundles. CSV and iCalendar are explicit projections and can lose unsupported meeting fields; the result reports losses. Export does not contact a vendor or mutate records.

~~~python
exported = engine.execute(
    "export",
    {"bundle": saved.data["bundle"], "format": "zip", "stream": True},
    context=context,
)
~~~

Large streamed exports return a scoped artifact ID. Use the HTTP file endpoint, the MCP resource flow, or the SDK artifact helper for the selected interface. Do not persist a local artifact path or assume an artifact ID can be used by another caller. Provider-specific file preparation is a separate opt-in operation documented by that provider; it is not a vendor upload.

## 6. Write workflow

Writes are separate from read, import, search and export. The default engine registers evidenced native adapters but supplies no credentials or grants. Write access requires a supported mapping, trusted source/credential policy, durable atomic storage, the <code>write:plan</code> and <code>write:commit</code> grants, and approval of one exact plan.

1. Ask <code>plan_write</code> to validate the proposed provider-native change.
2. Review every planned entity, source namespace, field, parent/resource ID, file hash, expected state and mock/live transport marker.
3. Approve the exact returned <code>plan_id</code> and <code>plan_hash</code> through your application’s authorization flow.
4. Call <code>commit_write</code> with only that plan ID and hash.
5. Read <code>receipt</code> for the durable outcome. If the response was lost or the receipt is uncertain, reconcile that receipt before deciding whether to retry.

~~~python
from quorumrelay import create_engine
from quorumrelay.storage import SQLiteStorage

# Load this from protected operator configuration; its shape is provider-specific.
write_context = OperationContext(
    principal="authorized-write-worker",
    client_id="your-application",
    tenant="authorized-test-organization",
    authorization=frozenset({"write:plan", "write:commit"}),
    allowed_operations=frozenset({"plan_write", "commit_write", "receipt"}),
    allowed_namespaces=frozenset({source.namespace}),
    credentials=trusted_provider_credentials,
)
write_engine = create_engine(storage=SQLiteStorage("state/quorumrelay-writes.sqlite3"))
planned = write_engine.plan_write(
    source,
    {
        "changes": [{
            "key": "meeting-2026-11-11",
            "entity": "event",
            "operation": "create",
            "fields": {"EventDate": "2026-11-11T00:00:00", "EventBodyId": 4},
        }],
    },
    context=write_context,
)
# Review planned.data["plan"] before obtaining the application's exact approval.
approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
committed = write_engine.commit_write(approval, context=write_context)
receipt = write_engine.receipt({"plan_id": approval["plan_id"]}, context=write_context)
~~~

The native fields are provider-specific. A neutral meeting record is not automatically a writable vendor request. Unknown fields, unsupported entities, deletion, arbitrary URLs and generic administration are rejected. An ambiguous create is not blindly repeated: the write coordinator persists intent and reconciles against readback. Completed siblings remain visible in a partial batch; no automatic remote rollback occurs.

Live write acceptance for this candidate is **NOT_RUN**. The mappings have deterministic fixture checks, but no authorized provider test tenant and credentials have been supplied. Synthetic or mock receipts are not vendor acceptance. Do not use a public city’s production data as a test environment. See [the write contract](WRITE-CONTRACT.md) for the currently mapped operations and their exact fields.

## 7. Run the CLI or service

### CLI

The console command accepts a single JSON request from stdin or <code>--request</code>. Add <code>--jsonl</code> for one request per nonblank line. <code>--content</code> supplies saved source bytes; <code>--file-root</code> confines local input paths. Stdout contains JSON result envelopes; diagnostics go to stderr.

~~~powershell
$Request = @{
  source = @{
    provider = "legistar"
    url = "https://webapi.legistar.com/v1/example-city/events"
    namespace = "//webapi.legistar.com/v1/example-city"
  }
  bounds = @{ date_from = "2026-11-01"; date_to = "2026-11-30"; max_pages = 3 }
} | ConvertTo-Json -Depth 12

$Request | quorumrelay discover --database C:\app\state\connectors.sqlite
~~~

For file output, use <code>--output</code> only with one <code>export</code> request. The file is created exclusively; an existing file is not overwritten. <code>--write-file CHANGE PART PATH</code> supplies one declared metadata-only write-plan file part. <code>--export-file INDEX PATH</code> supplies a declared export file. Both require the selected local file to remain under <code>--file-root</code> if that option is set.

Exit codes are 0 for completed, 2 partial, 3 cancelled, 4 failed, 5 unsupported and 64 invalid request/configuration. For JSONL, the CLI returns the highest observed code and retains every result.

### REST/HTTP

Install the <code>service</code> extra and run the process under your service manager:

~~~powershell
quorumrelay serve --config C:\app\connector-service.json --database C:\app\state\connectors.sqlite
~~~

The default listener is <code>127.0.0.1:8765</code>.
A minimal token-protected, loopback-only read policy is shown below. Store a generated token in an operator-controlled secret store and render the configuration with restrictive file permissions. This example has no upstream credentials and grants no provider writes.

~~~json
{
  "service": {
    "host": "127.0.0.1",
    "port": 8765,
    "tokens": {
      "replace-with-a-random-secret-at-least-16-characters": {
        "principal": "meeting-reader",
        "client_id": "your-application",
        "tenant": "your-organization",
        "operations": ["providers", "capabilities", "discover", "fetch", "normalize", "search", "import_preview", "import_bundle", "export", "receipt", "status", "cancel"],
        "allowed_namespaces": ["//webapi.legistar.com/v1/example-city"]
      }
    }
  }
}
~~~

For an account API, configure provider-specific credentials only in trusted private process configuration and bind them to the exact origin, tenant and namespace required by that adapter. The source namespace is still separate from the consumer tenant. `examples/service.mock.json` uses synthetic values and is not deployment configuration.

Check <code>GET /v1/info</code> and <code>GET /openapi.json</code>. Submit a shared engine request as JSON:

~~~powershell
$Headers = @{ Authorization = "Bearer $env:QUORUMRELAY_TOKEN" }
$Body = @{ source = $Source; bounds = @{ max_pages = 2; max_records = 50 } } | ConvertTo-Json -Depth 12
Invoke-RestMethod -Method Post -Uri "$env:QUORUMRELAY_URL/v1/operations/discover" -Headers $Headers -ContentType "application/json" -Body $Body
~~~

The token shown here must come from your trusted deployment configuration. Do not place it in a saved request or log it. The service returns the same complete result envelope used by the SDK. Long operations may use <code>POST /v1/jobs/{operation}</code>; poll with the shared <code>status</code> operation and request cooperative cancellation with <code>cancel</code>.

File upload uses <code>POST /v1/files</code> and returns an opaque caller-scoped handle, not a path. Retrieve it through <code>GET /v1/files/{handle}</code>. Use file handles for large imports/exports instead of embedding large base64 content in JSON. A handle is not a credential and is not portable across caller scopes.

### MCP

Run local MCP stdio with <code>quorumrelay mcp</code>. An operator-owned client can also use Streamable HTTP at <code>/mcp</code> when the service is explicitly configured for MCP. Both use the same engine operations and result envelope. For supported protocol versions, resource delivery, authentication and cancellation behavior, see [the MCP reference](MCP.md). The service does not issue OAuth tokens or expose provider credentials to model tool arguments.

## 8. Bounds, privacy and operational ownership

Default shared bounds are 1,000 records, 25 pages, 16 MiB parser input, 200 MiB transfer, and a 45-second engine deadline. Providers or service configuration may impose lower limits. HTTP/CLI JSON framing defaults to 24 MiB; the default HTTP operation timeout is 60 seconds. The parser limit and file-transfer limit are separate. Large downloadable bytes do not imply a large parser input can be processed.

The service requires explicit configuration before binding beyond loopback: enable network access, configure authenticated tokens and a non-wildcard Host allowlist, and set allowed origins for your deployment. Put it behind an operator-managed HTTPS reverse proxy. MCP network use with service tokens also needs the configured public resource URL, issuer URL and a verifier suitable for the deployment. Follow [the interface security notes](INTERFACES.md) and [MCP reference](MCP.md).

Use a private database path and restrict its filesystem permissions. SQLite uses WAL and full synchronous commits; the consumer owns backup, retention, restore testing, service lifecycle and file storage. Storage keys are scoped by principal, client and consumer tenant. Keep those three values stable while using existing records, checkpoints and write receipts. A new identity scope cannot see the old scope’s state.

Provider responses and document text are untrusted input. Preserve original captures and their hashes, validate dates/source identities, and apply your own editorial or records-management review. The engine does not publish articles, send notices, host an application’s canonical meeting records, or decide that an imported change is editorially approved.

## 9. Bounds, continuation and failure recovery

Always read all of <code>OperationResult</code>: <code>status</code>, <code>data</code>, <code>errors</code>, <code>coverage</code> and <code>operation_id</code>. The status values are:

| Status | Meaning |
|---|---|
| <code>completed</code> | The requested bounded operation completed. It does not promise an entire provider archive. |
| <code>partial</code> | Some data may be usable; inspect errors, truncation, unknown fields and scope. |
| <code>cancelled</code> | Cooperative cancellation stopped future work; prior completed work or receipts remain. |
| <code>failed</code> | The operation could not complete under the given request or policy. |
| <code>unsupported</code> | No evidenced operation is registered for that request. This is not an empty result. |

A continuation token is opaque state. Supply the exact returned checkpoint under <code>bounds.checkpoint</code> only with the same source, query, caller scope, date/body/type filters and current grants. Some adapters keep private cursor state in the current process, so a service restart or expiry may require restarting the bounded read. Do not edit a checkpoint, convert it into a URL or reuse it across callers. If the current page changes, restart according to that adapter’s coverage information.

| Symptom | What to check |
|---|---|
| <code>unsupported</code> or <code>operation_unavailable</code> | Check the canonical provider ID, operation and exact saved format in <code>providers</code>/<code>capabilities</code>. Lack of implementation is not proof the vendor lacks that feature. |
| <code>partial</code>, no error | Read coverage for page/record limits, unknown date/body, provider candidate limits, unavailable text and catalog scope. Do not report it as complete. |
| <code>invalid_capture</code> | Confirm the raw bytes, provider and exact <code>input_format</code>; stay within parser limit. |
| <code>permission_denied</code> | Confirm the authenticated principal’s operation and namespace grants. Caller identity, credentials and grants cannot be supplied in request JSON. |
| Provider 401/403 or missing account records | Check provider-specific credential binding, tenant/origin/namespace and upstream account permission in trusted configuration. Do not retry by changing source origins without evidence. |
| Expired/unavailable checkpoint | Restart the read with the same configured source and current filters. Use the returned partial coverage to decide whether another bounded read is appropriate. |
| File handle missing or rejected | Confirm the same authenticated principal/client/tenant, file purpose, expiry and hash/length. A handle is scoped and temporary. |
| Write response timeout or uncertain receipt | Read the existing <code>receipt</code> for the exact plan. Do not issue a new create until reconciliation determines the prior effect. |

## 10. Related references

- [Python SDK and provider examples](SDK.md)
- [External interfaces, CLI and service security](INTERFACES.md)
- [Engine/schema contract](ENGINE-CONTRACT.md)
- [Write contract and exact native mappings](WRITE-CONTRACT.md)
- [MCP protocol notes](MCP.md)
- [Provider implementation and acceptance coverage](ENGINE-COVERAGE.md)
- [Provider-native endpoint and field evidence](PROVIDER-NATIVE-MAPPINGS.md)
- [Capability research inventory](capabilities/README.md)
- [Independent synthetic examples](../examples/README.md)
