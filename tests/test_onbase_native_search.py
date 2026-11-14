"""Observed public HTML and vendor-response fault cases; no staff account required."""

import base64
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.contracts import Response

SOURCE = {"provider": "onbase", "url": "https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/"}
HTML = (Path(__file__).parent / "fixtures/onbase-search/fitchburg-council-2026.html").read_bytes()


class Vendor:
    def __init__(self, context):
        self.context, self.calls, self.fault = context, [], None

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False
        assert options["allowed_origins"] == ("https://agendas.fitchburgwi.gov",)
        assert options["deadline_seconds"] > 0
        raw = HTML
        if self.fault == "cancel":
            self.context.cancellation.set()
        if self.fault == "timeout":
            raise TimeoutError()
        if self.fault == "oversize":
            raw = b" " * (options["byte_limit"] + 1)
        if self.fault == "query":
            raw = raw.replace(b'value="Council"', b'value="different"')
        if self.fault == "layout":
            raw = b"<html>unavailable</html>"
        return Response(url + ("/other" if self.fault == "redirect" else ""), raw,
            "application/json" if self.fault == "mime" else "text/html; charset=utf-8",
            403 if self.fault == "denied" else 200)


def setup(tmp_path):
    context = OperationContext()
    vendor = Vendor(context)
    engine = create_engine(storage=SQLiteStorage(tmp_path / "search.sqlite"), provider_transport=vendor)
    request = {"source": SOURCE, "native": True, "query": {"terms": ["Council"]}}
    return engine, context, vendor, request


def test_observed_capped_search_keeps_native_ids_exact_capture_and_local_matching(tmp_path):
    engine, context, vendor, request = setup(tmp_path)
    result = engine.execute("search", request, context=context)
    assert result.status == "partial", result.public_dict()
    assert result.data["hits"]
    assert all("council" in r["normalized"]["title"].casefold() for r in result.data["records"])
    assert result.coverage["provider_candidates"] == 100
    assert result.coverage["provider_limit_reached"] is True
    assert result.coverage["truncated"] is True and result.coverage["catalog_complete"] is False
    assert result.coverage["checkpoint"] is None
    bundle = result.data["bundle"]
    assert len(bundle["records"]) == 100
    first = bundle["records"][0]
    assert first["identity"]["external_id"] == "3595"
    assert first["normalized"]["title"] == "Board of Public Works"
    fileless = next(r for r in bundle["records"] if r["identity"]["external_id"] == "3686")
    assert fileless["normalized"]["documents"] == []
    assert fileless["normalized"]["url"] == SOURCE["url"]
    assert fileless["original"]["row_attributes"]["data-meeting-id"] == "3686"
    assert base64.b64decode(bundle["capture"]["content_base64"]) == HTML
    assert len(vendor.calls) == 1
    assert parse_qs(urlsplit(vendor.calls[0][0]).query) == {"dropid": ["7"], "searchTerm": ["Council"]}


@pytest.mark.parametrize("fault", ["denied", "redirect", "mime", "timeout", "oversize", "query", "layout"])
def test_failure_never_becomes_empty_success(tmp_path, fault):
    engine, context, vendor, request = setup(tmp_path)
    vendor.fault = fault
    result = engine.execute("search", request, context=context)
    assert result.status == "failed" and result.errors
    assert len(vendor.calls) == 1


@pytest.mark.parametrize("before", [True, False])
def test_cancel_before_or_after_network(tmp_path, before):
    engine, context, vendor, request = setup(tmp_path)
    if before:
        context.cancellation.set()
    else:
        vendor.fault = "cancel"
    result = engine.execute("search", request, context=context)
    assert result.status == "cancelled"
    assert len(vendor.calls) == (0 if before else 1)


@pytest.mark.parametrize("change", ["checkpoint", "body", "item", "provider", "namespace", "empty"])
def test_unestablished_request_rejected_before_network(tmp_path, change):
    engine, context, vendor, request = setup(tmp_path)
    if change == "checkpoint":
        request["bounds"] = {"checkpoint": "untrusted"}
    elif change == "body":
        request["query"]["body"] = "Council"
    elif change == "item":
        request["query"]["record_types"] = ["agenda_item"]
    elif change == "provider":
        request["query"]["providers"] = ["legistar"]
    elif change == "namespace":
        request["query"]["namespaces"] = ["other"]
    else:
        request["query"] = {}
    result = engine.execute("search", request, context=context)
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


def test_bound_restricts_candidates_and_preserves_partial_without_cursor(tmp_path):
    engine, context, vendor, request = setup(tmp_path)
    request["bounds"] = {"max_records": 1}
    result = engine.execute("search", request, context=context)
    assert result.status == "partial" and not result.data["hits"]
    assert len(result.data["bundle"]["records"]) == 1
    assert result.coverage["truncated"] is True


def test_import_retry_reopen_local_search_and_zip_preserve_capture_and_identity(tmp_path):
    engine, context, vendor, request = setup(tmp_path)
    request["query"]["date_from"] = "2026-01-01"
    request["query"]["date_to"] = "2026-12-31"
    result = engine.execute("search", request, context=context)
    assert result.status == "partial", result.public_dict()
    bundle = result.data["bundle"]
    for _ in range(2):
        imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=context)
        assert imported.status == "completed", imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "search.sqlite"))
    assert len(list(reopened.storage.list("records", scope=context.scope))) == 100
    assert reopened.execute("search", {"query": {"terms": ["Council"]}}, context=context).data["hits"]
    exported = reopened.execute("export", {"format": "zip", "bundle": bundle}, context=context)
    assert exported.status == "completed", exported.public_dict()
    restored = create_engine().execute("import_bundle", {"format": "zip"}, context=context,
        content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    assert restored.data["bundle"] == bundle


def test_other_deployment_is_explicitly_unsupported(tmp_path):
    engine, context, vendor, request = setup(tmp_path)
    request["source"] = {**SOURCE, "url": "https://other.example/OnBaseAgendaOnline/"}
    result = engine.execute("search", request, context=context)
    assert result.status == "unsupported" and not vendor.calls


def test_native_row_disagreement_is_rejected_and_fileless_only_response_is_retained():
    from quorumrelay import Source
    from civic_data_connectors.providers.onbase_search import _rows
    with pytest.raises(ValueError):
        _rows(Source(**SOURCE), HTML.replace(b'data-meeting-id="3595"', b'data-meeting-id="9999"', 1))
    raw = b'''<table><tr id="meeting-1-row" class="meeting-row" data-meeting-id="1">
      <td data-sortable-type="mtgName">No documents</td>
      <td data-sortable-type="mtgTime">11/14/2026 1:00:00 PM</td></tr></table>'''
    rows = _rows(Source(**SOURCE), raw)
    assert len(rows) == 1 and rows[0][0]["external_id"] == "1"
    assert rows[0][0]["documents"] == []
