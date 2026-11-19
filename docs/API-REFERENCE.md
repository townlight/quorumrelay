# Generated API reference

Generated from QuorumRelay **0.1.0.dev15** source, OpenAPI **3.1.0**.

These files describe an application-hosted service. The documentation website does not
operate a public provider API or accept credentials. Run your own configured service.

[Operation requests and examples](OPERATION-REQUESTS.md) · [Integration guide](DEVELOPER-GUIDE.md) · [HTTP details](INTERFACES.md) · [MCP](MCP.md) · [OpenAPI JSON download](api/openapi.json)

## HTTP endpoints

Operation endpoints accept a shared JSON request and return the complete schema 2.0.0
result envelope. Provider-specific request details and coverage remain important; the
OpenAPI request object deliberately permits operation-specific fields.

| Method | Path | Operation | Request and result |
|---|---|---|---|
| `POST` | `/v1/operations/providers` | `providers` | [Contract](OPERATION-REQUESTS.md#source-and-discovery) |
| `POST` | `/v1/jobs/providers` | `submit_providers` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/capabilities` | `capabilities` | [Contract](OPERATION-REQUESTS.md#source-and-discovery) |
| `POST` | `/v1/jobs/capabilities` | `submit_capabilities` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/identify` | `identify` | [Contract](OPERATION-REQUESTS.md#source-and-discovery) |
| `POST` | `/v1/jobs/identify` | `submit_identify` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/validate_source` | `validate_source` | [Contract](OPERATION-REQUESTS.md#source-and-discovery) |
| `POST` | `/v1/jobs/validate_source` | `submit_validate_source` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/discover` | `discover` | [Contract](OPERATION-REQUESTS.md#source-and-discovery) |
| `POST` | `/v1/jobs/discover` | `submit_discover` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/fetch` | `fetch` | [Contract](OPERATION-REQUESTS.md#retrieve-and-normalize) |
| `POST` | `/v1/jobs/fetch` | `submit_fetch` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/normalize` | `normalize` | [Contract](OPERATION-REQUESTS.md#retrieve-and-normalize) |
| `POST` | `/v1/jobs/normalize` | `submit_normalize` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/search` | `search` | [Contract](OPERATION-REQUESTS.md#search-and-interchange) |
| `POST` | `/v1/jobs/search` | `submit_search` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/import_preview` | `import_preview` | [Contract](OPERATION-REQUESTS.md#search-and-interchange) |
| `POST` | `/v1/jobs/import_preview` | `submit_import_preview` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/import_bundle` | `import_bundle` | [Contract](OPERATION-REQUESTS.md#search-and-interchange) |
| `POST` | `/v1/jobs/import_bundle` | `submit_import_bundle` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/export` | `export` | [Contract](OPERATION-REQUESTS.md#search-and-interchange) |
| `POST` | `/v1/jobs/export` | `submit_export` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/plan_write` | `plan_write` | [Contract](OPERATION-REQUESTS.md#exact-write-lifecycle) |
| `POST` | `/v1/jobs/plan_write` | `submit_plan_write` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/commit_write` | `commit_write` | [Contract](OPERATION-REQUESTS.md#exact-write-lifecycle) |
| `POST` | `/v1/jobs/commit_write` | `submit_commit_write` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/receipt` | `receipt` | [Contract](OPERATION-REQUESTS.md#exact-write-lifecycle) |
| `POST` | `/v1/jobs/receipt` | `submit_receipt` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/status` | `status` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/operations/cancel` | `cancel` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `POST` | `/v1/files` | `upload_file` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `GET` | `/v1/files/{handle}` | `download_file` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |
| `GET` | `/v1/info` | `service_info` | [Contract](OPERATION-REQUESTS.md#jobs-and-files) |

The running service also exposes `GET /openapi.json`; `/mcp` exists only when
enabled in trusted service configuration. HTTP service authentication uses a service
bearer token, separate from upstream provider credentials. See the integration guide
for policy, networking, files, asynchronous jobs and cancellation.

## JSON schemas

The downloadable files below are the actual packaged schema resources, not hand-written
approximations. Schemas use JSON Schema 2020-12. Preserve the original capture and unknown
upstream fields alongside projections; schema validation is not vendor acceptance.

- [bounds](api/schemas/bounds.schema.json)
- [capability](api/schemas/capability.schema.json)
- [capture](api/schemas/capture.schema.json)
- [capture-bundle](api/schemas/capture-bundle.schema.json)
- [error](api/schemas/error.schema.json)
- [identity](api/schemas/identity.schema.json)
- [query](api/schemas/query.schema.json)
- [record](api/schemas/record.schema.json)
- [result](api/schemas/result.schema.json)
- [source](api/schemas/source.schema.json)

## Regenerate

From a checkout with `.[service]` installed:

```sh
python scripts/build_api_docs.py
```

Commit the generated documents with the source change. The site build copies these
versioned downloads without starting the service or contacting any provider.
