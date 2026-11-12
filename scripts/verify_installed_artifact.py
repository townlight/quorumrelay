"""Run from a non-checkout cwd using the fresh environment's Python."""

import argparse
import hashlib
import importlib.util
from importlib import import_module
import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import civic_data_connectors
import quorumrelay
from civic_data_connectors import Source, create_engine
from civic_data_connectors.schemas import json_schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    location = Path(civic_data_connectors.__file__).resolve()
    assert "site-packages" in location.parts, "This check must run against an installed wheel."
    assert quorumrelay.Engine is civic_data_connectors.Engine
    assert quorumrelay.__version__ == civic_data_connectors.__version__
    from quorumrelay.models import Source as PublicSource
    assert PublicSource is Source
    owner = create_engine()
    providers = owner.providers().data
    assert len(providers["providers"]) == 31 and len(providers["formats"]) == 34
    assert len(owner.parsers) == 7
    assert all(importlib.util.find_spec(name) is None for name in
               ("townlight_runtime", "townlight_core", "civiccast_brief", "townrecord"))
    original = [{"EventId": 1, "EventBodyName": "Synthetic council", "EventDate": "2026-11-11T00:00:00",
                 "unknown_nested": {"zero": 0, "null": None, "false": False, "empty": ""}}]
    normalized = owner.normalize(
        Source("legistar", "https://webapi.legistar.com/v1/city"),
        json.dumps(original).encode(), input_format="legistar-events-json",
    )
    assert normalized.status == "completed" and len(normalized.data["records"]) == 1
    assert normalized.data["records"][0]["original"] == original[0]
    assert json_schema("record")["properties"]["schema_version"]["const"] == "2.0.0"
    import_module("civic_data_connectors.transports.http")
    import_module("civic_data_connectors.transports.mcp")
    with zipfile.ZipFile(options.wheel) as archive:
        names = archive.namelist()
        assert "civic_data_connectors/data/capabilities.json" in names
        assert "civic_data_connectors/data/provider-identities.json" in names
        assert "civic_data_connectors/schemas/record.schema.json" in names
        member_hashes = {name: hashlib.sha256(archive.read(name)).hexdigest()
                         for name in names if name.endswith((".py", ".json"))}
    report = {
        "schema_version": "1.0.0", "artifact": options.wheel.name,
        "sha256": hashlib.sha256(options.wheel.read_bytes()).hexdigest(),
        "library_version": civic_data_connectors.__version__, "public_package": "quorumrelay", "python_version": platform.python_version(),
        "os": platform.system(), "observed_at": datetime.now(timezone.utc).isoformat(),
        "interpreter_environment": "fresh venv, wheel[service], outside checkout cwd",
        "installed_location": str(location), "status": "PASS",
        "checks": {"providers": 31, "baseline_formats": 34, "standard_handlers": len(owner.handlers),
                   "native_parsers": len(owner.parsers), "native_normalize": "PASS",
                   "raw_unknown_fields": "PASS", "reference_imports": "absent",
                   "HTTP_MCP_module_imports": "PASS", "packaged_resources": "PASS"},
        "wheel_member_sha256": member_hashes,
        "limits": ["Development snapshot only, not final release acceptance.",
                   "HTTP/MCP imports do not prove protocol or workflow acceptance.",
                   "No live vendor writes or installed reference-consumer acceptance.",
                   "Later source fixes require a new artifact and affected reruns."],
        "command": "fresh-venv/python scripts/verify_installed_artifact.py --wheel <immutable-wheel> --output <report>",
        "exit_status": 0,
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact_sha256": report["sha256"], "status": "PASS",
                      "checks": report["checks"], "output": str(options.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
