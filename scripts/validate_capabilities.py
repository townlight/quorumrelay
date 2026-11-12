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
LIVE_READ_RECEIPTS = {
    "legistar": {
        "operation": "fetch",
        "receipt_evidence_id": "legistar-event-detail-live",
        "receipt_path": "docs/verification/legistar-detail-2026-11-11.json",
        "required_capture_ids": {"legistar-event-detail-live"},
    },
    "champ": {
        "operation": "fetch",
        "receipt_evidence_id": "champ-live-engine-detail-receipt",
        "receipt_path": "docs/verification/champ-detail-2026-11-11.json",
        "required_capture_ids": {
            "champ-public-player-js", "champ-lakezurich-event-json", "champ-yuma-event-json"
        },
    },
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _within_root(relative_path):
    path = (ROOT / relative_path).resolve()
    return path if ROOT.resolve() in path.parents else None


def _live_read_receipt_errors(provider, operation, entry, evidence_by_id):
    errors = []
    rule = LIVE_READ_RECEIPTS.get(provider)
    if rule is None or operation != rule["operation"]:
        return [f"{provider}: live_read_passed is not allowed for {operation}"]
    receipt_evidence = evidence_by_id.get(rule["receipt_evidence_id"])
    if receipt_evidence is None or receipt_evidence.get("proof_level") != \
            "live_engine_bounded_read_receipt_not_write_acceptance":
        return [f"{provider}: live_read_passed lacks its exact bounded-read receipt evidence"]
    if not rule["required_capture_ids"].issubset(entry["evidence_ids"]):
        errors.append(f"{provider}: live_read_passed lacks the required captured source evidence")
    receipt_path = receipt_evidence.get("receipt_path")
    if receipt_path != rule["receipt_path"]:
        return errors + [f"{provider}: bounded-read receipt path is not the pinned receipt"]
    path = _within_root(receipt_path)
    if path is None or not path.is_file():
        return errors + [f"{provider}: bounded-read receipt is missing or escapes the repository"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt_evidence.get("receipt_sha256"):
        errors.append(f"{provider}: bounded-read receipt hash does not match inventory evidence")
    try:
        receipt = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return errors + [f"{provider}: bounded-read receipt is not valid JSON"]

    if receipt.get("operation") != "fetch_record":
        errors.append(f"{provider}: receipt is not a fetch_record operation")
    if provider == "legistar":
        coverage = receipt.get("coverage", {})
        if (receipt.get("status") != "completed" or receipt.get("errors") != []
                or receipt.get("remote_writes") != "NOT_PERFORMED"
                or receipt.get("source", {}).get("provider") != provider
                or receipt.get("external_id") != "7011"
                or coverage.get("catalog_complete") is not False
                or coverage.get("returned_records") != 1
                or coverage.get("failures") != []
                or receipt.get("original_fields_preserved") is not True):
            errors.append("legistar: receipt does not prove the exact bounded public detail read")
        capture = evidence_by_id.get("legistar-event-detail-live", {})
        if capture.get("url") != "https://webapi.legistar.com/v1/olympia/events/7011?EventItems=1&AgendaNote=1&MinutesNote=1&EventItemAttachments=1":
            errors.append("legistar: receipt evidence URL differs from the captured detail route")
        _validate_capture_file("legistar", capture, receipt.get("fixture"),
                               receipt.get("sha256"), errors)
    elif provider == "champ":
        rows = receipt.get("results", [])
        if (len(rows) != 2
                or receipt.get("operation") != "fetch_record"
                or receipt.get("policy") != "bounded public GET only; no writes, credentials or attachment downloads"):
            errors.append("champ: receipt must contain the two pinned bounded tenant reads")
        expected = {
            "champ-lakezurich-event-json": (
                "164", "https://play.champds.com/lakezurichil/event/164",
                "https://playapi.champds.com/lakezurichil/event/164",
            ),
            "champ-yuma-event-json": (
                "657", "https://play.champds.com/yumacoaz/event/657",
                "https://playapi.champds.com/yumacoaz/event/657",
            ),
        }
        by_id = {row.get("external_id"): row for row in rows}
        for evidence_id, (event_id, receipt_url, evidence_url) in expected.items():
            evidence = evidence_by_id.get(evidence_id, {})
            row = by_id.get(event_id)
            if row is None or evidence.get("url") != evidence_url:
                errors.append(f"champ: receipt is missing captured source {evidence_id}")
                continue
            coverage = row.get("coverage", {})
            if (row.get("status") != "completed" or row.get("errors") != []
                    or row.get("external_id") != event_id
                    or row.get("source_url") != receipt_url
                    or coverage.get("catalog_complete") is not False
                    or coverage.get("returned_records") != 1
                    or row.get("original_fields_preserved") is not True):
                errors.append(f"champ: receipt row {evidence_id} does not prove a bounded detail read")
            if (not isinstance(row.get("capture_sha256"), str)
                    or len(row["capture_sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in row["capture_sha256"])
                    or not isinstance(row.get("byte_length"), int)
                    or row["byte_length"] <= 0):
                errors.append(f"champ: receipt row {evidence_id} lacks a valid response digest/length")
            _validate_capture_file("champ", evidence, None, None, errors)
    return errors


def _validate_capture_file(provider, evidence, receipt_fixture, receipt_sha256, errors):
    fixture = evidence.get("fixture_path")
    expected_hash = evidence.get("fixture_sha256")
    if not fixture or (receipt_fixture and fixture != Path(receipt_fixture).as_posix()):
        errors.append(f"{provider}: receipt does not identify the pinned original capture fixture")
        return
    path = _within_root(fixture)
    if path is None or not path.is_file():
        errors.append(f"{provider}: original capture fixture is missing or escapes the repository")
        return
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != expected_hash or (receipt_sha256 and actual_hash != receipt_sha256):
        errors.append(f"{provider}: capture fixture hash differs from the receipt/inventory")


def semantic_errors(data, identities):
    errors = []
    status_model = data.get("status_model", {})
    status_fields = ("capability_status", "implementation_status", "acceptance_status")
    declared_statuses = {}
    for field in status_fields:
        values = status_model.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            errors.append(f"status_model.{field} must declare a list of string labels")
            declared_statuses[field] = set()
        else:
            declared_statuses[field] = set(values)
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
        evidence_by_id = {e["id"]: e for e in row["evidence"]}
        if len(refs) != len(set(refs)):
            errors.append(f"{name}: duplicate provider-scoped evidence IDs")
        for evidence in row["evidence"]:
            url = urlsplit(evidence["url"])
            if url.scheme not in {"https", "http"} or not url.hostname or url.username:
                errors.append(f"{name}: invalid or credentialed evidence URL")
            if any(k.lower() in {"token", "access_token", "api_key", "apikey", "secret"}
                   for k, _ in parse_qsl(url.query)):
                errors.append(f"{name}: secret-bearing evidence URL")
        for operation, entry in row["operations"].items():
            for field in status_fields:
                if entry.get(field) not in declared_statuses[field]:
                    errors.append(
                        f"{name}.{operation}: {field} label {entry.get(field)!r} "
                        f"is not declared by status_model.{field}"
                    )
            missing = set(entry["evidence_ids"]) - set(refs)
            if missing:
                errors.append(f"{name}: missing evidence refs {sorted(missing)}")
            status = entry["acceptance_status"]
            if status == "live_read_passed":
                errors.extend(_live_read_receipt_errors(name, operation, entry,
                                                        evidence_by_id))
            elif status != "not_run":
                errors.append(f"{name}: research snapshot cannot claim provider write acceptance")
        for entry in row["outbound_mappings"]:
            missing = set(entry["evidence_ids"]) - set(refs)
            if missing:
                errors.append(f"{name}: missing evidence refs {sorted(missing)}")
            if entry["acceptance_status"] != "not_run":
                errors.append(f"{name}: outbound mapping cannot claim provider acceptance")
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
    if len(api["legistar"]) != 16 or len(api["wistia"]) != 12 or len(api["laserfiche"]) != 7:
        errors.append("Official API contract extraction count changed without review")
    negative = 0
    invalid = deepcopy(inventory)
    invalid["providers"][0]["operations"] = {}
    if not list(validator.iter_errors(invalid)):
        errors.append("Negative schema check failed to reject missing operation statuses")
    else:
        negative += 1
    invalid = deepcopy(inventory)
    invalid["status_model"]["implementation_status"].remove("implemented")
    undeclared_status_errors = semantic_errors(invalid, identities)
    if not any(
        "implementation_status label 'implemented' is not declared by status_model.implementation_status"
        in error
        for error in undeclared_status_errors
    ):
        errors.append("Negative check failed to reject an undeclared implementation status")
    else:
        negative += 1
    invalid = deepcopy(inventory)
    invalid["providers"][0]["operations"]["create"]["acceptance_status"] = "live_write_passed"
    if not semantic_errors(invalid, identities):
        errors.append("Negative check failed to reject invented live acceptance")
    else:
        negative += 1
    invalid = deepcopy(inventory)
    invalid["providers"][1]["operations"]["fetch"]["acceptance_status"] = "live_read_passed"
    if not semantic_errors(invalid, identities):
        errors.append("Negative check failed to reject unreceipted live read acceptance")
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
        "live_provider_acceptance": (
            "Three bounded receipt files document five public engine read calls: one Legistar event "
            "detail, two CHAMP event details, and first/resumed Granicus Superior Clip searches. "
            "This validator checks the Legistar and CHAMP receipt/capture relationships; the distinct "
            "Granicus receipt and page-fixture hashes are recorded separately and are not cross-compared. "
            "None proves catalog completeness. Provider write acceptance is NOT_RUN because no authorized "
            "provider test tenants or credentials were supplied."
        ),
        "engine_status_reconciliation": "Owned independently by engine implementation owners",
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
