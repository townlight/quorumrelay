"""Independent pinned vendor literal-WSDL and private MediaVault session checks."""

from pathlib import Path
import hashlib
import xml.etree.ElementTree as ET

import pytest

from civic_data_connectors.models import Bounds, OperationContext, Source
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.granicus_soap import SOAP, RPC, Session
from civic_data_connectors.providers.granicus_vault import (
    NAMESPACE, VaultSession, contract, request_xml, response_value,
)


def envelope(method, content="", *, namespace=NAMESPACE):
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:r="{namespace}"><s:Body>'
            f'<r:{method}Response>{content}</r:{method}Response></s:Body></s:Envelope>').encode()


def test_literal_methods_exactly_match_pinned_vendor_wsdl():
    raw = (Path(__file__).parents[1] / "docs/capabilities/evidence/granicus-platform/SDK.asmx.wsdl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == contract()["source_wsdl_sha256"]
    wsdl = ET.fromstring(raw)
    ns = {"x": "http://www.w3.org/2001/XMLSchema", "w": "http://schemas.xmlsoap.org/wsdl/",
          "s": "http://schemas.xmlsoap.org/wsdl/soap/"}
    for name, operation in contract()["operations"].items():
        for direction, suffix in (("request", ""), ("response", "Response")):
            element = wsdl.find(f'.//x:element[@name="{name+suffix}"]', ns)
            sequence = element.find("x:complexType/x:sequence", ns)
            expected = {e.get("name"): e.get("type") for e in sequence} if sequence is not None else {}
            assert operation[direction] == expected
        assert operation["soap_action"] == wsdl.find(f'./w:binding/w:operation[@name="{name}"]/s:operation', ns).get("soapAction")


def test_literal_file_bytes_and_private_security_header():
    raw, headers = request_xml("UploadFile", {"FolderID": 11, "NewFileName": "supplied.mp4", "bytes": b"\0MP4\xff"},
        service_host="synthetic-city.granicus.com", token="synthetic-private-token", byte_limit=10000)
    root = ET.fromstring(raw)
    assert root.find(f"{{{SOAP}}}Header/{{{NAMESPACE}}}SecurityHeader/{{{NAMESPACE}}}SecurityToken").text == "synthetic-private-token"
    assert root.find(f"{{{SOAP}}}Body/{{{NAMESPACE}}}UploadFile/{{{NAMESPACE}}}bytes").text == "AE1QN P8=".replace(" ", "")
    assert headers["SOAPAction"] == '"http://granicus.com/MediaVault/SDK/UploadFile"'
    assert response_value("UploadFile", envelope("UploadFile", "<r:UploadFileResult>19</r:UploadFileResult>"), byte_limit=10000) == {"UploadFileResult": 19}


@pytest.mark.parametrize("change", [{"FolderID": True}, {"NewFileName": "bad\0name"}, {"bytes": "not-bytes"}])
def test_invalid_literal_input_fails_closed(change):
    with pytest.raises(ValueError):
        request_xml("UploadFile", {"FolderID": 11, "NewFileName": "x.mp4", "bytes": b"x", **change},
                    service_host="synthetic-city.granicus.com", token="private", byte_limit=10000)


@pytest.mark.parametrize("raw", [b'<!DOCTYPE x><x/>', b'\xff\xfe<\0!\0D\0O\0C\0T\0Y\0P\0E\0',
    envelope("StartUpload", '<r:StartUploadResult><r:nested/></r:StartUploadResult>'),
    envelope("StartUpload", '<r:Other>bad</r:Other>')])
def test_literal_response_rejects_unsafe_or_wrong_shapes(raw):
    with pytest.raises(ValueError):
        response_value("StartUpload", raw, byte_limit=10000)


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        body = ET.fromstring(kwargs["body"])
        method = list(body.find(f"{{{SOAP}}}Body"))[0].tag.rsplit("}", 1)[-1]
        if method == "Login":
            return Response(url, envelope("Login", namespace=RPC),
                set_cookie_headers=("PHPSESSID=synthetic-private-session; Path=/; Secure",))
        if method == "Logout":
            return Response(url, envelope("Logout", namespace=RPC))
        if method == "GetFolderUploadInterface":
            value = ('<interface><Host>https://synthetic-media.granicus.com</Host>'
                     '<ControlPort xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xsd:int">443</ControlPort>'
                     '</interface>')
            # Exact WSDL return parameter is independently asserted below.
            return Response(url, envelope(method, value, namespace=RPC))
        assert method == "UploadFile"
        assert url == "https://synthetic-media.granicus.com/MediaVault/SDK.asmx"
        assert "Cookie" not in kwargs["headers"]
        security = body.find(f"{{{SOAP}}}Header/{{{NAMESPACE}}}SecurityHeader")
        assert security.find(f"{{{NAMESPACE}}}ServiceHost").text == "synthetic-city.granicus.com"
        assert security.find(f"{{{NAMESPACE}}}SecurityToken").text == "synthetic-private-session"
        return Response(url, envelope(method, '<r:UploadFileResult>19</r:UploadFileResult>'))


def test_private_current_session_and_exact_configured_vault_origin():
    from civic_data_connectors.providers.granicus_soap import contract as platform_contract
    assert set(platform_contract()["operations"]["GetFolderUploadInterface"]["response"]) == {"interface"}
    source = Source("granicus", "https://synthetic-city.granicus.com/SDK/User/index.php", "//synthetic-city.granicus.com")
    config = {"username": "synthetic-user", "password": "synthetic-password", "tenant": "test-app",
              "origin": "https://synthetic-city.granicus.com", "namespace": source.namespace,
              "media_origin": "https://synthetic-media.granicus.com"}
    transport = Transport()
    context = OperationContext(tenant="test-app", credentials={"granicus": config})
    platform = Session(source, context, Bounds(), transport)
    vault = VaultSession(platform, 11)
    result = vault.call("UploadFile", {"FolderID": 11, "NewFileName": "provided.mp4", "bytes": b"synthetic-mp4"})
    assert result == {"UploadFileResult": 19} and "private" not in str(result)
    vault.close()
    assert vault._token is None
    platform.close()
    assert list(platform.jar) == []
    assert len(transport.calls) == 4


@pytest.mark.parametrize("origin", ["http://synthetic-media.granicus.com", "https://other.granicus.com", "https://synthetic-media.granicus.com:8443"])
def test_vault_origin_mismatch_never_sends_private_token(origin):
    source = Source("granicus", "https://synthetic-city.granicus.com/SDK/User/index.php", "//synthetic-city.granicus.com")
    config = {"username": "synthetic-user", "password": "synthetic-password", "tenant": "test-app",
              "origin": "https://synthetic-city.granicus.com", "namespace": source.namespace, "media_origin": origin}
    transport = Transport()
    context = OperationContext(tenant="test-app", credentials={"granicus": config})
    platform = Session(source, context, Bounds(), transport)
    with pytest.raises(ValueError, match="could not be verified"):
        VaultSession(platform, 11).call("UploadFile", {"FolderID": 11, "NewFileName": "a.mp4", "bytes": b"x"})
    assert transport.calls == [platform.url, platform.url]
    platform.close()
