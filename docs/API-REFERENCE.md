# Generated API reference

Generated from QuorumRelay **0.1.0.dev8** source, OpenAPI **3.1.0**.

These files describe an application-hosted service. The documentation website does not
operate a public provider API or accept credentials. Run your own configured service.

[Integration guide](DEVELOPER-GUIDE.md) · [HTTP details](INTERFACES.md) · [MCP](MCP.md) · [OpenAPI JSON download](api/openapi.json)

## HTTP endpoints

Operation endpoints accept a shared JSON request and return the complete schema 2.0.0
result envelope. Provider-specific request details and coverage remain important; the
OpenAPI request object deliberately permits operation-specific fields.

| Method | Path | Operation |
|---|---|---|
| `POST` | `/v1/operations/providers` | `providers` |
| `POST` | `/v1/jobs/providers` | `submit_providers` |
| `POST` | `/v1/operations/capabilities` | `capabilities` |
| `POST` | `/v1/jobs/capabilities` | `submit_capabilities` |
| `POST` | `/v1/operations/identify` | `identify` |
| `POST` | `/v1/jobs/identify` | `submit_identify` |
| `POST` | `/v1/operations/validate_source` | `validate_source` |
| `POST` | `/v1/jobs/validate_source` | `submit_validate_source` |
| `POST` | `/v1/operations/discover` | `discover` |
| `POST` | `/v1/jobs/discover` | `submit_discover` |
| `POST` | `/v1/operations/fetch` | `fetch` |
| `POST` | `/v1/jobs/fetch` | `submit_fetch` |
| `POST` | `/v1/operations/normalize` | `normalize` |
| `POST` | `/v1/jobs/normalize` | `submit_normalize` |
| `POST` | `/v1/operations/search` | `search` |
| `POST` | `/v1/jobs/search` | `submit_search` |
| `POST` | `/v1/operations/import_preview` | `import_preview` |
| `POST` | `/v1/jobs/import_preview` | `submit_import_preview` |
| `POST` | `/v1/operations/import_bundle` | `import_bundle` |
| `POST` | `/v1/jobs/import_bundle` | `submit_import_bundle` |
| `POST` | `/v1/operations/export` | `export` |
| `POST` | `/v1/jobs/export` | `submit_export` |
| `POST` | `/v1/operations/plan_write` | `plan_write` |
| `POST` | `/v1/jobs/plan_write` | `submit_plan_write` |
| `POST` | `/v1/operations/commit_write` | `commit_write` |
| `POST` | `/v1/jobs/commit_write` | `submit_commit_write` |
| `POST` | `/v1/operations/receipt` | `receipt` |
| `POST` | `/v1/jobs/receipt` | `submit_receipt` |
| `POST` | `/v1/operations/status` | `status` |
| `POST` | `/v1/operations/cancel` | `cancel` |
| `POST` | `/v1/files` | `upload_file` |
| `GET` | `/v1/files/{handle}` | `download_file` |
| `GET` | `/v1/info` | `service_info` |

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
