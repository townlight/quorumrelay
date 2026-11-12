# QuorumRelay

Independent civic-data connectors for applications, scripts and agents. A project
of [Townlight](https://github.com/townlight).

QuorumRelay identifies configured civic sources, discovers and retrieves records,
normalizes saved captures, searches captured information, exports interchange
bundles, and plans explicitly authorized provider writes. Python, CLI, HTTP/OpenAPI,
MCP and a TypeScript HTTP client use the same engine and result contract.

## Development status

The current candidate is **0.1.0.dev3**. It is not a completed first release.
All 31 source families and 34 original input-format combinations remain in scope,
along with every interface and all four reference integrations. Provider research,
implemented behavior, fixture tests, live reads, authorized write acceptance and
installed consumer acceptance are separate evidence levels.

Provider test credentials and authorized writable environments are outstanding.
Mocked writes do not satisfy live write acceptance. Consult the
[capability inventory](docs/capabilities/README.md) and
[execution state](docs/EXECUTION-STATE.md) for remaining work. Missing access is not
evidence that a provider lacks an operation.

## Use the candidate

Python 3.11 or later is required. From a source checkout:

```powershell
python -m pip install -e ".[service]"
quorumrelay providers
```

For a built candidate, install its explicit wheel path and verify its recorded
hash. Package-index publication has not yet occurred. Installing QuorumRelay
does not install Townlight or start a service.

```python
from quorumrelay import Source, create_engine

engine = create_engine()
source = Source("legistar", "https://example.org", input_format="meeting-export")
# saved_capture contains bytes in the documented provider format.
result = engine.normalize(source, saved_capture, input_format=source.input_format)
print(result.public_dict())  # Retain status, coverage, errors and provenance.
```

For an explicitly configured local service:

```powershell
quorumrelay serve --config C:\app\connector-service.json --database C:\app\captures.sqlite
```

The application owns configuration, credentials, service lifecycle and storage.
Loopback is the default; network deployment requires explicit authentication and
host policy. Upstream provider credentials are separate from service credentials.
Imports never publish a story or implicitly mutate provider data.

The TypeScript package is `quorumrelay-client`; install a locally packed tarball
until it is published. Its `QuorumRelayClient` requires an explicit service URL.
Earlier `civic_data_connectors` Python imports and `CivicConnectorClient` remain
compatibility aliases to the same implementation.

## Documentation

- [Full bounded implementation plan and acceptance](docs/IMPLEMENTATION-PLAN.md)
- [Python SDK](docs/SDK.md), [engine and storage contract](docs/ENGINE-CONTRACT.md)
- [CLI, HTTP, file transfer and TypeScript](docs/INTERFACES.md)
- [MCP stdio and Streamable HTTP](docs/MCP.md)
- [Write planning, authorization, receipts and recovery](docs/WRITE-CONTRACT.md)
- [Provider capability evidence](docs/capabilities/README.md)
- [Native source mappings and legacy identities](docs/PROVIDER-NATIVE-MAPPINGS.md)
- [Examples](examples/README.md), [TypeScript client](client/README.md)
- [Pinned source baseline](docs/SOURCE-BASELINE.md)

Townlight, TownReporter, CivicCast Brief and TownRecord are the four required
reference integrations. Other applications can use QuorumRelay independently.
Sharing the Townlight organization does not make its municipal suite a dependency.

## Development checks

```powershell
python -m pip install -e ".[service,test]"
npm --prefix client ci
npm --prefix client run build
python -X utf8 -m pytest tests -q
python -m ruff check src tests scripts examples
npm --prefix client test
```

The automated suite uses isolated synthetic inputs and retained public captures.
It does not replace installed-product checks or authorized vendor test-tenant
readback. Historical artifact receipts identify only the exact artifacts tested.
