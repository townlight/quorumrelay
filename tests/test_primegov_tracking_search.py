"""Literal public TrackingNo form mapping, not authenticated API equivalence."""

import base64
import json
from urllib.parse import parse_qs

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.storage import SQLiteStorage
from test_primegov_native_search import Transport, request


def tracking_request(number="PG-2026/011", **bounds):
    value = request(**bounds)
    value["source"] = {**value["source"], "options": {"tracking_number": number}}
    return value


@pytest.mark.parametrize("text", [True, False])
@pytest.mark.parametrize("number", ["PG-2026/011", "A&B=2 +% café"])
def test_public_tracking_number_is_sent_literally_with_optional_local_text(text, number):
    vendor = Transport()
    value = tracking_request(number)
    if not text:
        value["query"]["terms"] = []
    result = create_engine(provider_transport=vendor).execute("search", value)
    assert result.status == "partial", result.public_dict()
    fields = parse_qs(vendor.calls[0][1]["body"].decode(), keep_blank_values=True)
    assert fields["TrackingNo"] == [number]
    assert fields["Text"] == ["Council" if text else ""]
    assert result.coverage["tracking_number_filter"] == {
        "value": number, "field": "TrackingNo", "matching": "provider_defined_not_locally_verified"}
    bundle = result.data["bundle"]
    assert bundle["extensions"]["public_search_request"]["fields"]["TrackingNo"] == number
    assert base64.b64decode(bundle["capture"]["content_base64"]) == vendor.content
    originals = json.loads(vendor.content)
    assert all(row["original"] in originals for row in bundle["records"])
    assert result.coverage["source_complete"] is False


@pytest.mark.parametrize("number", [None, True, 7, [], {}, "", "  ", "A\x00B", "A\nB", "x" * 1025])
def test_invalid_tracking_filter_is_rejected_without_network(number):
    vendor = Transport()
    result = create_engine(provider_transport=vendor).execute("search", tracking_request(number))
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


def test_tracking_filter_keeps_required_dates_and_utf8_byte_bounds():
    vendor = Transport()
    owner = create_engine(provider_transport=vendor)
    value = tracking_request()
    value["query"].pop("date_from")
    assert owner.execute("search", value).status == "failed"
    value = tracking_request("\u00e9" * 257, parser_bytes=512)
    assert owner.execute("search", value).status == "failed"
    assert not vendor.calls


def test_tracking_option_is_not_enabled_for_another_provider():
    vendor = Transport()
    value = tracking_request()
    value["source"] = {**value["source"], "provider": "legistar", "url": "https://webapi.legistar.com/v1/fixture/events"}
    result = create_engine(provider_transport=vendor).execute("search", value)
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


def test_resume_is_bound_to_the_tracking_filter():
    vendor = Transport()
    owner = create_engine(provider_transport=vendor)
    first = owner.execute("search", tracking_request(max_records=1))
    token = first.coverage["checkpoint"]
    assert token
    before = len(vendor.calls)
    changed = owner.execute("search", tracking_request("PG-OTHER", checkpoint=token))
    assert changed.status == "failed" and len(vendor.calls) == before
    removed = owner.execute("search", request(checkpoint=token))
    assert removed.status == "failed" and len(vendor.calls) == before
    resumed = owner.execute("search", tracking_request(max_records=2, checkpoint=token))
    assert resumed.status == "partial"
    assert resumed.data["bundle"]["records"][0]["identity"] != first.data["bundle"]["records"][0]["identity"]


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_tracking_request_context_survives_reopen_and_neutral_export(tmp_path, format):
    store = SQLiteStorage(tmp_path / "tracking.sqlite")
    owner = create_engine(storage=store, provider_transport=Transport())
    caller = OperationContext(principal="tracking-reader")
    result = owner.execute("search", tracking_request(max_records=2), context=caller)
    assert result.status == "partial", result.public_dict()
    bundle = result.data["bundle"]
    saved = owner.execute("import_bundle", {"bundle": bundle, "persist": True}, context=caller)
    assert saved.status in {"partial", "completed"}, saved.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "tracking.sqlite"))
    stored = reopened.storage.list("bundles", scope=caller.scope)
    assert len(stored) == 1
    exported = reopened.execute("export", {"bundle_key": stored[0].key, "format": format}, context=caller)
    assert exported.status in {"partial", "completed"}, exported.public_dict()
    restored = read_bundle(base64.b64decode(exported.data["content_base64"]), format=format)
    assert restored["extensions"]["public_search_request"] == bundle["extensions"]["public_search_request"]
    assert restored["records"] == bundle["records"]
