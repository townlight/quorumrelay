"""Pinned native history item IDs with explicit selected-meeting context."""
import base64
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_history, escribe_publishing as soap
from civic_data_connectors.providers.contracts import Response
from test_escribe_publishing import ARRAY, MEETING, PORTAL, SOURCE, response, identity_key
from test_escribe_history import Server as History, REQUEST as HISTORY_REQUEST

METHOD = "MeetingAgendaItemsWithHistory"
REQUEST = {"api_method": METHOD, "api_parameters": {"MeetingId": MEETING}}


class Index:
    def __init__(self, ids=(12, 13), *, nil=False, namespace=ARRAY):
        self.ids, self.nil, self.namespace = ids, nil, namespace
        self.calls, self.payload = [], None
        self.after = lambda: None

    def request(self, url, **options):
        request = ET.fromstring(options["body"])
        selected = request.find("{" + soap.SOAP + "}Body")[0]
        assert selected.tag == "{" + soap.NS + "}" + METHOD
        assert len(selected) == 1 and selected[0].tag == "{" + soap.NS + "}MeetingId"
        self.calls.append(selected[0].text)
        relation = request.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        envelope = ET.fromstring(response(METHOD, None if self.nil else {}, relation=relation))
        target = envelope.find("{" + soap.SOAP + "}Body")[0][0]
        if not self.nil:
            for value in self.ids:
                ET.SubElement(target, "{" + self.namespace + "}int").text = str(value)
        self.payload = ET.tostring(envelope)
        self.after()
        return Response(url, self.payload, "application/soap+xml")


def test_index_native_ids_context_search_reopen_and_neutral_formats(tmp_path):
    server = Index()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "index.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert server.calls == [MEETING]
    assert [r["original"] for r in result.data["records"]] == [12, 13]
    record = result.data["records"][0]
    assert record["identity"]["record_type"] == "agenda_item_history_reference"
    assert record["identity"]["external_id"] == identity_key({"MeetingId": MEETING, "AgendaItemId": 12})
    assert record["normalized"]["meeting_binding"] == "explicit_request_context_not_response_echo"
    assert record["relationships"][0]["identity"]["external_id"] == MEETING
    assert "identity" not in record["relationships"][1]
    assert result.data["extensions"]["native_request_context"] == REQUEST
    assert base64.b64decode(result.data["capture"]["content_base64"]) == server.payload
    assert not result.coverage["catalog_complete"] and result.coverage["pagination"] == "not_inferred"
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "index.sqlite"))
    assert len(reopened.execute("search", {"query": {"record_types": ["agenda_item_history_reference"]}}).data["hits"]) == 2
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data
    other = create_engine(provider_transport=Index()).fetch(SOURCE, {
        "api_method": METHOD, "api_parameters": {"MeetingId": PORTAL}})
    assert other.data["records"][0]["identity"] != record["identity"]
    # A bare array cannot independently prove a parent when replayed offline.
    normalized = owner.execute("normalize", {"source": SOURCE.public_dict()}, content=server.payload)
    assert normalized.status == "failed"


@pytest.mark.parametrize("nil", [False, True])
def test_nil_and_empty_are_explicit_partial_results(nil):
    result = create_engine(provider_transport=Index((), nil=nil)).fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors and not result.data["records"]
    assert result.data["extensions"]["native_result_availability"] == ("nil" if nil else "supplied_array")
    assert result.coverage["catalog_complete"] is False


def test_native_index_selects_existing_history_view_without_an_identity_guess():
    index, history = Index((12,)), History()

    class Routing:
        def request(self, url, **options):
            method = ET.fromstring(options["body"]).find("{" + soap.SOAP + "}Body")[0].tag
            return (index if method.endswith("}" + METHOD) else history).request(url, **options)

    engine = create_engine(provider_transport=Routing())
    selected = engine.fetch(SOURCE, REQUEST)
    assert history.calls == 0  # No implicit fan-out over the native selector.
    item = selected.data["records"][0]["normalized"]["native_agenda_item_id"]
    detail = engine.fetch(SOURCE, {"api_method": HISTORY_REQUEST["api_method"],
        "api_parameters": {"MeetingId": MEETING, "AgendaItemId": item}})
    assert detail.status == "partial" and not detail.errors
    assert detail.data["records"][0]["original"]["History"]["AgendaItemId"] == item
    assert index.calls == [MEETING] and history.calls == 1


@pytest.mark.parametrize("ids", [(0,), (-1,), (12, 12), (2147483648,), ("12.5",), ("true",)])
def test_invalid_or_duplicate_native_ids_fail_without_a_partial_projection(ids):
    result = create_engine(provider_transport=Index(ids)).fetch(SOURCE, REQUEST)
    assert result.status == "failed" and result.errors and result.data is None


@pytest.mark.parametrize("case", ["bound", "namespace", "cancel", "deadline", "transfer"])
def test_index_obeys_schema_and_operation_completion_bounds(monkeypatch, case):
    server, caller, bounds = Index(), OperationContext(), Bounds()
    clock = [0.0]
    if case == "bound":
        bounds = Bounds(max_records=1)
    elif case == "namespace":
        server.namespace = soap.NS
    elif case == "cancel":
        server.after = caller.cancellation.set
    elif case == "transfer":
        bounds = Bounds(transfer_bytes=1)
    else:
        original = escribe_history.history_index_bundle

        def expired(*args, **kwargs):
            bundle = original(*args, **kwargs)
            clock[0] = 2.0
            return bundle

        monkeypatch.setattr(escribe_history, "history_index_bundle", expired)
        monkeypatch.setattr(soap, "monotonic", lambda: clock[0])
        bounds = Bounds(deadline_seconds=1)
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST, bounds=bounds, context=caller)
    assert result.status == ("cancelled" if case == "cancel" else "failed"), result.public_dict()
    assert result.data is None


@pytest.mark.parametrize("parameters", [{}, {"MeetingId": None}, {"MeetingId": "not-guid"},
                                      {"meetingId": MEETING}, {"MeetingId": MEETING, "Extra": 1}])
def test_index_requires_exact_native_meeting_before_network(parameters):
    server = Index()
    request = deepcopy(REQUEST)
    request["api_parameters"] = parameters
    result = create_engine(provider_transport=server).fetch(SOURCE, request)
    assert result.status == "failed" and not server.calls
