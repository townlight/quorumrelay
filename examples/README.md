# Independent executable examples

Install the standalone wheel with its service extra. No reference product,
application database, model provider, hosted service, or real vendor write
account is needed. Use a new, isolated writable folder for state files.
These examples use synthetic data, not live provider acceptance.

## Python, in process

```powershell
python C:\connectors\examples\mock_workflow.py python --database C:\demo\python.sqlite
```

Runs discover, preview, explicit persistence, search, streamed ZIP export and
real-adapter mocked plan/commit/readback/receipt.

## CLI and HTTP/JSON

`cli-workflow.ps1` drives installed CLI processes using stdin JSON and an
explicit database. `http-workflow.ps1` sends the same requests over HTTP.
The scripts use saved synthetic provider-format data, preserve partial coverage,
and never configure a live mutation transport.

```powershell
pwsh -File C:\connectors\examples\cli-workflow.ps1 -Database C:\demo\cli.sqlite
python C:\connectors\examples\mock_workflow.py serve --database C:\demo\service.sqlite
# Separate terminal:
$env:CIVIC_CONNECTOR_URL = 'http://127.0.0.1:8765'
$env:CIVIC_CONNECTOR_TOKEN = 'synthetic-demo-token-never-for-deployment'
pwsh -File C:\connectors\examples\http-workflow.ps1
```

The operator owns the service process and stops it with Ctrl+C. The mock
upstream exists only in this executable example. Its durable receipts/captures
are SQLite-backed, but its simulated provider state is process-local.
Do not use this fixture as evidence of cross-restart upstream persistence.

## Unrelated fifth Node client

From `client/`, run `npm install`, `npm run build`, and `npm pack`.
In a new unrelated directory, install the generated `.tgz`; copy only
`fifth-client.mjs` there. With the explicit URL/token above:

```powershell
npm install C:\connectors\client\quorumrelay-client-0.1.0-dev.2.tgz
node C:\unrelated\fifth-client.mjs
```

The client verifies the service version and runs saved discovery, import,
search and a real streamed ZIP download. It neither starts a service nor
assumes a reference application's filesystem layout.

## Both MCP transports and eras

```powershell
python C:\connectors\examples\mcp-client.py stdio --database C:\demo\stdio.sqlite
python C:\connectors\examples\mcp-client.py stdio --mode legacy --database C:\demo\legacy.sqlite
# Against the separately started mock HTTP service:
python C:\connectors\examples\mcp-client.py http --url http://127.0.0.1:8765
python C:\connectors\examples\mcp-client.py http --mode legacy --url http://127.0.0.1:8765
```

The official SDK clients negotiate 2026-07-28 (modern) or 2025-11-25 (legacy).
They also read a chunked export resource and exercise exact mock write approval.
The example checks `plan.mock` before commit and refuses a non-mock plan.
