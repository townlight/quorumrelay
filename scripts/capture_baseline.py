"""Copy the pinned original corpus and generate independent original-output hashes.

Run explicitly with original repository and matrix paths. Never imports the new readers.
"""

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "baseline"
    output.mkdir(parents=True, exist_ok=True)
    core = load("original_normalization", args.repos / "core/townlight_core/connectors/imports.py")
    parent = types.ModuleType("townlight_core")
    parent.__path__ = []
    namespace = types.ModuleType("townlight_core.connectors")
    namespace.ConnectorImportError = core.ConnectorImportError
    namespace.import_meeting_payload = core.import_meeting_payload
    sys.modules["townlight_core"] = parent
    sys.modules["townlight_core.connectors"] = namespace
    original = load("original_meeting_readers", args.repos /
                    "townlight/desktop/runtime/python-services/townlight_runtime/meeting_imports.py")
    cases = json.loads((args.matrix / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        source = args.matrix / case["file"]
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == case["sha256"]
        result = original.preview_export(case["connector"], case["source_url"], content,
                                         input_format=case["input_format"])
        canonical = json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True,
                               separators=(",", ":")).encode()
        case["original_output_sha256"] = hashlib.sha256(canonical).hexdigest()
        case["original_record_count"] = len(result["meetings"])
        case["original_namespace"] = result["source"]["namespace"]
        shutil.copyfile(source, output / case["file"])
        print(json.dumps({"provider": case["connector"], "format": case["input_format"],
                          "records": len(result["meetings"]), "passed": True}), flush=True)
    (output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"Captured {len(cases)} independently computed original compatibility hashes.")


if __name__ == "__main__":
    main()
