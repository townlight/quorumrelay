"""Synthetic bounded meeting-type and native-language item-text selection."""
import base64
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.contracts import Response
from test_escribe_publishing import MEETING, PORTAL, SOURCE, identity_key, response, sample, xml_fields

TEXT = {"AgendaType": "Agenda", "AllowPublicComments": False, "Description": "Supplied description",
        "Header": "Source heading", "Id": 12, "LanguageId": 1033, "MeetingId": MEETING,
        "Mintues": "The source minutes spelling is preserved.", "Title": "Library evidence"}


class Collection:
    def __init__(self, method, values, wrapper):
        self.method, self.values, self.wrapper = method, values, wrapper
        self.calls = 0
        self.parameters = None
        self.after = lambda: None

    def request(self, url, **options):
        self.calls += 1
        envelope = ET.fromstring(options["body"])
        header = envelope.find("{" + soap.SOAP + "}Header")
        relation = header.findtext("{" + soap.ADDRESS + "}MessageID")
        self.parameters = envelope.find("{" + soap.SOAP + "}Body")[0]
        payload = ET.fromstring(response(self.method, {}, relation=relation))
        result = payload.find("{" + soap.SOAP + "}Body")[0][0]
        for value in self.values:
            xml_fields(ET.SubElement(result, "{" + soap.NS + "}" + self.wrapper), value, soap.NS)
        self.after()
        return Response(url, ET.tostring(payload), "application/soap+xml")


def text_request(language=1033):
    return {"api_method": "AgendaItemTextGetByMeetingId", "api_parameters": {"meetingId": MEETING, "languageId": language}}


@pytest.mark.parametrize("case", ["ok", "wrong_type", "wrong_portal", "missing_component", "bound"])
def test_selected_meeting_type_checks_both_native_parent_components(case):
    value = sample("Meeting")
    server = Collection("MeetingGetByMeetingType", [value], "Meeting.Record")
    parent = {"Id": 7, "PortalId": PORTAL}
    if case == "wrong_type":
        parent["Id"] = 8
    elif case == "wrong_portal":
        parent["PortalId"] = MEETING
    elif case == "missing_component":
        parent.pop("PortalId")
    elif case == "bound":
        server.values *= 2
    result = create_engine(provider_transport=server).fetch(SOURCE,
        {"api_method": server.method, "api_parameters": {"Id": parent}}, bounds=Bounds(max_records=1))
    if case == "ok":
        assert result.status == "partial" and not result.errors, result.public_dict()
        assert result.data["records"][0]["identity"]["external_id"] == MEETING
        assert result.coverage["source_complete"] is False
    else:
        assert result.status == "failed" and result.data is None
        assert server.calls == (0 if case == "missing_component" else 1)


@pytest.mark.parametrize("case", ["meeting", "language", "agenda", "missing_id", "bound", "unknown"])
def test_item_text_rejects_mismatched_or_incomplete_unpaged_source(case):
    value = deepcopy(TEXT)
    if case == "meeting":
        value["MeetingId"] = PORTAL
    elif case == "language":
        value["LanguageId"] = 1036
    elif case == "agenda":
        value["AgendaType"] = None
    elif case == "missing_id":
        value.pop("Id")
    elif case == "unknown":
        value["Unmapped"] = "value"
    server = Collection("AgendaItemTextGetByMeetingId", [value], "AgendaItemText")
    if case == "bound":
        server.values *= 2
    result = create_engine(provider_transport=server).fetch(SOURCE, text_request(), bounds=Bounds(max_records=1))
    assert result.status == "failed" and result.errors and result.data is None, result.public_dict()


def test_item_text_language_id_source_fields_search_reopen_and_all_neutral_formats(tmp_path):
    server = Collection("AgendaItemTextGetByMeetingId", [TEXT], "AgendaItemText")
    owner = create_engine(storage=SQLiteStorage(tmp_path / "texts.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE, text_request())
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["original"] == TEXT
    expected = {k: TEXT[k] for k in ("MeetingId", "AgendaType", "Id", "LanguageId")}
    assert record["identity"]["external_id"] == identity_key(expected)
    parent, = record["relationships"]
    assert parent["relation"] == "agenda_item"
    assert parent["identity"]["external_id"] == identity_key(sample("AgendaItem")["Id"])
    assert all(t["provenance"]["source_language_key"] == 1033 for t in record["text"])
    assert next(t for t in record["text"] if t["field"] == "Mintues")["text"] == TEXT["Mintues"]
    assert [n.tag.split("}")[1] for n in server.parameters] == ["meetingId", "languageId"]
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    french = deepcopy(TEXT)
    french["LanguageId"] = 1036
    french["Title"] = "Texte fourni"
    other = create_engine(provider_transport=Collection(server.method, [french], "AgendaItemText")).fetch(SOURCE,text_request(1036))
    assert other.data["records"][0]["identity"]["external_id"] != record["identity"]["external_id"]
    assert owner.execute("import_bundle", {"bundle": other.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "texts.sqlite"))
    assert len(reopened.execute("search", {"query": {"phrases": ["minutes spelling"]}}).data["hits"]) == 2
    assert len(reopened.execute("search", {"query": {"record_types": ["agenda_item_text"]}}).data["hits"]) == 2
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("case", ["missing", "null", "wrong_case", "string_language"])
def test_native_text_selector_rejects_unbound_parameters_before_network(case):
    request = text_request()
    if case == "missing":
        request["api_parameters"].pop("languageId")
    elif case == "null":
        request["api_parameters"]["languageId"] = None
    elif case == "wrong_case":
        request["api_parameters"]["MeetingId"] = request["api_parameters"].pop("meetingId")
    else:
        request["api_parameters"]["languageId"] = "1033"
    server = Collection("AgendaItemTextGetByMeetingId", [TEXT], "AgendaItemText")
    result = create_engine(provider_transport=server).fetch(SOURCE, request)
    assert result.status == "failed" and not server.calls


def test_text_cancelled_after_response_is_not_completed_or_published():
    server = Collection("AgendaItemTextGetByMeetingId", [TEXT], "AgendaItemText")
    context = OperationContext()
    server.after = context.cancellation.set
    result = create_engine(provider_transport=server).fetch(SOURCE, text_request(), context=context)
    assert result.status == "cancelled" and result.data is None
