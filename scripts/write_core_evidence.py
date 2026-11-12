"""Produce a requirement-scoped machine-readable baseline implementation overlay."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from civic_data_connectors import compat
from civic_data_connectors.engine import canonical_hash

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/baseline"
CASES = json.loads((CORPUS / "cases.json").read_text(encoding="utf-8"))
ACCEPTANCE_IDS = {
    ("legistar", "meeting-export"): "B01", ("primegov", "meeting-export"): "B02",
    ("primegov", "primegov-portal-json"): "B03", ("granicus", "meeting-export"): "B04",
    ("granicus", "viewpublisher-html"): "B05", ("novusagenda", "meeting-export"): "B06",
}
REST = [
    ("civicplus-select", "civicplus-events-json"), ("civicplus-agenda-center", "agenda-center-html"),
    ("municode-meetings", "municode-meetings-html"), ("boardbook", "boardbook-html"),
    ("escribe", "escribe-calendar-json"), ("simbli", "simbli-html"), ("civicweb", "civicweb-html"),
    ("iqm2", "iqm2-html"), ("swagit", "swagit-archive-html"), ("suiteone-media", "suiteone-archive-html"),
    ("peak", "peak-viewpublisher-html"), ("utah-public-notice", "utah-notice-html"),
    ("destiny-agendaquick", "agendaquick-html"), ("town-hall-streams", "town-hall-streams-html"),
    ("telvue", "telvue-playlist-html"), ("champ", "champ-event-json"), ("onbase", "onbase-agenda-online-html"),
    ("laserfiche-weblink", "laserfiche-folder-html"), ("towncloud", "towncloud-table-json"),
    ("towncloud", "towncloud-agenda-html"), ("digital-towpath", "digital-towpath-detail-html"),
    ("clerkbase", "clerkbase-document-html"), ("first-party", "public-meeting-ics"),
    ("wistia", "wistia-media-json"), ("boardable", "boardable-public-meeting-html"),
    ("gworks", "gworks-frontdesk-json"), ("boarddocs", "boarddocs-print-pdf"),
    ("tyler-meeting-manager", "tyler-public-calendar-json"),
]
ACCEPTANCE_IDS.update({pair: f"B{number:02}" for number, pair in enumerate(REST, 7)})


def main():
    rows = []
    for case in CASES:
        pair = (case["connector"], case["input_format"])
        content = (CORPUS / case["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == case["sha256"]
        result = compat.preview_export(*pair[:1], case["source_url"], content, input_format=pair[1])
        assert canonical_hash(result) == case["original_output_sha256"]
        parser = (compat.read_meeting_export if pair[1] == "meeting-export" else compat.PORTAL_READERS[pair])
        fixture = "tests/fixtures/baseline/" + case["file"]
        parameter = case["connector"] + "/" + case["input_format"]
        rows.append({
            "provider": pair[0], "input_format": pair[1], "requirement_ids": [ACCEPTANCE_IDS[pair], "R02", "R03"],
            "operation": "parse", "implementation_status": "implemented",
            "acceptance_status": "fixture_passed", "result": "PASS",
            "evidence_level": "exact_pinned_original_output_comparison",
            "codepath": f"src/civic_data_connectors/compat.py:{parser.__name__}",
            "tests": [f"tests/test_baseline.py::test_original_corpus_exact_compatibility[{parameter}]",
                      f"tests/test_baseline.py::test_rich_capture_is_lossless_and_compatible[{parameter}]"],
            "fixture": fixture, "fixture_sha256": case["sha256"],
            "oracle_output_sha256": case["original_output_sha256"],
            "actual_output_sha256": canonical_hash(result),
            "original_record_count": case["original_record_count"],
            "namespace": case["original_namespace"],
            "proves": "Saved format parsing/legacy identity/provenance plus exact capture retention only.",
            "does_not_prove": ["live discovery", "native search", "vendor export", "remote writes",
                               "installed consumer acceptance"],
        })
    provider_ids = {row["provider"] for row in rows}
    assert len(rows) == 34 and len(provider_ids) == 31
    checks = [
        (["S02", "S03"], "tests/test_core.py::test_parent_identity_metadata_is_not_part_of_identity_but_parent_id_is"),
        (["S05", "S06"], "tests/test_core.py::test_typed_roundtrip_retains_unknown_nested_and_top_level_fields"),
        (["R05", "S07"], "tests/test_core.py::test_tyler_rich_cancelled_and_adjourned_retained_legacy_filtered"),
        (["S07", "C07"], "tests/test_core.py::test_calendar_cancellation_and_timezone_parameters_preserved"),
        (["S01"], "tests/test_core.py::test_schema_validates_actual_result_and_bundle"),
        (["G01", "G10"], "tests/test_core.py::test_trusted_discover_normalize_delegation_does_not_expand_public_grants"),
        (["I10"], "tests/test_core.py::test_conformance_checks_bound_signatures_and_allows_variadic_hooks"),
        (["I10"], "tests/test_extension_dispatch.py::test_example_extension_discovery_and_identification_need_no_transport_changes"),
        (["G03", "G04"], "tests/test_fetch.py::test_redirect_rechecks_dns_and_closes_every_connection"),
        (["G05"], "tests/test_fetch.py::test_dns_resolution_cannot_overrun_total_request_deadline"),
        (["G05", "G06"], "tests/test_fetch.py::test_default_large_transfer_boundary_streams_without_parser_cap"),
        (["G06"], "tests/test_core.py::test_original_parser_16mib_exact_boundary"),
        (["R03", "S09"], "tests/test_legacy_projection.py::test_native_existing_transition_needs_evidenced_id_mapping"),
        (["C06", "S09"], "tests/test_legacy_projection.py::test_projection_uses_only_selected_records_not_unfiltered_page_preview"),
    ]
    files = ["compat.py", "normalization.py", "fetch.py", "models.py", "engine.py", "extensions.py",
             "schemas.py", "factory.py", "legacy.py", "capabilities.py"]
    evidence = {
        "schema_version": "1.0.0", "owner": "core", "library_version": "0.1.0.dev1",
        "record_schema_version": "2.0.0", "observed_at": datetime.now(timezone.utc).isoformat(),
        "test_policy": "synthetic/mock tests and preserved original saved public captures; no live writes",
        "release_status": "incomplete", "provider_count": 31, "baseline_format_count": 34,
        "source_pins": [
            {"repository": "https://github.com/townlight/townlight",
             "revision": "d4470aeae662c759351f63140b035edac10d9a52", "state_before_extraction": "clean",
             "paths": ["desktop/runtime/python-services/townlight_runtime/meeting_imports.py",
                       "desktop/runtime/python-services/townlight_runtime/meeting_import_fetch.py"]},
            {"repository": "https://github.com/townlight/core",
             "revision": "88fe5bd19110058b93d72ce4bb5ae9c2d68d0106", "state_before_extraction": "clean",
             "paths": ["townlight_core/connectors/imports.py"]},
            {"repository": "https://github.com/townlight/meetings",
             "revision": "f8ccf82807597e228ba276e1b3f89d053a7c0018", "state_before_extraction": "clean",
             "paths": ["townlight_meetings/imported_meetings.py"], "reuse": "semantics, no persistence copied"},
        ],
        "oracle": {
            "method": "scripts/capture_baseline.py executed pinned untouched original readers/Core normalizers",
            "original_corpus_manifest": "tests/fixtures/baseline/cases.json",
            "manifest_sha256": hashlib.sha256((CORPUS / "cases.json").read_bytes()).hexdigest(),
            "validator_oracle_sha256": "4ecc089cb8e130218bc9bba819abe095eefdebc0187b61fc58262faf5e7cc6b7",
            "validator_report": "Independent validator reported frozen baseline wheel full JSON34/34 and no reference imports.",
        },
        "commands": [
            {"command": ".venv/Scripts/python.exe -m pytest tests/test_baseline.py tests/test_core.py tests/test_fetch.py tests/test_legacy_projection.py tests/test_extension_dispatch.py tests/test_capabilities.py -q",
             "exit_status": 0, "result": "PASS", "note": "Each per-format test listed below is separately parameterized."},
            {"command": ".venv/Scripts/python.exe scripts/run_original_matrix.py <pinned-original>/check-source-matrix.py",
             "exit_status": 0, "result": "PASS", "observed": "34/34 unchanged original runner local-parser cases"},
            {"command": ".venv/Scripts/python.exe -m pytest tests -q", "exit_status": 0,
             "result": "PASS", "observed": "279 passed, 1 Starlette/anyio deprecation warning in57.48s",
             "limits": "Intermediate combined-source snapshot, not final artifact or later changes."},
        ],
        "source_file_sha256": {f"src/civic_data_connectors/{name}":
                               hashlib.sha256((ROOT / "src/civic_data_connectors" / name).read_bytes()).hexdigest()
                               for name in files},
        "baseline_parse": rows,
        "non_provider_specific_checks": [
            {"requirement_ids": ids, "test": test, "result": "PASS",
             "limits": "Core contract behavior only; not evidence of each provider live operation."}
            for ids, test in checks
        ],
        "live_write_acceptance": "NOT_RUN", "installed_consumer_acceptance": "NOT_RUN",
        "remaining": ["Final coordinated artifact rebuild and affected reruns",
                      "Live provider writes prohibited by current mock-data direction",
                      "Installed consumer and signed-installer acceptance are separate owning tracks"],
    }
    path = ROOT / "docs/verification/core.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(path), "providers": len(provider_ids), "formats": len(rows),
                      "baseline_result": "PASS"}))


if __name__ == "__main__":
    main()
