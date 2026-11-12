"""Actual engine paths over synthetic responses shaped by official Granicus WSDL."""

from xml.sax.saxutils import escape

from civic_data_connectors import create_engine
from civic_data_connectors.models import OperationContext
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.granicus_soap import ENC, RPC, SOAP

SOURCE = {"provider": "granicus", "url": "https://synthetic-city.granicus.com/SDK/User/index.php",
          "input_format": "granicus-platform-soap-xml"}
NAMESPACE = "//synthetic-city.granicus.com"


def context():
    return OperationContext(tenant="test-app", credentials={"granicus": {
        "username": "synthetic-user", "password": "synthetic-password", "tenant": "test-app",
        "origin": "https://synthetic-city.granicus.com", "namespace": NAMESPACE}})


def envelope(method, payload):
    return (f'<s:Envelope xmlns:s="{SOAP}" xmlns:r="{RPC}" xmlns:e="{ENC}" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<s:Body><r:{method}Response>{payload}</r:{method}Response></s:Body></s:Envelope>').encode()


def event(identity=7):
    return (f'<ID xsi:type="xsd:int">{identity}</ID><Name>Council Budget</Name>'
            '<MeetingTime>2026-11-12T18:00:00-07:00</MeetingTime>'
            '<LastModified>2026-11-11T10:00:00Z</LastModified><VendorFuture>retained</VendorFuture>')


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        method = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        self.calls.append(method)
        assert kwargs["allow_redirects"] is False
        if method in {"Login", "Logout"}:
            payload = ""
        elif method == "GetEvent":
            payload = "<event>" + event() + "</event>"
        elif method == "GetEventsByDateRange":
            assert b"StartDate" in kwargs["body"] and b"EndDate" in kwargs["body"]
            payload = '<events e:arrayType="g:EventData[2]"><item>' + event() + '</item><item>' + event(8) + '</item></events>'
        elif method == "GetEventMetaData":
            payload = ('<metadata e:arrayType="g:MetaDataData[1]"><item><ID xsi:type="xsd:int">91</ID>'
                       '<Name>Budget motion</Name><TimeStamp xsi:type="xsd:int">120</TimeStamp>'
                       '<Payload>' + escape("<motion>Supplied text</motion>") + '</Payload></item></metadata>')
        else:
            raise AssertionError(method)
        return Response(url, envelope(method, payload))


def test_engine_fetch_preserves_identity_revision_unknowns_and_xml_capture():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE, "external_id": "7"}, context=context())
    assert result.status == "partial" and not result.errors
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "7"
    assert record["original"]["VendorFuture"] == "retained"
    assert record["source_revision"]["value"] == "2026-11-11T10:00:00Z"
    assert result.data["capture"]["content_base64"]
    assert transport.calls == ["Login", "GetEvent", "Logout"]


def test_engine_discovery_exact_vendor_dates_local_limit_and_no_paging_claim():
    result = create_engine(provider_transport=Transport()).execute("discover", {"source": SOURCE,
        "api_parameters": {"StartDate": "2026-11-01T00:00:00-07:00", "EndDate": "2026-11-30T23:59:59-07:00"},
        "bounds": {"max_records": 1}}, context=context())
    assert result.status == "partial" and not result.errors
    assert len(result.data["records"]) == 1 and result.coverage["truncated"]
    assert result.coverage["catalog_complete"] is False and result.coverage["checkpoint"] is None


def test_engine_metadata_parent_and_supplied_motion_payload():
    result = create_engine(provider_transport=Transport()).execute("fetch", {"source": SOURCE, "external_id": "7",
        "api_resource": "event_items"}, context=context())
    assert result.status == "partial" and not result.errors
    record = result.data["records"][0]
    assert record["identity"]["parent"]["external_id"] == "7"
    assert record["normalized"]["timestamp_seconds"] == 120
    assert record["original"]["Payload"] == "<motion>Supplied text</motion>"


def test_engine_type_filter_and_unknown_body_are_explicit():
    engine = create_engine(provider_transport=Transport())
    result = engine.execute("fetch", {"source": {**SOURCE, "body": "Council"}, "external_id": "7"}, context=context())
    assert result.status == "partial" and result.coverage["unknown_body_records"] == ["7"]
    result = engine.execute("fetch", {"source": SOURCE, "external_id": "7", "record_types": ["agenda_item"]}, context=context())
    assert result.status == "partial" and result.data["records"] == []
