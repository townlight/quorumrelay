"""Explicit typed document cursor selection, without inferred paging semantics."""
import base64
from copy import deepcopy

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from test_escribe_publishing import SOURCE, sample
from test_escribe_selected_text import Collection

METHOD = "DocumentGetSince"
REQUEST = {"api_method": METHOD, "api_parameters": {"intLastInsertedId": 20}}


def server(values=None):
    row = sample("Document")
    row["DisplayName"] = "Budget source metadata"
    return Collection(METHOD, [row] if values is None else values, "Document.Record")


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_explicit_cursor_request_capture_metadata_search_reopen_and_exports(tmp_path, format):
    vendor = server()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "documents.sqlite"), provider_transport=vendor)
    result = owner.fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    row, = result.data["records"]
    assert row["identity"]["external_id"] == "23" and row["identity"]["record_type"] == "document"
    assert row["original"] == vendor.values[0]
    assert row["normalized"]["documents"] == [] and not row["relationships"]
    assert vendor.calls == 1
    assert vendor.parameters[0].tag == "{" + soap.NS + "}intLastInsertedId"
    assert vendor.parameters[0].text == "20"
    assert not result.coverage["source_complete"] and not result.coverage["catalog_complete"]
    assert result.coverage["pagination"] == "not_inferred"
    context = result.data["extensions"]["native_request_context"]
    assert context["api_parameters"] == REQUEST["api_parameters"]
    assert "continuation_not_inferred" in context["selection_semantics"]
    assert base64.b64decode(result.data["capture"]["content_base64"])
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "documents.sqlite"))
    hits = reopened.execute("search", {"query": {"phrases": ["Budget source metadata"]}}).data["hits"]
    assert len(hits) == 1 and hits[0]["identity"]["external_id"] == "23"
    exported = reopened.execute("export", {"bundle": result.data, "format": format})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data
    saved = owner.normalize(SOURCE, base64.b64decode(result.data["capture"]["content_base64"]), input_format=soap.FORMAT)
    assert saved.status == "completed"
    assert [{k: v for k, v in r.items() if k != "captured_at"} for r in saved.data["records"]] == [
        {k: v for k, v in r.items() if k != "captured_at"} for r in result.data["records"]]
    assert "native_request_context" not in saved.data["extensions"]
    vendor.values[0]["DisplayName"] = "Changed document metadata"
    revised = owner.fetch(SOURCE, REQUEST)
    changed, = revised.data["records"]
    assert changed["identity"] == row["identity"] and changed["normalized_sha256"] != row["normalized_sha256"]


@pytest.mark.parametrize("identity", [-1, True, 2.5, "20", 2**31, None])
def test_invalid_native_cursor_never_requests(identity):
    vendor = server()
    result = create_engine(provider_transport=vendor).fetch(SOURCE,
        {"api_method": METHOD, "api_parameters": {"intLastInsertedId": identity}})
    assert result.status == "failed" and result.data is None and not vendor.calls


@pytest.mark.parametrize("case", ["negative", "zero", "duplicate", "bound"])
def test_unverified_document_collection_never_publishes_truncated_success(case):
    row = sample("Document")
    vendor = server([row])
    bounds = Bounds(max_records=1)
    if case in {"negative", "zero"}:
        row["Id"] = -1 if case == "negative" else 0
    else:
        other = deepcopy(row)
        other["Id"] = row["Id"] if case == "duplicate" else 24
        vendor.values.append(other)
    result = create_engine(provider_transport=vendor).fetch(SOURCE, REQUEST, bounds=bounds)
    assert result.status == "failed" and result.data is None


def test_empty_result_and_cursor_inclusion_never_imply_provider_exhaustion():
    empty = create_engine(provider_transport=server([])).fetch(SOURCE, REQUEST)
    assert empty.status == "partial" and empty.data["records"] == []
    assert not empty.coverage["source_complete"] and not empty.coverage["catalog_complete"]
    row = sample("Document")
    row["Id"] = 20
    result = create_engine(provider_transport=server([row])).fetch(SOURCE, REQUEST)
    assert result.status == "partial" and result.data["records"][0]["identity"]["external_id"] == "20"
    assert "checkpoint" not in result.coverage


@pytest.mark.parametrize("when", ["before", "transport", "deadline", "bytes"])
def test_interruption_and_transfer_bounds_never_publish_metadata(monkeypatch, when):
    vendor, clock, ctx = server(), [0.0], OperationContext()
    monkeypatch.setattr(soap, "monotonic", lambda: clock[0])
    if when == "before":
        ctx.cancellation.set()
    elif when == "transport":
        vendor.after = ctx.cancellation.set
    elif when == "deadline":
        vendor.after = lambda: clock.__setitem__(0, 2.0)
    result = create_engine(provider_transport=vendor).fetch(SOURCE, REQUEST, context=ctx,
        bounds=Bounds(deadline_seconds=1, transfer_bytes=16 if when == "bytes" else 100000))
    assert result.status == ("cancelled" if when in {"before", "transport"} else "failed")
    assert result.data is None
    if when in {"before", "bytes"}:
        assert not vendor.calls


def test_configured_discovery_uses_explicit_native_selector_without_advancing_it():
    vendor = server()
    result = create_engine(provider_transport=vendor).execute("discover", {"source": SOURCE.public_dict(), **REQUEST})
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert vendor.calls == 1 and vendor.parameters[0].text == "20"
    assert result.data["extensions"]["native_request_context"]["api_parameters"] == REQUEST["api_parameters"]
    assert "checkpoint" not in result.coverage and not result.coverage["source_complete"]


@pytest.mark.parametrize("operation", ["fetch", "discover"])
def test_unapproved_namespace_prevents_selector_network_request(operation):
    vendor = server()
    ctx = OperationContext(allowed_namespaces=frozenset({"another-source"}))
    result = create_engine(provider_transport=vendor).execute(operation, {"source": SOURCE.public_dict(), **REQUEST}, context=ctx)
    assert result.status == "failed" and result.data is None and not vendor.calls


@pytest.mark.parametrize("case", ["missing", "other_method", "saved", "records"])
def test_discovery_never_broadens_to_unmapped_catalog_or_supplied_data(case):
    vendor = server()
    request = {"source": SOURCE.public_dict(), **deepcopy(REQUEST)}
    if case == "missing":
        request.pop("api_method")
    elif case == "other_method":
        request["api_method"] = "MeetingGetAll"
    elif case == "saved":
        request["content_base64"] = ""
    else:
        request["records"] = []
    result = create_engine(provider_transport=vendor).execute("discover", request)
    assert result.status == "failed" and result.data is None and not vendor.calls
