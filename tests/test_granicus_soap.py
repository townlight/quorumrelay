"""Synthetic SOAP execution uses the pinned vendor WSDL, never a vendor account."""

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from civic_data_connectors.providers.granicus_soap import (
    ENC, RPC, SOAP, Session, contract, request_xml, response_value,
)
from civic_data_connectors.models import Bounds, OperationContext, Source
from civic_data_connectors.providers.contracts import Response


def test_exact_pinned_vendor_contract():
    raw = (Path(__file__).parents[1] / "docs/capabilities/evidence/granicus-platform/index.php.wsdl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == contract()["source_wsdl_sha256"]
    root = ET.fromstring(raw)
    ns = {"w": "http://schemas.xmlsoap.org/wsdl/", "x": "http://www.w3.org/2001/XMLSchema"}
    for name, operation in contract()["operations"].items():
        for direction, suffix in (("request", "Request"), ("response", "Response")):
            message = root.find(f'./w:message[@name="{name}{suffix}"]', ns)
            assert {p.get("name"): p.get("type") for p in message} == operation[direction]
        binding = root.find(f'./w:binding/w:operation[@name="{name}"]', ns)
        assert binding[0].get("soapAction") == operation["soap_action"]
    event = root.find('.//x:complexType[@name="EventData"]', ns)
    assert {p.get("name"): p.get("type") for p in event.find("x:all", ns)} == contract()["types"]["EventData"]["fields"]
    assert "DeleteUser" not in contract()["operations"]


def test_vendor_event_request_types_and_xml_escaping():
    raw, headers = request_xml("CreateEvent", {"EventData": {
        "Name": "Council <Budget> & Finance", "Record": False, "Duration": 30,
        "StartTime": "2026-11-12T18:00:00-07:00", "Views": [1, 2]}}, byte_limit=4096)
    root = ET.fromstring(raw)
    event = root.find(f"{{{SOAP}}}Body/{{{RPC}}}CreateEvent/EventData")
    assert event.findtext("Name") == "Council <Budget> & Finance"
    assert event.findtext("Record") == "false"
    assert event.find("Views").get(f"{{{ENC}}}arrayType") == "xsd:int[2]"
    assert headers["SOAPAction"] == '"urn:UserSDK#UserWebservice#CreateEvent"'


@pytest.mark.parametrize("operation,parameters", [
    ("DeleteUser", {"UserID": 1}), ("GetEvent", {"ID": 1}),
    ("GetEvent", {"EventID": True}), ("GetEvent", {"EventID": 2**31}),
    ("UpdateEvent", {"event": {"InventedField": "x"}}),
    ("UploadEventAgendaDocument", {"EventID": 1, "Document": {"FileContents": "!!!"}}),
])
def test_request_rejects_wrong_contract(operation, parameters):
    with pytest.raises(ValueError):
        request_xml(operation, parameters, byte_limit=4096)


def response(body):
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:r="{RPC}" xmlns:e="{ENC}" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<s:Body>{body}</s:Body></s:Envelope>').encode()


def test_synthetic_rpc_readback_preserves_unknown_fields_and_references():
    raw = response('<r:GetEventResponse><event href="#event1"/></r:GetEventResponse>'
                   '<multiRef id="event1"><ID xsi:type="xsd:int">7</ID>'
                   '<Name>Budget</Name><VendorFutureField>retained</VendorFutureField>'
                   '<Views e:arrayType="xsd:int[2]"><item xsi:type="xsd:int">1</item>'
                   '<item xsi:type="xsd:int">2</item></Views></multiRef>')
    value = response_value("GetEvent", raw, byte_limit=4096)["event"]
    assert value == {"ID": 7, "Name": "Budget", "VendorFutureField": "retained", "Views": [1, 2]}


@pytest.mark.parametrize("body", [
    '<r:GetEventResponse><event href="https://example.com/secret"/></r:GetEventResponse>',
    '<r:GetEventResponse><event href="#x"/></r:GetEventResponse><ref id="x" href="#x"/>',
    '<r:GetClipResponse><clip/></r:GetClipResponse>',
    '<s:Fault><faultstring>private provider details</faultstring></s:Fault>',
])
def test_response_rejects_external_cycle_wrong_method_and_fault(body):
    with pytest.raises(ValueError):
        response_value("GetEvent", response(body), byte_limit=4096)


def test_xml_and_transfer_limits():
    with pytest.raises(ValueError):
        request_xml("GetEvent", {"EventID": 1}, byte_limit=1)
    with pytest.raises(ValueError):
        response_value("GetEvent", b'<!DOCTYPE x [<!ENTITY x "bad">]><x/>', byte_limit=4096)
    with pytest.raises(ValueError):
        response_value("GetEvent", '<!DOCTYPE x [<!ENTITY x "bad">]><x/>'.encode("utf-16"), byte_limit=4096)
    with pytest.raises(ValueError):
        response_value("GetEvent", response('<r:GetEventResponse><event/></r:GetEventResponse>'), byte_limit=1)


def setup_session(transport, **policy):
    source = Source("granicus", "https://synthetic-city.granicus.com/SDK/User/index.php", "synthetic-city")
    config = {"username": "synthetic-user", "password": "synthetic-password",
              "tenant": "test-app", "origin": "https://synthetic-city.granicus.com",
              "namespace": "synthetic-city", **policy}
    context = OperationContext(tenant="test-app", credentials={"granicus": config},
                               allowed_namespaces=("synthetic-city",))
    return Session(source, context, Bounds(parser_bytes=4096, transfer_bytes=8192), transport)


def test_private_login_cookie_and_readback_use_same_guarded_transport():
    class Transport:
        def __init__(self):
            self.actions = []

        def request(self, url, **kwargs):
            action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
            self.actions.append(action)
            assert kwargs["allow_redirects"] is False
            assert kwargs["allowed_origins"] == ("https://synthetic-city.granicus.com",)
            if action == "Login":
                assert b"synthetic-password" in kwargs["body"]
                return Response(url, response('<r:LoginResponse/>'), set_cookie_headers=("SID=private; Path=/; Secure",))
            assert kwargs["headers"]["Cookie"] == "SID=private"
            assert b"synthetic-password" not in kwargs["body"]
            body = ('<r:GetEventResponse><event><ID xsi:type="xsd:int">7</ID><Name>Budget</Name>'
                    '</event></r:GetEventResponse>') if action == "GetEvent" else '<r:LogoutResponse/>'
            return Response(url, response(body))

    transport = Transport()
    session = setup_session(transport)
    result, captured = session.call("GetEvent", {"EventID": 7})
    assert result["event"]["ID"] == 7
    assert b"synthetic-password" not in captured and b"SID=" not in captured
    session.close()
    assert transport.actions == ["Login", "GetEvent", "Logout"]
    assert list(session.jar) == []


@pytest.mark.parametrize("policy", [{"tenant": "other-app"}, {"origin": "https://another.granicus.com"},
                                    {"namespace": "other-account"}])
def test_credential_scope_mismatch_never_contacts_transport(policy):
    with pytest.raises(ValueError, match="policy"):
        setup_session(object(), **policy)
