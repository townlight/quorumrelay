# QuorumRelay

The integrated development source is Python **0.1.0.dev13** / TypeScript **0.1.0-dev.13**. It adds approved CivicWeb/Cablecast readers, an opt-in BoardDocs public listing/detail path and CivicClerk Select detail/files and section writes: 32 registered providers, 31 baseline families, 34 baseline formats, 47 additive parser hooks and 17 native-search handlers. The matching local wheel and TypeScript tarball are built but unpublished; no Windows release is claimed. See [local preparation evidence](docs/verification/local-completion-2026-11-14.json).

Preserved package baseline: Python **0.1.0.dev11**, TypeScript **0.1.0-dev.11**, schema **2.0.0**. Those immutable packages precede the integrated reader fixes. The frozen dev8 artifacts remain historical evidence.

Civic records, with their source. QuorumRelay is a standalone civic-data connector engine for applications, scripts and agents. A project of [Townlight](https://github.com/townlight).

Identify configured sources, discover and retrieve records, normalize saved captures, search available information, export portable bundles, and plan explicitly authorized provider writes through one shared result contract. Python, CLI, HTTP/OpenAPI, MCP and a TypeScript HTTP client use the same engine. Your application owns its records, access policy, review and service lifecycle.

[Website](https://townlight.github.io/quorumrelay/) Â· [User manual](https://townlight.github.io/quorumrelay/docs/user-manual/) Â· [Developer guide](https://townlight.github.io/quorumrelay/docs/developer-guide/) Â· [Architecture](https://townlight.github.io/quorumrelay/docs/architecture/) Â· [API reference](https://townlight.github.io/quorumrelay/docs/api-reference/)

## Start from source

Python 3.11 or newer is required. The public repository supplies the published preview; remote main does not yet contain this local integration. These clone commands install that public preview. To evaluate the integrated source, use the approved local checkout and run the same venv/install commands there. No package-index release is claimed.

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

The integrated source reports version **0.1.0.dev13**, schema **2.0.0**. Its locally built Python wheel and TypeScript tarball remain unpublished. It retains 31 baseline provider families and 34 original input-format combinations, adds Cablecast as a typed connector, and registers 47 additive parser hooks and 17 native-search handlers. These counts describe the implemented source scope, not universal operation or tenant support. Every result retains status, coverage, errors and provenance; partial results must remain visibly partial in consuming applications.

The public dev8 source/documentation publication is separate from later local source additions, which are listed in the [developer mapping guides](docs/DEVELOPER-GUIDE.md#later-local-source-mapping-guides). Those additions do not change the immutable dev8 wheel or its installed-consumer evidence. Vendor-documented synthetic execution is accepted verification for the provider operations and fields it covers; it is not a claim of actual tenant transactions. Live provider writes, some authenticated account reads and broader catalog claims remain unobserved or incomplete as stated. See the [capability inventory](docs/capabilities/README.md), [coverage map](docs/ENGINE-COVERAGE.md) and [execution state](docs/EXECUTION-STATE.md).

Townlight, TownReporter, CivicCast Brief and TownRecord are reference integrations. Other products can use QuorumRelay independently; none of these applications is a runtime dependency. This publication does not merge or release those projects.

## Reference and development

- [Python SDK](docs/SDK.md), [CLI/HTTP/TypeScript](docs/INTERFACES.md), [MCP stdio and HTTP](docs/MCP.md)
- [OpenAPI](docs/api/openapi.json) and [JSON schemas](docs/api/schemas/)
- [Write planning and receipts](docs/WRITE-CONTRACT.md), [provider mappings](docs/PROVIDER-NATIVE-MAPPINGS.md), [BoardDocs public reader](docs/BOARDDOCS-PUBLIC.md), [CivicClerk Select reads/writes](docs/CIVICCLERK-SELECT.md)
- [Examples](examples/README.md), [TypeScript client](client/README.md)
- [Contributing and checks](CONTRIBUTING.md), [site build](site/README.md)
