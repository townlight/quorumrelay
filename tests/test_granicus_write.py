"""Real coordinator transactions with an independently WSDL-shaped SOAP server."""

from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.providers.granicus_write import GranicusWriteAdapter
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_transport import PublicWriteTransport, WriteResponse
from civic_data_connectors.writes import register

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
RPC = "urn:UserSDK"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ENC = "http://schemas.xmlsoap.org/soap/encoding/"
SOURCE = {"provider": "granicus", "url": "https://synthetic-city.granicus.com/SDK/User/index.php",
          "namespace": "//synthetic-city.granicus.com", "input_format": "granicus-platform-soap-xml"}
WSDL = ET.fromstring((Path(__file__).parents[1] / "docs/capabilities/evidence/granicus-platform/index.php.wsdl").read_bytes())
NS = {"x": "http://www.w3.org/2001/XMLSchema"}


def model_fields(model_name="EventData"):
    model = WSDL.find(f'.//x:complexType[@name="{model_name}"]', NS)
    return {field.get("name"): field.get("type") for field in model.find("x:all", NS)}


class Network:
    mock = True

    def __init__(self, model_name="EventData", read_method="GetEvent", write_method="UpdateEvent", parameter="event"):
        self.model_name, self.read_method = model_name, read_method
        self.write_method, self.parameter = write_method, parameter
        self.values = {}
        for key, typ in model_fields(model_name).items():
            self.values[key] = (0 if typ == "xsd:int" else False if typ == "xsd:boolean" else
                                "2026-11-12T18:00:00Z" if typ == "xsd:dateTime" else
                                [] if typ.startswith("ns5:") else "")
        self.values.update(ID=7, Name="Before", LastModified="2026-11-12T17:00:00Z")
        self.mutations = 0
        self.lose_response = False

    def _record(self, event):
        for key, typ in model_fields(self.model_name).items():
            field = ET.SubElement(event, key)
            value = self.values[key]
            if isinstance(value, list):
                field.set(f"{{{ENC}}}arrayType", "xsd:string[0]")
            else:
                field.set(f"{{{XSI}}}type", typ)
                field.text = str(value).lower() if type(value) is bool else str(value)

    def send(self, url, **kwargs):
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        body = ET.Element(f"{{{SOAP}}}Envelope")
        response = ET.SubElement(ET.SubElement(body, f"{{{SOAP}}}Body"), f"{{{RPC}}}{action}Response")
        if action != "Login":
            assert kwargs["headers"].get("Cookie") == "SID=synthetic-private-session"
        if action == self.read_method:
            event = ET.SubElement(response, self.parameter)
            self._record(event)
        elif action == "GetEventsByForeignID":
            records = ET.SubElement(response, "events", {f"{{{ENC}}}arrayType": "g:EventData[0]"})
            request = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}GetEventsByForeignID")
            if str(self.values["ForeignID"]) == request.findtext("ForeignID"):
                self._record(ET.SubElement(records, "item"))
        elif action == "CreateEvent":
            sent = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}CreateEvent/EventData")
            assert set(child.tag for child in sent) == set(model_fields())
            assert sent.findtext("ID") == "0"
            for key, typ in model_fields().items():
                field = sent.find(key)
                value = field.text or ""
                self.values[key] = (int(value) if typ == "xsd:int" else value == "true" if typ == "xsd:boolean"
                                    else [] if typ.startswith("ns5:") else value)
            self.values.update(ID=8, UID="synthetic-provider-guid", LastModified="2026-11-12T19:00:00Z")
            self.mutations += 1
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("synthetic create response loss")
            ET.SubElement(response, "EventID", {f"{{{XSI}}}type": "xsd:int"}).text = "8"
        elif action == self.write_method:
            sent = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}{action}/{self.parameter}")
            assert set(child.tag for child in sent) == set(model_fields(self.model_name))
            assert sent.findtext("ID") == "7"
            self.values["Name"] = sent.findtext("Name")
            self.values["LastModified"] = "2026-11-12T19:00:00Z"
            self.mutations += 1
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("synthetic failure after mutation")
        else:
            assert action in {"Login", "Logout"}
        return WriteResponse(200, ET.tostring(body), set_cookie_headers=(
            ("SID=synthetic-private-session; Path=/; Secure",) if action == "Login" else ()))


def setup(tmp_path, network=None):
    network = network or Network()
    engine = Engine(storage=SQLiteStorage(tmp_path / "soap-writes.sqlite"))
    register(engine, {"granicus": GranicusWriteAdapter(network)})
    context = OperationContext(principal="actor", client_id="sdk", tenant="test-app",
        authorization=frozenset({"write:plan", "write:commit"}), credentials={"granicus": {
        "username": "synthetic-user", "password": "synthetic-password", "tenant": "test-app",
        "origin": "https://synthetic-city.granicus.com", "namespace": SOURCE["namespace"],
        "permissions": ["event:update"], "resource_ids": ["7"]}})
    change = {"key": "rename", "entity": "event", "operation": "update", "resource_id": "7", "fields": {"Name": "After"}}
    return engine, network, context, change


def plan(engine, context, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "completed", result.errors
    serialized = json.dumps(result.data)
    assert "synthetic-password" not in serialized and "synthetic-user" not in serialized
    assert "synthetic-private-session" not in serialized
    return {"plan_id": result.data["plan_id"], "plan_hash": result.data["plan_hash"]}


def test_exact_plan_commit_readback_and_duplicate_replay(tmp_path):
    engine, network, context, change = setup(tmp_path)
    request = plan(engine, context, change)
    assert network.mutations == 0
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "completed", result.errors
    assert result.data["items"][0]["readback"]["Name"] == "After"
    assert "synthetic-private-session" not in json.dumps(result.public_dict())
    for collection in ("write_plans", "receipts"):
        stored = engine.storage.get(collection, request["plan_id"], scope=context.scope)
        assert "synthetic-private-session" not in json.dumps(stored.value)
    assert engine.execute("commit_write", request, context=context).status == "completed"
    assert network.mutations == 1


def test_conflict_and_revoked_scope_do_not_mutate(tmp_path):
    engine, network, context, change = setup(tmp_path)
    request = plan(engine, context, change)
    network.values["Name"] = "Concurrent"
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "failed" and result.errors[0].code == "conflict"
    assert network.mutations == 0
    engine, network, context, change = setup(tmp_path / "revoked")
    request = plan(engine, context, change)
    context.credentials["granicus"]["resource_ids"] = []
    assert engine.execute("commit_write", request, context=context).status == "failed"
    assert network.mutations == 0


def test_lost_mutation_response_reconciles_without_repeat(tmp_path):
    engine, network, context, change = setup(tmp_path)
    request = plan(engine, context, change)
    network.lose_response = True
    assert engine.execute("commit_write", request, context=context).status == "partial"
    assert engine.execute("commit_write", request, context=context).status == "completed"
    assert network.mutations == 1


def test_unknown_model_fields_are_not_silently_dropped(tmp_path):
    engine, network, context, change = setup(tmp_path)
    change = deepcopy(change)
    change["fields"]["NotInVendorModel"] = "x"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed" and network.mutations == 0


@pytest.mark.parametrize("lose_response", [False, True])
def test_create_full_event_model_and_foreign_id_reconciliation(tmp_path, lose_response):
    engine, network, context, change = setup(tmp_path)
    context.credentials["granicus"].update(permissions=["event:create"], foreign_ids=["9001"])
    fields = {**deepcopy(network.values), "ID": 0, "UID": "", "ForeignID": 9001, "Name": "Created"}
    change.update(operation="create", resource_id=None, fields=fields)
    request = plan(engine, context, change)
    network.lose_response = lose_response
    result = engine.execute("commit_write", request, context=context)
    assert result.status == ("partial" if lose_response else "completed"), result.errors
    if lose_response:
        result = engine.execute("commit_write", request, context=context)
    assert result.status == "completed" and network.mutations == 1
    assert result.data["items"][0]["resource_id"] == 8
    assert result.data["items"][0]["readback"]["Name"] == "Created"


def test_private_write_response_cookies_remain_transport_only(monkeypatch):
    from civic_data_connectors import fetch
    from civic_data_connectors.write_adapters import sanitize

    def request(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return fetch.PublicResponse(url, b"<response/>", "text/xml", 200, {}, ("SID=private; Secure",))

    monkeypatch.setattr(fetch, "request_public_response", request)
    response = PublicWriteTransport().send(SOURCE["url"], method="POST", body=b"x", headers={},
                                          byte_limit=4096, deadline_seconds=1)
    assert response.set_cookie_headers == ("SID=private; Secure",)
    assert "SID=" not in repr(response)
    assert sanitize({"body": "a-private-password", "password": "a-private-password"},
                    {"password": "a-private-password"}) == {"body": "[REDACTED]"}


@pytest.mark.parametrize("entity,model,read_method,write_method,parameter", [
    ("recording", "ClipData", "GetClip", "UpdateClip", "clip"),
    ("agenda_item", "MetaDataData", "GetMetaData", "UpdateMetaData", "MetaData"),
])
def test_related_full_model_updates_use_documented_methods(tmp_path, entity, model, read_method, write_method, parameter):
    network = Network(model, read_method, write_method, parameter)
    engine, _, context, change = setup(tmp_path, network)
    context.credentials["granicus"].update(permissions=[f"{entity}:update"], meeting_ids=["11"])
    change.update(entity=entity, meeting_id="11")
    request = plan(engine, context, change)
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "completed", result.errors
    assert result.data["items"][0]["readback"]["Name"] == "After"
    assert network.mutations == 1
