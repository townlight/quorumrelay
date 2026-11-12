import base64
import json
from threading import Event

import pytest

from civic_data_connectors import Bounds, Engine, OperationContext, Query, Source
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.models import CaptureBundle


def payload(**extra):
    return json.dumps({"MeetingId": 8, "MeetingName": "Council", "MeetingDate": "2026-11-11T23:00:00Z",
                       "extra": {"zero": 0, "null": None, "false": False, "empty": "", "list": [1, "é"]},
                       **extra}, ensure_ascii=False).encode()


def test_original_unknown_fields_and_capture_exact_bytes():
    data = payload()
    result = Engine().normalize(Source("legistar", "https://example.org"), data)
    assert result.status == "completed"
    assert base64.b64decode(result.data["capture"]["content_base64"]) == data
    assert result.data["records"][0]["original"]["extra"] == json.loads(data)["extra"]
    assert result.data["records"][0]["source_revision"]["kind"] == "not_supplied"


def test_source_revision_capture_content_and_application_ids_are_distinct():
    first = Engine().normalize(Source("legistar", "https://one.example"), payload())
    second = Engine().normalize(Source("legistar", "https://two.example"), payload())
    a, b = first.data["records"][0], second.data["records"][0]
    assert a["capture_sha256"] == b["capture_sha256"]
    assert source_identity_key(a["identity"]) != source_identity_key(b["identity"])
    parent = {**a["identity"], "parent": {"external_id": "99"}}
    assert source_identity_key(parent) != source_identity_key(a["identity"])
    assert "application_id" not in a


def test_bounds_are_inclusive_and_unknown_dates_are_partial():
    result = Engine().normalize(Source("legistar", "https://example.org"), payload(),
                                bounds=Bounds(date_from="2026-11-11", date_to="2026-11-11"))
    assert result.status == "completed" and len(result.data["records"]) == 1
    result = Engine().normalize(Source("legistar", "https://example.org"), payload(),
                                bounds=Bounds(date_to="2026-11-10"))
    assert not result.data["records"] and result.coverage["filtered_records"] == 1


def test_tenant_namespace_validation():
    for source, context in [
        (Source("legistar", "https://one.example", namespace="//two.example"), None),
        (Source("legistar", "https://one.example"),
         OperationContext(allowed_namespaces=frozenset({"//two.example"}))),
    ]:
        assert Engine().normalize(source, payload(), context=context).status == "failed"


def test_cancel_before_and_mid_normalize():
    cancelled = Event()
    cancelled.set()
    assert Engine().normalize(Source("legistar", "https://example.org"), payload(),
                              context=OperationContext(cancellation=cancelled)).status == "cancelled"
    context = OperationContext()
    context.progress = lambda _: context.cancellation.set()
    result = Engine().normalize(Source("legistar", "https://example.org"), payload(), context=context)
    assert result.status == "cancelled"
    assert len(result.data["records"]) == 1


def test_parser_limit_independent_of_transfer_limit():
    result = Engine().normalize(Source("legistar", "https://example.org"), payload(),
                                bounds=Bounds(parser_bytes=5, transfer_bytes=200 * 1024 * 1024))
    assert result.status == "failed"


@pytest.mark.parametrize("bounds", [{"max_records": 0}, {"max_pages": -1}, {"parser_bytes": True},
                                   {"date_from": "2026-11-12", "date_to": "2026-11-11"}])
def test_invalid_bounds(bounds):
    with pytest.raises(ValueError):
        Bounds(**bounds)


def test_failed_parse_never_success_empty():
    result = Engine().execute("normalize", {"source": {"provider": "legistar", "url": "https://example.org"}},
                              content=b"not JSON")
    assert result.status == "failed" and result.errors and result.coverage["failures"]


def test_transport_input_and_unregistered_operations():
    engine = Engine()
    assert engine.execute("normalize", {}).status == "failed"
    assert engine.execute("normalize", {"source": {}, "content_base64": "not-base64"}).status == "failed"
    assert engine.execute("invented_operation", {}).status == "unsupported"
    assert Query(terms=("budget",), phrases=("public hearing",)).limit == 100


def test_client_scopes_and_credentials_not_serialized():
    a = OperationContext(principal="a", client_id="one", tenant="town", credentials={"token": "secret"})
    b = OperationContext(principal="a", client_id="two", tenant="town")
    assert a.scope != b.scope
    result = Engine().normalize(Source("legistar", "https://example.org"), payload(), context=a)
    assert "secret" not in json.dumps(result.public_dict())


def test_tyler_rich_cancelled_and_adjourned_retained_legacy_filtered():
    rows = [{"id": str(i), "meetingTitle": title, "startDateTime": "2026-11-11",
             "startTime": "07:00 PM", "isPublicVisibility": 1, "canceled": cancel, "adjourned": adjourned}
            for i, title, cancel, adjourned in
            [(1, "Council", False, False), (2, "Cancelled Council", True, False), (3, "Adjourned", False, True)]]
    result = Engine().normalize(Source("tyler-meeting-manager", "https://town.meetingmanager.tylerapp.com"),
                                json.dumps(rows).encode(), input_format="tyler-public-calendar-json")
    assert result.status == "completed", result.errors
    assert len(result.data["compatibility"]["meetings"]) == 1
    assert len(result.data["records"]) == 3
    assert result.data["records"][1]["normalized"]["source_status"]["canceled"] is True
    assert result.data["records"][2]["normalized"]["time_zone_status"] == "unknown"


def test_calendar_cancellation_and_timezone_parameters_preserved():
    capture = (b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:one\nSUMMARY:Cancelled council\n"
               b"DTSTART;TZID=America/Denver:20261111T190000\nSTATUS:CANCELLED\nEND:VEVENT\nEND:VCALENDAR\n")
    result = Engine().normalize(Source("first-party", "https://example.org/calendar.ics"), capture,
                                input_format="public-meeting-ics")
    assert result.status == "completed"
    assert not result.data["compatibility"]["meetings"]
    row = result.data["records"][0]["normalized"]
    assert row["source_status"] == "CANCELLED"
    assert row["source_calendar_parameters"]["DTSTART"] == "TZID=America/Denver"
    assert row["time_zone_status"] == "supplied_zone"
    assert row["source_time_zone"] == "America/Denver"


def test_typed_roundtrip_retains_unknown_nested_and_top_level_fields():
    result = Engine().normalize(Source("legistar", "https://example.org"), payload())
    bundle = result.data
    bundle["newer_bundle_field"] = {"zero": 0}
    bundle["source"]["newer_source_field"] = False
    bundle["records"][0]["newer_record_field"] = ["", None]
    bundle["records"][0]["identity"]["newer_identity_field"] = {"x": "é"}
    assert CaptureBundle.from_dict(bundle).public_dict() == bundle


def test_schema_validates_actual_result_and_bundle():
    from jsonschema import Draft202012Validator
    from civic_data_connectors.schemas import json_schema

    result = Engine().normalize(Source("legistar", "https://example.org"), payload()).public_dict()
    Draft202012Validator(json_schema("result")).validate(result)
    Draft202012Validator(json_schema("capture-bundle")).validate(result["data"])
    for name in ("source", "record", "query", "error", "bounds", "identity", "capture"):
        Draft202012Validator.check_schema(json_schema(name))


def test_truncation_is_partial_and_original_compatibility_untruncated():
    rows = [{"id": i, "dateTime": "2026-11-11T12:00:00", "title": f"Meeting {i}"} for i in range(3)]
    result = Engine().normalize(Source("primegov", "https://example.org"), json.dumps(rows).encode(),
                                input_format="primegov-portal-json", bounds=Bounds(max_records=2))
    assert result.status == "partial" and result.coverage["truncated"]
    assert len(result.data["records"]) == 2
    assert len(result.data["compatibility"]["meetings"]) == 3


def test_engine_and_direct_sdk_enforce_trusted_operation_policy():
    context = OperationContext(allowed_operations=frozenset({"providers"}))
    engine = Engine()
    assert engine.execute("normalize", {}, content=payload(), context=context).errors[0].code == "permission_denied"
    assert engine.normalize(Source("legistar", "https://example.org"), payload(),
                            context=context).errors[0].code == "permission_denied"
    assert engine.execute("providers", {}, context=context).status == "completed"


def test_consumer_state_tenant_differs_from_upstream_source_namespace():
    context = OperationContext(tenant="newsroom-123", allowed_namespaces=frozenset({"//example.org"}))
    assert Engine().normalize(Source("legistar", "https://example.org"), payload(),
                              context=context).status == "completed"


def test_trusted_discover_normalize_delegation_does_not_expand_public_grants():
    context = OperationContext(tenant="newsroom-123", allowed_operations=frozenset({"discover"}),
                               allowed_namespaces=frozenset({"//example.org"}))
    engine = Engine()
    engine.register_operation("discover", lambda eng, req, data, ctx:
                              eng.normalize(Source("legistar", "https://example.org"), payload(), context=ctx))
    assert engine.execute("discover", {}, context=context).status == "completed"
    assert engine.normalize(Source("legistar", "https://example.org"), payload(),
                            context=context).errors[0].code == "permission_denied"
    assert engine.execute("normalize", {}, context=context).errors[0].code == "permission_denied"


def test_conformance_checks_bound_signatures_and_allows_variadic_hooks():
    from civic_data_connectors.extensions import check_connector

    class Extension:
        provider = "synthetic"

        def capabilities(self):
            return {}

        def identify(self, url):
            return None

        def __getattr__(self, key):
            return lambda *args: None

    assert not check_connector(Extension())
    broken = Extension()
    broken.parse = lambda: None
    assert any("parse" in failure for failure in check_connector(broken))


def test_additive_parser_registration_cannot_replace_baseline_and_preserves_shared_bounds():
    from copy import deepcopy
    from civic_data_connectors import OperationResult
    owner = Engine()
    baseline = owner.normalize(Source("legistar", "https://example.org"), payload())
    bundle = deepcopy(baseline.data)
    second = deepcopy(bundle["records"][0])
    second["identity"]["external_id"] = "second"
    second["normalized"]["scheduled_start"] = "2026-11-12T12:00:00Z"
    bundle["records"].append(second)
    owner.register_parser("legistar", "synthetic-additive", lambda *args: OperationResult("completed", bundle))
    result = owner.normalize(Source("legistar", "https://example.org"), b"synthetic",
                             input_format="synthetic-additive", bounds=Bounds(date_to="2026-11-11"))
    assert result.status == "completed" and len(result.data["records"]) == 1
    assert result.coverage["filtered_records"] == 1
    with pytest.raises(ValueError, match="cannot replace"):
        owner.register_parser("legistar", "meeting-export", lambda *args: baseline)


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_original_parser_16mib_exact_boundary(delta):
    cap = Bounds().parser_bytes
    content = payload()
    content += b" " * (cap + delta - len(content))
    result = Engine().normalize(Source("legistar", "https://example.org"), content)
    assert result.status == ("failed" if delta > 0 else "completed")


def test_parent_identity_metadata_is_not_part_of_identity_but_parent_id_is():
    identity = {"provider": "legistar", "namespace": "//example.org", "record_type": "agenda_item",
                "external_id": "8", "parent": {
                    "provider": "legistar", "namespace": "//example.org", "record_type": "meeting",
                    "external_id": "99", "parent": None, "derivation": "url", "stability": "limited",
                }}
    from copy import deepcopy
    changed_metadata = deepcopy(identity)
    changed_metadata["parent"]["derivation"] = "provider"
    changed_metadata["parent"]["stability"] = "known"
    changed_metadata["parent"]["unknown_extension"] = {"hello": "world"}
    assert source_identity_key(identity) == source_identity_key(changed_metadata)
    changed_metadata["parent"]["external_id"] = "100"
    assert source_identity_key(identity) != source_identity_key(changed_metadata)
