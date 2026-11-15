"""Native meeting type selection without guessed IDs or language meanings."""
import base64
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.contracts import Response
from test_escribe_publishing import ARRAY, MEETING, PORTAL, SOURCE, identity_key, response, sample
from test_escribe_selected_text import Collection

METHOD = "MeetingTypeGetByPortal"
REQUEST = {"api_method": METHOD, "api_parameters": {"PortalId": PORTAL}}
VALUE = {"Id": {"Id": 7, "PortalId": PORTAL},
         "Name": {"KeyValueOfintstring": [{"Key": 1033, "Value": "Supplied council type"},
                                         {"Key": 1036, "Value": "Conseil fourni"}]}}


class Types:
    def __init__(self, values=None):
        self.values = deepcopy([VALUE] if values is None else values)
        self.calls, self.payload = 0, None
        self.after = lambda: None

    def request(self, url, **options):
        self.calls += 1
        request = ET.fromstring(options["body"])
        selected = request.find("{" + soap.SOAP + "}Body")[0]
        assert selected.tag == "{" + soap.NS + "}" + METHOD
        assert len(selected) == 1 and selected[0].tag == "{" + soap.NS + "}PortalId"
        assert selected[0].text == PORTAL
        relation = request.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        envelope = ET.fromstring(response(METHOD, {}, relation=relation))
        target = envelope.find("{" + soap.SOAP + "}Body")[0][0]
        for row in self.values:
            node = ET.SubElement(target, "{" + soap.NS + "}MeetingType.Record")
            for key, value in row.items():
                field = ET.SubElement(node, "{" + soap.NS + "}" + key)
                if value is None:
                    field.set("{" + soap.XSI + "}nil", "true")
                elif key == "Id":
                    for name, literal in value.items():
                        ET.SubElement(field, "{" + soap.NS + "}" + name).text = str(literal)
                elif key == "Name":
                    for entry in value["KeyValueOfintstring"]:
                        pair = ET.SubElement(field, "{" + ARRAY + "}KeyValueOfintstring")
                        for name, literal in entry.items():
                            ET.SubElement(pair, "{" + ARRAY + "}" + name).text = str(literal)
                else:
                    field.text = str(value)
        self.payload = ET.tostring(envelope)
        self.after()
        return Response(url, self.payload, "application/soap+xml")


def test_types_select_existing_meeting_list_and_preserve_names_capture_exports(tmp_path):
    server = Types()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "types.sqlite"), provider_transport=server)
    result = engine.fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["record_type"] == "meeting_type"
    assert record["identity"]["external_id"] == identity_key(VALUE["Id"])
    assert record["original"] == VALUE and record["normalized"]["native_fields"] == VALUE
    assert {t["provenance"]["source_language_key"] for t in record["text"]} == {1033, 1036}
    assert all(t["citation_url"] == SOURCE.url for t in record["text"])
    assert base64.b64decode(result.data["capture"]["content_base64"]) == server.payload
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "types.sqlite"))
    assert len(reopened.execute("search", {"query": {"phrases": ["Conseil fourni"]}}).data["hits"]) == 1
    for format in ("json", "jsonl", "zip"):
        exported = engine.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data
    selected = Collection("MeetingGetByMeetingType", [sample("Meeting")], "Meeting.Record")
    meetings = create_engine(provider_transport=selected).fetch(SOURCE, {
        "api_method": selected.method, "api_parameters": {"Id": record["original"]["Id"]}})
    assert meetings.status == "partial" and not meetings.errors
    assert meetings.data["records"][0]["identity"]["external_id"] == MEETING


@pytest.mark.parametrize("case", ["wrong_portal", "missing_component", "nil_id", "duplicate", "bound", "unknown"])
def test_type_identity_parent_and_response_bounds_fail_closed(case):
    server, bounds = Types(), Bounds()
    if case == "wrong_portal":
        server.values[0]["Id"]["PortalId"] = MEETING
    elif case == "missing_component":
        server.values[0]["Id"].pop("PortalId")
    elif case == "nil_id":
        server.values[0]["Id"] = None
    elif case == "unknown":
        server.values[0]["Extra"] = "unmapped"
    else:
        server.values.append(deepcopy(VALUE))
        if case == "bound":
            server.values[1]["Id"]["Id"] = 8
            bounds = Bounds(max_records=1)
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST, bounds=bounds)
    assert result.status == "failed" and result.errors and result.data is None


@pytest.mark.parametrize("case", ["empty", "null_name", "cancel", "deadline"])
def test_type_empty_names_and_interruption_remain_explicit(monkeypatch, case):
    server, caller, bounds = Types(), OperationContext(), Bounds()
    if case == "empty":
        server.values = []
    elif case == "null_name":
        server.values[0]["Name"] = None
    elif case == "cancel":
        server.after = caller.cancellation.set
    else:
        clock = [0.0]
        monkeypatch.setattr(soap, "monotonic", lambda: clock[0])
        server.after = lambda: clock.__setitem__(0, 2.0)
        bounds = Bounds(deadline_seconds=1)
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST, context=caller, bounds=bounds)
    if case in {"empty", "null_name"}:
        assert result.status == "partial" and not result.errors and not result.coverage["catalog_complete"]
        assert not result.data["records"] if case == "empty" else not result.data["records"][0]["text"]
    else:
        assert result.status == ("cancelled" if case == "cancel" else "failed") and result.data is None


@pytest.mark.parametrize("parameters", [{}, {"PortalId": None}, {"PortalId": "not-guid"}, {"portalId": PORTAL}])
def test_exact_type_selector_required_before_network(parameters):
    server = Types()
    result = create_engine(provider_transport=server).fetch(SOURCE, {"api_method": METHOD, "api_parameters": parameters})
    assert result.status == "failed" and not server.calls
