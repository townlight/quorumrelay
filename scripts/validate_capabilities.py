"""Validate research evidence, identities and original format coverage, never live acceptance."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/capabilities"
DATA = ROOT / "src/civic_data_connectors/data"
OPERATIONS = {
    "identify", "discover", "fetch", "parse", "native_search", "local_search",
    "neutral_export", "vendor_file_export", "create", "update", "upload",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(data, identities):
    errors = []
    rows = data["providers"]
    canonical = {row["canonical_id"] for row in rows}
    if len(canonical) != 31 or len(rows) != 31:
        errors.append("Exactly31 unique canonical provider rows required")
    if sum(len(row["baseline_formats"]) for row in rows) != 34:
        errors.append("Exactly34 baseline provider/format pairs required")
    for row in rows:
        name = row["canonical_id"]
        if row["id"] != name:
            errors.append(f"{name}: id must be canonical")
        if set(row["operations"]) != OPERATIONS:
            errors.append(f"{name}: exactly11 independent operation entries required")
        refs = [e["id"] for e in row["evidence"]]
        if len(refs) != len(set(refs)):
            errors.append(f"{name}: duplicate provider-scoped evidence IDs")
        for evidence in row["evidence"]:
            url = urlsplit(evidence["url"])
            if url.scheme not in {"https", "http"} or not url.hostname or url.username:
                errors.append(f"{name}: invalid or credentialed evidence URL")
            if any(k.lower() in {"token", "access_token", "api_key", "apikey", "secret"}
                   for k, _ in parse_qsl(url.query)):
                errors.append(f"{name}: secret-bearing evidence URL")
        for entry in [*row["operations"].values(), *row["outbound_mappings"]]:
            missing = set(entry["evidence_ids"]) - set(refs)
            if missing:
                errors.append(f"{name}: missing evidence refs {sorted(missing)}")
            if entry["acceptance_status"] != "not_run":
                errors.append(f"{name}: research snapshot must not invent acceptance")
        for mapping in row["outbound_mappings"]:
            if mapping["operation"] not in OPERATIONS:
                errors.append(f"{name}: unknown outbound operation")
            if mapping["interface_type"] == "documented_automated_api":
                if not mapping["evidence_ids"] or name not in {
                    "legistar", "laserfiche-weblink", "wistia"
                }:
                    errors.append(f"{name}: automatic API claim lacks reviewed exact product evidence")
            if mapping.get("method") == "DELETE":
                errors.append(f"{name}: deletion outside permitted domain")
        if identities["alias_to_canonical"].get(name) != name:
            errors.append(f"{name}: canonical ID lookup absent")
        expected = next((p for p in identities["providers"] if p["canonical_id"] == name), None)
        if expected is None or row["aliases"] != expected["aliases"]:
            errors.append(f"{name}: aliases disagree with public identity definition")
        for alias in row["aliases"]:
            if identities["alias_to_canonical"].get(alias) != name or alias in canonical:
                errors.append(f"{name}: alias missing, ambiguous or collides with canonical ID")
    for alias, name in identities["alias_to_canonical"].items():
        row = next((p for p in rows if p["canonical_id"] == name), None)
        if row is None or not row["operations"]:
            errors.append(f"{alias}: empty/missing capability row after exact alias resolution")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-source", type=Path)
    args = parser.parse_args()
    inventory, runtime = load(DOCS / "inventory.json"), load(DATA / "capabilities.json")
    schema = load(DOCS / "inventory.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    identities = load(DOCS / "provider-identities.json")
    errors = []
    for label, data in [("inventory", inventory), ("runtime", runtime)]:
        errors.extend(f"{label}: {error.json_path}: {error.message}"
                      for error in validator.iter_errors(data))
        errors.extend(f"{label}: {error}" for error in semantic_errors(data, identities))
    if identities != load(DATA / "provider-identities.json"):
        errors.append("Packaged identity definition differs from documentation source")
    if runtime["source_sha256"] != hashlib.sha256((DOCS / "inventory.json").read_bytes()).hexdigest():
        errors.append("Packaged capability research snapshot is stale")
    documented = {(p["id"], fmt) for p in inventory["providers"] for fmt in p["baseline_formats"]}
    contracts = load(DOCS / "baseline-field-contracts.json")["contracts"]
    if {(p["provider"], p["format"]) for p in contracts} != documented or len(contracts) != 34:
        errors.append("Exact34 baseline source mapping contracts differ from inventory")
    original_checked = False
    if args.baseline_source:
        source = ast.parse(args.baseline_source.read_text(encoding="utf-8"))
        assignment = next(n for n in source.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "SOURCE_FORMATS"
                                  for t in n.targets))
        originals = ast.literal_eval(assignment.value)
        if len(originals) != 34 or {(p, fmt) for p, fmt, _ in originals} != documented:
            errors.append("Inventory differs from independently pinned original SOURCE_FORMATS")
        original_checked = True
    api = load(DOCS / "provider-api-contracts.json")
    for entry in api["legistar"]:
        if not entry["model_fields"] or any("\n" in fmt for fmt in entry["request_formats"]):
            errors.append(f"Invalid extracted exact Legistar schema {entry['method_path']}")
    if len(api["legistar"]) != 12 or len(api["wistia"]) != 8 or len(api["laserfiche"]) != 7:
        errors.append("Official API contract extraction count changed without review")
    negative = 0
    invalid = deepcopy(inventory)
    invalid["providers"][0]["operations"] = {}
    if not list(validator.iter_errors(invalid)):
        errors.append("Negative schema check failed to reject missing operation statuses")
    else:
        negative += 1
    invalid = deepcopy(inventory)
    invalid["providers"][0]["operations"]["create"]["acceptance_status"] = "live_write_passed"
    if not semantic_errors(invalid, identities):
        errors.append("Negative check failed to reject invented live acceptance")
    else:
        negative += 1
    invalid = deepcopy(inventory)
    invalid["providers"][0]["id"] = "unknown-provider"
    if not semantic_errors(invalid, identities):
        errors.append("Negative check failed to reject noncanonical provider ID")
    else:
        negative += 1
    report = {
        "status": "FAILED" if errors else "PASSED",
        "scope": "Research schema/references/identities/format validation, not engine/provider acceptance",
        "providers": len(inventory["providers"]),
        "baseline_formats": len(documented),
        "operation_entries": sum(len(p["operations"]) for p in inventory["providers"]),
        "outbound_mapping_entries": sum(len(p["outbound_mappings"]) for p in inventory["providers"]),
        "interface_types": dict(Counter(m["interface_type"] for p in inventory["providers"]
                                        for m in p["outbound_mappings"])),
        "evidence_records": sum(len(p["evidence"]) for p in inventory["providers"]),
        "distinct_evidence_urls": len({e["url"] for p in inventory["providers"] for e in p["evidence"]}),
        "exact_identity_lookups": len(identities["alias_to_canonical"]),
        "original_SOURCE_FORMATS_independently_checked": original_checked,
        "negative_checks_passed": negative,
        "errors": errors,
        "live_provider_acceptance": "NOT_RUN, user authorized mocks only",
        "engine_status_reconciliation": "Owned independently by engine implementation owners",
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
