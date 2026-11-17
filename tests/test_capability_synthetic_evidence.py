"""Synthetic capability labels need executed, scoped, byte-bound evidence."""
import hashlib
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("capability_validator", Path(__file__).parents[1] / "scripts/validate_capabilities.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    bindings = []
    for kind, name in [("vendor_contract", "docs/vendor.md"), ("test", "tests/test_route.py")]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic validator fixture, not an execution receipt")
        bindings.append({"kind": kind, "path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    proof = {"provider": "wistia", "status": "mock_passed", "operations": ["update"],
        "entities": ["recording_replacement"], "scope": "one approved swap",
        "execution_provenance": "Recorded local synthetic fixture execution, no live claim",
        "checks": [{"command": "pytest tests/test_route.py -q", "passed": 1, "failed": 0}], "bindings": bindings}
    refs = {"synthetic": {"proof_level": "vendor_contract_and_synthetic_engine_execution", "synthetic_execution": proof}}
    entry = {"entity": "recording_replacement", "implementation_status": "implemented",
             "acceptance_status": "mock_passed", "evidence_ids": ["synthetic"]}
    return entry, refs


@pytest.mark.parametrize("status", ["mock_passed", "fixture_passed"])
def test_explicit_scoped_synthetic_status_with_pinned_evidence(evidence, status):
    entry, refs = evidence
    entry["acceptance_status"] = status
    refs["synthetic"]["synthetic_execution"]["status"] = status
    assert validator._synthetic_errors("wistia", "update", entry, refs) == []


@pytest.mark.parametrize("problem", ["missing", "wrong_provider", "wrong_operation", "wrong_entity",
    "wrong_hash", "missing_contract", "escaping_path", "failed_check", "not_executed", "not_implemented"])
def test_unattributed_or_invalid_synthetic_status_is_rejected(evidence, problem):
    entry, refs = evidence
    proof = refs["synthetic"]["synthetic_execution"]
    if problem == "missing":
        refs.clear()
    elif problem == "wrong_provider":
        proof["provider"] = "legistar"
    elif problem == "wrong_operation":
        proof["operations"] = ["create"]
    elif problem == "wrong_entity":
        proof["entities"] = ["supplied_caption"]
    elif problem == "wrong_hash":
        proof["bindings"][0]["sha256"] = "0" * 64
    elif problem == "missing_contract":
        proof["bindings"] = proof["bindings"][1:]
    elif problem == "escaping_path":
        proof["bindings"][0]["path"] = "../outside.md"
    elif problem == "failed_check":
        proof["checks"][0]["failed"] = 1
    elif problem == "not_executed":
        proof.pop("execution_provenance")
    else:
        entry["implementation_status"] = "not_implemented"
    assert validator._synthetic_errors("wistia", "update", entry, refs)


def test_live_claims_still_require_existing_dedicated_receipts():
    inventory = validator.load(validator.DOCS / "inventory.json")
    identities = validator.load(validator.DOCS / "provider-identities.json")
    invalid = deepcopy(inventory)
    row = next(row for row in invalid["providers"] if row["id"] == "wistia")
    row["outbound_mappings"][-1]["acceptance_status"] = "live_write_passed"
    assert any("outbound mapping cannot claim provider acceptance" in error
               for error in validator.semantic_errors(invalid, identities))
    row["outbound_mappings"][-1]["acceptance_status"] = "mock_passed"
    row["operations"]["discover"]["acceptance_status"] = "live_read_passed"
    assert any("live_read_passed is not allowed" in error
               for error in validator.semantic_errors(invalid, identities))


def test_packaged_synthetic_claim_retains_the_attributed_proof():
    data = validator.load(validator.DATA / "capabilities.json")
    identities = validator.load(validator.DOCS / "provider-identities.json")
    assert validator.semantic_errors(data, identities) == []
    wistia = next(row for row in data["providers"] if row["id"] == "wistia")
    swap = next(row for row in wistia["outbound_mappings"] if row["entity"] == "recording_replacement")
    assert swap["acceptance_status"] == "mock_passed"
    evidence = {row["id"]: row for row in wistia["evidence"]}
    assert validator._synthetic_errors("wistia", "update", swap, evidence) == []
    assert wistia["operations"]["discover"]["implementation_status"] == "implemented"
    # Executed swap evidence is deliberately not blanket whole-provider acceptance.
    assert wistia["operations"]["update"]["acceptance_status"] == "not_run"


@pytest.mark.parametrize("case", ["crlf", "changed", "unknown", "raw", "vendor"])
def test_explicit_test_source_line_ending_policy_is_narrow(evidence, case):
    entry, refs = evidence
    proof = refs["synthetic"]["synthetic_execution"]
    binding = proof["bindings"][0 if case == "vendor" else 1]
    path = validator.ROOT / binding["path"]
    original = b"first\nsecond\n"
    binding["sha256"] = hashlib.sha256(original).hexdigest()
    binding.update(hash_policy="test_source_crlf_to_lf",
                   canonical_lf_sha256=hashlib.sha256(original).hexdigest())
    path.write_bytes(original.replace(b"\n", b"\r\n"))
    if case == "changed":
        path.write_bytes(b"first\r\nchanged\r\n")
    elif case == "unknown":
        binding["hash_policy"] = "ignore_all_whitespace"
    elif case == "raw":
        binding.pop("hash_policy")
    errors = validator._synthetic_errors("wistia", "update", entry, refs)
    assert bool(errors) == (case != "crlf")
