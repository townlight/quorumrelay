# QuorumRelay

Python **0.1.0.dev15**, TypeScript **0.1.0-dev.15**, schema **2.0.0**. [Release packages and checksums](https://github.com/townlight/quorumrelay/releases/tag/v0.1.0.dev15).

Civic records, with their source. QuorumRelay is a standalone civic-data connector engine for applications, scripts and agents. A project of [Townlight](https://github.com/townlight).

Identify configured sources, discover and retrieve records, normalize saved captures, search available information, export portable bundles, and plan explicitly authorized provider writes through one shared result contract. Python, CLI, HTTP/OpenAPI, MCP and a TypeScript HTTP client use the same engine. Your application owns its records, access policy, review and service lifecycle.

[Website](https://townlight.github.io/quorumrelay/) · [User manual](https://townlight.github.io/quorumrelay/docs/user-manual/) · [Developer guide](https://townlight.github.io/quorumrelay/docs/developer-guide/) · [Architecture](https://townlight.github.io/quorumrelay/docs/architecture/) · [API reference](https://townlight.github.io/quorumrelay/docs/api-reference/)

## Start with the published package

Download the [dev15 Python wheel](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/quorumrelay-0.1.0.dev15-py3-none-any.whl) and [checksums](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/SHA256SUMS). Use Python 3.11+ in an activated virtual environment and verify the wheel hash before installing.

~~~sh
python -m pip install ./quorumrelay-0.1.0.dev15-py3-none-any.whl
quorumrelay providers
~~~

The [quickstart](docs/QUICKSTART.md) walks through one offline saved meeting. Install the wheel with `[service]` for [HTTP setup and exact request paths](docs/API-REFERENCE.md) or [MCP stdio and Streamable HTTP](docs/MCP.md). Node and TypeScript consumers can install the [published client tarball](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/quorumrelay-client-0.1.0-dev.15.tgz) and connect to a separately configured service.

## Current coverage

The engine registers 33 providers, 34 baseline formats, 74 additional parsers and 23 native search handlers. All 31 original families have readers. Twelve families have active upstream write mappings, 20 are read-only, and TownCloud write work remains parked with its existing draft-text adapter. Cablecast and Diligent Community are the additional readers. See [provider coverage by operation](docs/PROVIDER-COVERAGE.md) to check a specific integration.

Townlight, TownReporter, CivicCast Brief and TownRecord are reference integrations. Other products can use QuorumRelay independently; none of these applications is a runtime dependency. This publication does not merge or release those projects.

This preview fixes [TownCloud public agenda, minutes and packet downloads](docs/TOWNCLOUD-AGENDA.md) from both published listing formats and adds [gWorks production draft title, location and schedule updates](docs/GWORKS-EDITOR.md#production-one-unpublished-meeting-title-location-or-schedule), one field at a time. Further TownCloud writes stay parked. The release also improves [Wistia swap readback](docs/WISTIA-SWAP.md) when the provider supplies comparable original-file metadata.

## Reference and development

- [Python SDK](docs/SDK.md), [CLI/HTTP/TypeScript](docs/INTERFACES.md), [MCP stdio and HTTP](docs/MCP.md)
- [Operation requests and responses](docs/OPERATION-REQUESTS.md), [OpenAPI](docs/api/openapi.json) and [JSON schemas](docs/api/schemas/)
- [Write planning and receipts](docs/WRITE-CONTRACT.md), [provider mappings](docs/PROVIDER-NATIVE-MAPPINGS.md), [BoardDocs public reader](docs/BOARDDOCS-PUBLIC.md), [CivicClerk Select reads/writes](docs/CIVICCLERK-SELECT.md)
- [Examples](examples/README.md), [TypeScript client](client/README.md)
- [Contributing and checks](CONTRIBUTING.md), [site build](site/README.md)

## License

Current Townlight-owned source is licensed under AGPL-3.0-only; see [LICENSE](LICENSE). Dependencies retain their own licenses. This declaration does not replace or alter historical published artifacts.
