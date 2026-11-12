# QuorumRelay

Civic records, with their source. QuorumRelay is a standalone civic-data connector engine for applications, scripts and agents. A project of [Townlight](https://github.com/townlight).

Identify configured sources, discover and retrieve records, normalize saved captures, search available information, export portable bundles, and plan explicitly authorized provider writes through one shared result contract. Python, CLI, HTTP/OpenAPI, MCP and a TypeScript HTTP client use the same engine. Your application owns its records, access policy, review and service lifecycle.

[Website](https://townlight.github.io/quorumrelay/) · [User manual](https://townlight.github.io/quorumrelay/docs/user-manual/) · [Developer guide](https://townlight.github.io/quorumrelay/docs/developer-guide/) · [Architecture](https://townlight.github.io/quorumrelay/docs/architecture/) · [API reference](https://townlight.github.io/quorumrelay/docs/api-reference/)

## Start from source

Python 3.11 or newer is required. The source checkout is the public installation path; this development candidate is not published to a package registry.

```powershell
git clone https://github.com/townlight/quorumrelay.git
cd quorumrelay
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[service]"
quorumrelay providers
```

Installing the package does not start a service or install a consumer application. Follow the [manual](docs/USER-MANUAL.md) for saved captures, bounded discovery, search, export and service configuration. The [developer guide](docs/DEVELOPER-GUIDE.md) contains runnable SDK and MCP examples, CLI/HTTP/TypeScript integration paths, authentication, large-file transfer, schemas and extension points.

## Current coverage

The current development candidate is **0.1.0.dev8**, schema **2.0.0**. It retains 31 provider families and 34 original input-format combinations, plus additive parsers. These counts describe the implemented scope, not universal operation or tenant support. Every result retains status, coverage, errors and provenance; partial results must remain visibly partial in consuming applications.

Public source and documentation are being published independently of deferred provider verification. Live provider-write acceptance, some authenticated account reads and broader catalog claims remain unverified. Synthetic tests are not relabeled as vendor acceptance. See the [capability inventory](docs/capabilities/README.md), [coverage map](docs/ENGINE-COVERAGE.md) and [execution state](docs/EXECUTION-STATE.md).

Townlight, TownReporter, CivicCast Brief and TownRecord are reference integrations. Other products can use QuorumRelay independently; none of these applications is a runtime dependency. This publication does not merge or release those projects.

## Reference and development

- [Python SDK](docs/SDK.md), [CLI/HTTP/TypeScript](docs/INTERFACES.md), [MCP stdio and HTTP](docs/MCP.md)
- [OpenAPI](docs/api/openapi.json) and [JSON schemas](docs/api/schemas/)
- [Write planning and receipts](docs/WRITE-CONTRACT.md), [provider mappings](docs/PROVIDER-NATIVE-MAPPINGS.md)
- [Examples](examples/README.md), [TypeScript client](client/README.md)
- [Contributing and checks](CONTRIBUTING.md), [site build](site/README.md)
