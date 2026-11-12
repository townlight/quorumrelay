"""Publish the actual OpenAPI/schema resources as static documentation downloads."""

import json
from pathlib import Path

from quorumrelay import __version__
from quorumrelay.transports.openapi import document, schemas


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "docs" / "api"
    (target / "schemas").mkdir(parents=True, exist_ok=True)
    api = document()
    (target / "openapi.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
    definitions = schemas()
    for name, value in definitions.items():
        (target / "schemas" / f"{name}.schema.json").write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Generated API reference", "",
        f"Generated from QuorumRelay **{__version__}** source, OpenAPI **{api['openapi']}**.", "",
        "These files describe an application-hosted service. The documentation website does not",
        "operate a public provider API or accept credentials. Run your own configured service.", "",
        "[Integration guide](DEVELOPER-GUIDE.md) · [HTTP details](INTERFACES.md) · "
        "[MCP](MCP.md) · [OpenAPI JSON download](api/openapi.json)", "",
        "## HTTP endpoints", "",
        "Operation endpoints accept a shared JSON request and return the complete schema 2.0.0",
        "result envelope. Provider-specific request details and coverage remain important; the",
        "OpenAPI request object deliberately permits operation-specific fields.", "",
        "| Method | Path | Operation |", "|---|---|---|",
    ]
    for path, verbs in api["paths"].items():
        for method, value in verbs.items():
            lines.append(f"| `{method.upper()}` | `{path}` | `{value['operationId']}` |")
    lines += [
        "", "The running service also exposes `GET /openapi.json`; `/mcp` exists only when",
        "enabled in trusted service configuration. HTTP service authentication uses a service",
        "bearer token, separate from upstream provider credentials. See the integration guide",
        "for policy, networking, files, asynchronous jobs and cancellation.", "",
        "## JSON schemas", "",
        "The downloadable files below are the actual packaged schema resources, not hand-written",
        "approximations. Schemas use JSON Schema 2020-12. Preserve the original capture and unknown",
        "upstream fields alongside projections; schema validation is not vendor acceptance.", "",
    ]
    for name in sorted(definitions):
        lines.append(f"- [{name}](api/schemas/{name}.schema.json)")
    lines += [
        "", "## Regenerate", "",
        "From a checkout with `.[service]` installed:", "",
        "```sh", "python scripts/build_api_docs.py", "```", "",
        "Commit the generated documents with the source change. The site build copies these",
        "versioned downloads without starting the service or contacting any provider.", "",
    ]
    (root / "docs" / "API-REFERENCE.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated OpenAPI and {len(definitions)} schema downloads for {__version__}")


if __name__ == "__main__":
    main()
