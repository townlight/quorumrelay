# QuorumRelay

Python **0.1.0.dev14**, TypeScript **0.1.0-dev.14**, schema **2.0.0**. [Release packages and checksums](https://github.com/townlight/quorumrelay/releases/tag/v0.1.0.dev14).

Civic records, with their source. QuorumRelay is a standalone civic-data connector engine for applications, scripts and agents. A project of [Townlight](https://github.com/townlight).

Identify configured sources, discover and retrieve records, normalize saved captures, search available information, export portable bundles, and plan explicitly authorized provider writes through one shared result contract. Python, CLI, HTTP/OpenAPI, MCP and a TypeScript HTTP client use the same engine. Your application owns its records, access policy, review and service lifecycle.

[Website](https://townlight.github.io/quorumrelay/) · [User manual](https://townlight.github.io/quorumrelay/docs/user-manual/) · [Developer guide](https://townlight.github.io/quorumrelay/docs/developer-guide/) · [Architecture](https://townlight.github.io/quorumrelay/docs/architecture/) · [API reference](https://townlight.github.io/quorumrelay/docs/api-reference/)

## Start from source

Python 3.11 or newer is required. Clone the release tag or download the wheel from GitHub Releases.

```powershell
git clone --branch v0.1.0.dev14 https://github.com/townlight/quorumrelay.git
cd quorumrelay
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[service]"
quorumrelay providers
```

Installing the package does not start a service or install a consumer application. Follow the [manual](docs/USER-MANUAL.md) for saved captures, bounded discovery, search, export and service configuration. The [developer guide](docs/DEVELOPER-GUIDE.md) contains runnable SDK and MCP examples, CLI/HTTP/TypeScript integration paths, authentication, large-file transfer, schemas and extension points.

## Current coverage

The engine registers 33 providers, 34 baseline formats, 74 additional parsers and 23 native search handlers. All 31 original families have readers. Twelve active families support selected upstream writes, 18 are read-only, and TownCloud remains parked with its existing draft-text adapter. Cablecast and Diligent Community are additional readers. See the [provider delivery scope](docs/DELIVERY-SCOPE.md) for exact operations and deployment limits.

Townlight, TownReporter, CivicCast Brief and TownRecord are reference integrations. Other products can use QuorumRelay independently; none of these applications is a runtime dependency. This publication does not merge or release those projects.

## Reference and development

- [Python SDK](docs/SDK.md), [CLI/HTTP/TypeScript](docs/INTERFACES.md), [MCP stdio and HTTP](docs/MCP.md)
- [OpenAPI](docs/api/openapi.json) and [JSON schemas](docs/api/schemas/)
- [Write planning and receipts](docs/WRITE-CONTRACT.md), [provider mappings](docs/PROVIDER-NATIVE-MAPPINGS.md), [BoardDocs public reader](docs/BOARDDOCS-PUBLIC.md), [CivicClerk Select reads/writes](docs/CIVICCLERK-SELECT.md)
- [Examples](examples/README.md), [TypeScript client](client/README.md)
- [Contributing and checks](CONTRIBUTING.md), [site build](site/README.md)
