"""Independent synthetic history-view server using the pinned vendor namespaces."""
import base64
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.contracts import Response
from test_escribe_publishing import MEETING, PORTAL, SOURCE, DATA, response, identity_key

VOTE = {"Id": 4, "MeetingId": MEETING, "MotionId": 3, "UserId": None,
        "UserName": "Source voter", "Vote": "Source vote label", "Weight": 2}
VALUE = {"Document": None, "Documents": {"Document.Record": [{"DisplayName": "Source document", "Id": 23}]},
    "History": {"DocumentId": 23, "Id": {"Id": 42, "PortalId": PORTAL}, "Type": "Source type",
    "AgendaItemId": 12, "AgendaItemTitle": "Library funding", "Comments": "Source history note",
    "Date": "2026-11-15T18:30:00", "MeetingId": MEETING},
    "Motions": {"Motion": [{"AgendaItemId": 12, "Id": 3, "MeetingId": MEETING, "Result": "Recorded result",
        "Text": "Allocate funding", "Votes": {"MotionVote": [VOTE]}}]},
    "Votes": {"MotionVote": [VOTE]}}
REQUEST = {"api_method": "AgendaItemItemHistoryView", "api_parameters": {"MeetingId": MEETING, "AgendaItemId": 12}}


def fields(node, values, namespace):
    for name, value in values.items():
        for entry in value if isinstance(value, list) else [value]:
            child = ET.SubElement(node, "{" + namespace + "}" + name)
            if isinstance(entry, dict):
                fields(child, entry, DATA if name == "History" or namespace == DATA else soap.NS)
            elif entry is None:
                child.set("{" + soap.XSI + "}nil", "true")
            else:
                child.text = str(entry)


class Server:
    def __init__(self, value=None):
        self.value = deepcopy(VALUE if value is None else value)
        self.calls = 0
        self.after = lambda: None
        self.payload = None
        self.transform = lambda result: None

    def request(self, url, **options):
        self.calls += 1
        request = ET.fromstring(options["body"])
        node = request.find("{" + soap.SOAP + "}Body")[0]
        assert [c.tag.split("}")[1] for c in node] == ["MeetingId", "AgendaItemId"]
        assert [c.text for c in node] == [MEETING, "12"]
        relation = request.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        result = ET.fromstring(response(REQUEST["api_method"], {}, relation=relation))
        target = result.find("{" + soap.SOAP + "}Body")[0][0]
        fields(target, self.value, soap.NS)
        self.transform(target)
        self.payload = ET.tostring(result)
        self.after()
        return Response(url, self.payload, "application/soap+xml")


def test_literal_motions_votes_inherited_history_capture_search_and_exports(tmp_path):
    server = Server()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "history.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["original"] == VALUE
    assert record["identity"]["external_id"] == identity_key(VALUE["History"]["Id"])
    assert record["identity"]["record_type"] == "agenda_item_history_view"
    assert record["normalized"]["source_motions"] == VALUE["Motions"]
    assert record["normalized"]["source_votes"] == VALUE["Votes"]
    assert "tally" not in record["normalized"]
    parent = next(r for r in record["relationships"] if r["relation"] == "agenda_item_reference")
    assert parent["value"]["native_agenda_item_id"] == 12 and "identity" not in parent
    documents = [r for r in record["relationships"] if r["relation"] == "document"]
    assert {r["identity"]["external_id"] for r in documents} == {"23"}
    assert {r["source_field"] for r in documents} == {"History.DocumentId", "Documents.Document.Record[0].Id"}
    assert base64.b64decode(result.data["capture"]["content_base64"]) == server.payload
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "history.sqlite"))
    hits = reopened.execute("search", {"query": {"phrases": ["Allocate funding"]}}).data["hits"]
    assert len(hits) == 1
    assert all(t["provenance"]["capture_sha256"] == result.data["capture"]["sha256"] for t in record["text"])
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("case", ["meeting", "item", "missing_history", "partial_id", "unknown", "bound", "cancel",
                                  "base_namespace", "base_order"])
def test_history_selection_schema_component_bounds_and_cancel_fail_closed(case):
    server = Server()
    context = OperationContext()
    bounds = Bounds()
    if case == "meeting":
        server.value["History"]["MeetingId"] = PORTAL
    elif case == "item":
        server.value["History"]["AgendaItemId"] = 13
    elif case == "missing_history":
        server.value["History"] = None
    elif case == "partial_id":
        server.value["History"]["Id"].pop("PortalId")
    elif case == "unknown":
        server.value["Motions"]["Motion"][0]["Unmapped"] = "field"
    elif case == "bound":
        bounds = Bounds(max_records=1)
    elif case in {"base_namespace", "base_order"}:
        def corrupt(target):
            history = target.find("{" + soap.NS + "}History")
            base_id = history.find("{" + DATA + "}Id")
            if case == "base_namespace":
                base_id.tag = "{" + soap.NS + "}Id"
            else:
                history.remove(base_id)
                history.append(base_id)
        server.transform = corrupt
    else:
        server.after = context.cancellation.set
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST, bounds=bounds, context=context)
    assert result.status == ("cancelled" if case == "cancel" else "failed"), result.public_dict()
    assert result.data is None


def test_history_keeps_previous_meeting_motions_and_null_votes_without_reparenting():
    server = Server()
    server.value["Motions"]["Motion"][0]["MeetingId"] = PORTAL
    server.value["Motions"]["Motion"][0]["Votes"] = None
    server.value["Votes"] = None
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["normalized"]["source_motions"]["Motion"][0]["MeetingId"] == PORTAL
    assert record["normalized"]["source_votes"] is None
    assert not any(r["relation"] == "motion" for r in record["relationships"])


@pytest.mark.parametrize("value", [None, "12", True, 0, -1])
def test_history_requires_exact_positive_native_item_before_network(value):
    request = deepcopy(REQUEST)
    request["api_parameters"]["AgendaItemId"] = value
    server = Server()
    result = create_engine(provider_transport=server).fetch(SOURCE, request)
    assert result.status == "failed" and server.calls == 0
