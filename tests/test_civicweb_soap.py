"""Independent synthetic examples follow pinned CivicWeb WSDL/2014 guide fields."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from civic_data_connectors.models import Bounds, OperationContext, Source
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.civicweb_soap import (
    NS, SOAP, PublicClient, contract, request_xml, response_value,
)


def envelope(method, result):
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns="{NS}"><s:Body>'
            f'<{method}Response><{method}Result>{result}</{method}Result>'
            f'</{method}Response></s:Body></s:Envelope>').encode()


CHILDREN = envelope("GetChildList", '<ID>0</ID><Nodes><DocumentTreeNodeInformation>'
    '<ID>71</ID><Name>Agenda &amp; Minutes</Name><Folder>true</Folder>'
    '<IsPublic>true</IsPublic><CanUpdate>false</CanUpdate>'
    '<Future>preserved</Future></DocumentTreeNodeInformation></Nodes>')


def test_independent_vendor_wsdl_fields_actions_and_known_discrepancies():
    root_path = Path(__file__).parents[1] / "docs/capabilities/evidence/civicweb-filepro"
    raw = (root_path / "trail-Document.wsdl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == contract()["source_wsdl_sha256"]
    for source in json.loads((root_path / "source.json").read_bytes())["sources"]:
        captured = (root_path / source["file"]).read_bytes()
        assert len(captured) == source["bytes"]
        assert hashlib.sha256(captured).hexdigest() == source["sha256"]
    ns = {"x": "http://www.w3.org/2001/XMLSchema", "w": "http://schemas.xmlsoap.org/wsdl/",
          "s": "http://schemas.xmlsoap.org/wsdl/soap/"}
    for filename in ("trail-Document.wsdl", "livetest-Document.wsdl"):
        root = ET.fromstring((root_path / filename).read_bytes())
        for name, operation in contract()["operations"].items():
            for direction, suffix in (("request", ""), ("response", "Response")):
                fields = root.findall(f'.//x:schema/x:element[@name="{name}{suffix}"]/'
                                      'x:complexType/x:sequence/x:element', ns)
                assert [(x.get("name"), x.get("type").split(":")[-1]) for x in fields] == [
                    (x["name"], x["type"]) for x in operation[direction]]
            action = root.find(f'.//w:binding/w:operation[@name="{name}"]/s:operation', ns)
            assert action.get("soapAction") == operation["soap_action"]
        for name, model in contract()["types"].items():
            fields = root.findall(f'.//x:complexType[@name="{name}"]/x:sequence/x:element', ns)
            assert [(x.get("name"), x.get("type").split(":")[-1]) for x in fields] == [
                (x["name"], x["type"]) for x in model]
    # Guide summary says plural Results/controlID; actual WSDL and SOAP use these.
    assert "GetSearchResultsDetails" not in contract()["operations"]
    assert contract()["operations"]["GetChildList"]["request"][-1]["name"] == "controlId"
    assert "GetSearchResultsBySearchCriteria" not in contract()["operations"]  # absent current WSDL


def test_vendor_child_request_and_response_unknown_fields():
    raw, headers = request_xml("GetChildList", dict(id=0, path="", includeDocuments=True,
        documentProvider="iCompass.CivicWeb.Items.DocumentProvider", controlId=""), byte_limit=4096)
    node = ET.fromstring(raw).find(f"{{{SOAP}}}Body/{{{NS}}}GetChildList")
    assert [x.tag.split("}")[-1] for x in node] == [
        "id", "path", "includeDocuments", "documentProvider", "controlId"]
    assert headers["SOAPAction"] == '"http://civicweb.net/GetChildList"'
    value = response_value("GetChildList", CHILDREN, byte_limit=4096)
    assert value["ID"] == 0
    assert value["Nodes"][0]["Name"] == "Agenda & Minutes"
    assert value["Nodes"][0]["Folder"] is True
    assert "preserved" in value["Nodes"][0]["Future"]["xml"]


def test_original_bytes_html_and_nil_are_distinct():
    raw = envelope("GetOriginalFile", '<Html>&lt;p&gt;Agenda&lt;/p&gt;</Html>'
                   '<FileBytes>JVBERi0=</FileBytes><Extension>.pdf</Extension>')
    assert response_value("GetOriginalFile", raw, byte_limit=4096) == {
        "Html": "<p>Agenda</p>", "FileBytes": "JVBERi0=", "Extension": ".pdf"}
    raw = envelope("GetOriginalFile", '<Html></Html><FileBytes></FileBytes><Extension></Extension>')
    assert response_value("GetOriginalFile", raw, byte_limit=4096)["FileBytes"] == ""
    raw = (f'<s:Envelope xmlns:s="{SOAP}" xmlns="{NS}" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
           '<s:Body><GetOriginalFileResponse><GetOriginalFileResult i:nil="true"/>'
           '</GetOriginalFileResponse></s:Body></s:Envelope>').encode()
    assert response_value("GetOriginalFile", raw, byte_limit=4096) is None


def test_search_request_escapes_text_and_limits_document_batches():
    params = dict(exactPhrase="Council & <Budget>", allWords="", atLeastOneWord="",
                  wordsInProximity1="", wordsInProximity2="", wordsNotIncluded="")
    raw, _ = request_xml("GetSearchResultDetails", dict(searchResultsSubset=[71, 72], **params), byte_limit=4096)
    node = ET.fromstring(raw).find(f"{{{SOAP}}}Body/{{{NS}}}GetSearchResultDetails")
    assert node.findtext(f"{{{NS}}}exactPhrase") == "Council & <Budget>"
    with pytest.raises(ValueError, match="50"):
        request_xml("GetSearchResultDetails", dict(searchResultsSubset=list(range(1, 52)), **params), byte_limit=4096)


@pytest.mark.parametrize("method,parameters", [
    ("DeleteDocument", {"id": 1}), ("LoginUser", {"userName": "x", "password": "x"}),
    ("GetOriginalFile", {"id": True}), ("GetOriginalFile", {"id": 0}),
    ("GetOriginalFile", {"id": 2**31}), ("GetOriginalFile", {"id": 1, "secret": "x"}),
    ("GetChildList", dict(id=0, path="private", includeDocuments=True,
                         documentProvider="iCompass.CivicWeb.Items.DocumentProvider", controlId="")),
])
def test_invalid_or_unmapped_requests_fail_closed(method, parameters):
    with pytest.raises(ValueError):
        request_xml(method, parameters, byte_limit=4096)


@pytest.mark.parametrize("raw", [
    b'<!DOCTYPE x [<!ENTITY x "bad">]><x/>',
    '<!DOCTYPE x><x/>'.encode("utf-16"),
    envelope("GetTitle", "wrong method"),
    envelope("GetOriginalFile", '<FileBytes>bad!</FileBytes>'),
    envelope("GetOriginalFile", '<Extension>.pdf</Extension><Extension>.txt</Extension>'),
    envelope("GetChildList", '<Nodes/>'),  # missing required parent ID
    envelope("GetOriginalFile", '<FileBytes xmlns="https://foreign.example">eA==</FileBytes>'),
])
def test_hostile_or_invalid_responses_fail_closed(raw):
    with pytest.raises(ValueError):
        response_value("GetOriginalFile" if b"GetChildList" not in raw else "GetChildList", raw, byte_limit=4096)


def test_public_client_exact_endpoint_no_login_redirect_or_cookie_and_cumulative_bounds():
    class Network:
        calls = []

        def request(self, url, **kwargs):
            self.calls.append((url, kwargs))
            assert kwargs["allow_redirects"] is False
            assert set(kwargs["headers"]) == {"SOAPAction", "Content-Type"}
            return Response(url, CHILDREN, "text/xml", set_cookie_headers=("CurrentSession=private",))

    network = Network()
    client = PublicClient(Source("civicweb", "https://synthetic.civicweb.net/Portal/"),
                          Bounds(parser_bytes=4096, transfer_bytes=1000), OperationContext(), network)
    params = dict(id=0, path="", includeDocuments=True,
        documentProvider="iCompass.CivicWeb.Items.DocumentProvider", controlId="")
    value, _ = client.call("GetChildList", params)
    assert value["ID"] == 0
    assert network.calls[0][0] == "https://synthetic.civicweb.net/Global/WebServices/Document.asmx"
    with pytest.raises(ValueError):
        client.call("GetChildList", params)
    assert "private" not in repr(client.__dict__)


def test_client_cancellation_and_response_endpoint_identity():
    class Network:
        def request(self, url, **kwargs):
            return Response(url + "?other", envelope("GetTitle", "Agenda"), "text/xml")

    ctx = OperationContext()
    client = PublicClient(Source("civicweb", "https://synthetic.civicweb.net/"), Bounds(), ctx, Network())
    with pytest.raises(ValueError, match="civicweb_soap_unavailable"):
        client.call("GetTitle", {"id": 1})
    ctx.cancellation.set()
    with pytest.raises(ValueError, match="cancelled"):
        client.call("GetTitle", {"id": 1})
