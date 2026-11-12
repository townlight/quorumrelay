from copy import deepcopy
from dataclasses import replace

from civic_data_connectors import Bounds, Engine, OperationResult, Source
from civic_data_connectors.legacy import LegacyIdentityMapping, legacy_previews
from test_core import payload


def test_exact_existing_preview_and_partial_coverage_preserved():
    result = Engine().normalize(Source("legistar", "https://example.org"), payload())
    projected = legacy_previews(result)
    assert projected.data["previews"] == [result.data["compatibility"]]
    partial = replace(result, status="partial", coverage={"failures": ["page-2"]})
    projected = legacy_previews(partial)
    assert projected.status == "partial" and projected.coverage["failures"] == ["page-2"]


def native_result():
    result = Engine().normalize(Source("legistar", "https://webapi.legistar.com/v1/town/Events"), payload())
    data = deepcopy(result.data)
    data["compatibility"] = {}
    data["records"][0]["identity"]["external_id"] = "Event-8"
    data["records"][0]["normalized"]["external_id"] = "Event-8"
    return OperationResult("completed", data=data)


def test_native_existing_transition_needs_evidenced_id_mapping():
    result = native_result()
    blocked = legacy_previews(result)
    assert blocked.status == "failed"
    assert blocked.errors[0].code == "legacy_identity_mapping_required"
    mapping = LegacyIdentityMapping("legistar", "//webapi.legistar.com/v1/town", "https://town.legistar.com",
                                    {"Event-8": "old-Meeting-88"}, "verified historical import ledger mapping")
    projected = legacy_previews(result, identity_mappings=(mapping,))
    assert projected.status == "completed"
    preview = projected.data["previews"][0]
    assert preview["source"]["namespace"] == "//town.legistar.com"
    assert preview["meetings"][0]["external_id"] == "old-Meeting-88"


def test_explicit_brand_new_source_import_keeps_provider_identity_without_legacy_claim():
    result = native_result()
    projected = legacy_previews(result, new_source=True)
    assert projected.status == "completed"
    preview = projected.data["previews"][0]
    assert preview["source"]["namespace"] == "//webapi.legistar.com/v1/town"
    assert preview["meetings"][0]["external_id"] == "Event-8"
    assert projected.coverage["new_source"] is True


def test_new_source_does_not_accept_arbitrary_namespace_alias():
    result = native_result()
    result.data["records"][0]["identity"]["namespace"] = "//different.example"
    projected = legacy_previews(result, new_source=True)
    assert projected.status == "failed" and projected.errors[0].code == "legacy_source_mismatch"


def test_native_convenience_preview_never_bypasses_existing_identity_mapping():
    result = native_result()
    result.data["compatibility"] = {
        "version": 1, "source": {"connector": "legistar", "url": result.data["source"]["url"],
                                 "namespace": result.data["source"]["namespace"],
                                 "format": "legistar-events-json",
                                 "sha256": result.data["capture"]["sha256"]},
        "meetings": [result.data["records"][0]["normalized"]],
    }
    assert legacy_previews(result).errors[0].code == "legacy_identity_mapping_required"
    assert legacy_previews(result, new_source=True).status == "completed"


def test_projection_uses_only_selected_records_not_unfiltered_page_preview():
    import json
    rows = [{"id": i, "dateTime": f"2026-11-{i + 10:02}T12:00:00", "title": f"Meeting {i}"} for i in range(4)]
    normalized = Engine().normalize(Source("primegov", "https://example.org"), json.dumps(rows).encode(),
                                    input_format="primegov-portal-json",
                                    bounds=Bounds(date_from="2026-11-11", date_to="2026-11-13", max_records=2))
    assert normalized.status == "partial"
    assert len(normalized.data["compatibility"]["meetings"]) == 4
    aggregate = OperationResult("partial", {
        "records": normalized.data["records"], "bundles": [normalized.data],
    }, coverage=normalized.coverage)
    projected = legacy_previews(aggregate)
    assert projected.status == "partial"
    assert [m["external_id"] for p in projected.data["previews"] for m in p["meetings"]] == ["1", "2"]
