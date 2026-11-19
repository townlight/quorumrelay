# Operation requests and responses

QuorumRelay **0.1.0.dev15**, result schema **2.0.0**. These are shared engine requests. Send the object itself to HTTP `POST /v1/operations/{operation}` or to `quorumrelay {operation}` on stdin. For MCP, call the tool with the same operation name and arguments `{"request": <object>}`. Provider-specific selectors and write fields are described in the [provider guides](PROVIDER-COVERAGE.md) and [write contract](WRITE-CONTRACT.md).

## Source and discovery

| Operation | Required request fields | Common optional inputs | Typical result data |
| --- | --- | --- | --- |
| `providers` | None. Send `{}`. | — | `providers` with IDs, aliases and input formats |
| `capabilities` | None. Send `{}` for the inventory. | `provider` to select a connector | `providers` with operation and evidence records |
| `identify` | `url` (or `source.url`) | — | Recognition, candidates and ambiguity |
| `validate_source` | `source` | Provider-specific configuration in `source.options` | Validated source and recognition details |
| `discover` | `source` | `bounds`, `record_types` where mapped, saved `content_base64` or a scoped `file_handle` on HTTP | Records, source captures and bundles; `coverage` contains bounds, failures and checkpoint when available |

A source requires `provider` and `url`. Optional properties are `namespace`, `body`, `input_format` and `options`. The provider determines the namespace. Place credentials in trusted context or service configuration. Never send them in a request body or source URL. See the [source and bounds contracts](ENGINE-CONTRACT.md#common-serialization).

### Saved discovery request

This synthetic request is executable without an upstream connection. It submits one saved Legistar Events row.

```json
{
  "source": {
    "provider": "legistar",
    "url": "https://mock-city.legistar.com/Calendar.aspx",
    "input_format": "legistar-events-json"
  },
  "content_base64": "W3siRXZlbnRJZCI6NywiRXZlbnRCb2R5TmFtZSI6IkNvdW5jaWwiLCJFdmVudERhdGUiOiIyMDI2LTExLTExVDAwOjAwOjAwIiwiRXZlbnRUaW1lIjoiNzowMCBQTSJ9XQ==",
  "bounds": {"max_records": 5}
}
```

The response contains one meeting with external ID `7`, the original capture and its provenance. This is an excerpt. Retain the full response in your app.

```json
{
  "schema_version": "2.0.0",
  "status": "partial",
  "errors": [],
  "coverage": {
    "returned_records": 1,
    "truncated": false,
    "checkpoint": null,
    "scope": "one saved capture, not a complete upstream catalog"
  }
}
```

## Retrieve and normalize

| Operation | Required request fields | Common optional inputs | Typical result data |
| --- | --- | --- | --- |
| `fetch` | `source` and a supported selector. A simple detail request uses `external_id`. | `bounds`; provider-specific selectors; `attachment` with captured parent/evidence for supported transfers | A detail, related records or a captured artifact, depending on the selector |
| `normalize` | `source` and original bytes. Use `content_base64`, HTTP file input or SDK/CLI bytes. | `input_format` if already specified on the source, `bounds` | Capture bundle with records, raw capture and compatibility preview where applicable |

For example, use `{"source":{"provider":"legistar","url":"https://webapi.legistar.com/v1/olympia/events"},"external_id":"7011"}` for a live Legistar detail. Use the [manual’s fetch examples](USER-MANUAL.md#fetch-one-known-record-or-a-supplied-attachment) for attachment membership and transfer inputs. A supplied player or file link can be retained as a locator without an available download.

## Search and interchange

Examples below are request templates. Replace the string placeholders for upstream objects with the complete objects returned by earlier operations.

| Operation | Example | Input and result details |
| --- | --- | --- |
| `search` | `{"query":{"terms":["Council"],"limit":5}}` | With scoped storage, searches stored records. Alternatively send a `result`, `bundle` or `records` for a local search over passed data. Set `native:true` with a supported configured `source` to search upstream. Returns hits and coverage. |
| `import_preview` | `{"result":"DISCOVERY_RESULT"}` | Pass one upstream result, capture bundle, or supported source/file input. Returns a preview bundle and persistence status without saving. |
| `import_bundle` | `{"result":"DISCOVERY_RESULT","persist":true}` | Pass the same inputs as preview. Persistence defaults to false and needs configured scoped storage when true. Returns the saved bundle and persistence information. |
| `export` | `{"bundle":"SAVED_BUNDLE","format":"zip","stream":true}` | Supply a bundle, result, stored `bundle_key` or applicable records. Neutral formats are JSON, JSONL and ZIP. CSV/ICS report projection losses. For streamed delivery, use the returned artifact or file handle via the chosen transport. |

To import an existing ZIP over HTTP, upload it to `POST /v1/files` and pass `{"format":"zip","file_handle":"HANDLE"}` to preview or import. A handle is scoped to the caller. See [file transfers](INTERFACES.md#files-and-long-operations) and the [synthetic workflows](../examples/README.md) for complete requests and the actual responses.

## Jobs and files

| Method and path | Request | Response |
| --- | --- | --- |
| `GET /v1/info` | No body. Use the configured service bearer if required. | Installed version and result schema version |
| `POST /v1/jobs/{operation}` | Same operation body as a synchronous call, for the [listed job routes](API-REFERENCE.md#http-endpoints) | HTTP 202 with an `operation_id` and running state |
| `POST /v1/operations/status` or `cancel` | `{"operation_id":"RETURNED_ID"}` | Stored job state and terminal result when available, or cancellation requested |
| `POST /v1/files` | Multipart field `file` or raw `application/octet-stream` | Scoped `file_handle` |
| `GET /v1/files/{handle}` | Same authorized caller as the upload/export | Download stream |
| `GET /openapi.json` | No body | Running HTTP service’s OpenAPI document |
| `/mcp` | Enable MCP; use the negotiated [Streamable HTTP protocol](MCP.md#streamable-http-and-authentication) | MCP tool results and resource reads |

Cancellation is cooperative. Poll for the actual terminal state. MCP also exposes the shared status/cancel tools and supports protocol cancellation.

## Exact write lifecycle

| Operation | Required request fields | Result |
| --- | --- | --- |
| `plan_write` | `source`, nonempty `changes` array, optional `bounds`. Each change identifies its key, entity, operation and mapped fields or files. | The immutable plan, `plan_id` and `plan_hash` for review |
| `commit_write` | `{"plan_id":"RETURNED_ID","plan_hash":"RETURNED_HASH"}` and approval through trusted caller policy | Receipt with write outcome and available readback |
| `receipt` | `{"plan_id":"RETURNED_ID"}` | Existing scoped receipt for that plan |

For complete synthetic planning JSON and a worked example, use the [write contract](WRITE-CONTRACT.md#public-operations) and [example workflows](../examples/README.md). A timeout during commit calls for reading the existing receipt before any retry. TownCloud write work remains parked.

## Interpret results consistently

Inspect `status`, `errors`, `coverage` and `operation_id` on every response. An HTTP `200` can carry a `failed` or `unsupported` operation result.

| Status | How to handle it |
| --- | --- |
| `completed` | The requested bounded operation completed. Check its scope before making broader claims. |
| `partial` | Keep usable records and retain coverage or errors. Resume with a returned checkpoint and the same bound source, caller and filters where supported. |
| `failed` | Inspect typed errors and any returned coverage. Resolve the cause before retrying. |
| `unsupported` | This adapter has no mapped path for the request. Surface the reason to the caller. |
| `cancelled` | Work stopped cooperatively. Keep completed steps and any existing receipts. |
