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


class SupportingTransport(Transport):
    def request(self, url, **kwargs):
        import base64
        method = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        # Parameters and wrapper names are the pinned vendor WSDL signatures.
        bodies = {
            "GetClipCaptions": "<captions>Entire supplied caption text</captions>",
            "GetEventVideoLocation": "<url>https://synthetic-city.granicus.com/event.m3u8</url>",
            "GetClipVideoLocation": "<url>https://synthetic-city.granicus.com/clip.mp4</url>",
            "GetMetaDataVideoLocation": "<url>https://synthetic-city.granicus.com/clip.mp4?start=12</url>",
            "FetchAttachment": "<Attachment><Description>Agenda attachment</Description><Location>retained raw</Location>"
                "<FileExtension>pdf</FileExtension><FileContents>" + base64.b64encode(b"%PDF-synthetic").decode() + "</FileContents></Attachment>",
            "GetClipMinutesDocuments": '<MinutesDocuments e:arrayType="g:MinutesDocumentData[1]"><item><UID>minutes-uid</UID>'
                '<Name>Approved Minutes</Name><Type>pdf</Type><Published xsi:type="xsd:boolean">true</Published>'
                '<Default xsi:type="xsd:boolean">false</Default></item></MinutesDocuments>',
        }
        if method in bodies:
            self.calls.append(method)
            return Response(url, envelope(method, bodies[method]))
        return super().request(url, **kwargs)


def test_supporting_reads_preserve_supplied_text_bytes_locations_and_relationships():
    import hashlib
    engine = create_engine(provider_transport=SupportingTransport())
    for resource in ("clip_captions", "event_video", "clip_video", "item_video", "attachment", "clip_minutes"):
        result = engine.execute("fetch", {"source": SOURCE, "external_id": "7", "api_resource": resource}, context=context())
        assert result.status == "partial" and not result.errors, (resource, result.errors)
        record = result.data["records"][0]
        assert record["identity"]["parent"]["external_id"] == "7"
        assert result.data["capture"]["content_base64"]
        if resource == "clip_captions":
            assert record["text"][0]["text"] == "Entire supplied caption text"
        elif resource == "attachment":
            assert record["normalized"]["document_sha256"] == hashlib.sha256(b"%PDF-synthetic").hexdigest()
            assert record["original"]["Location"] == "retained raw"
        elif resource == "clip_minutes":
            assert record["identity"]["external_id"] == "minutes-uid"
            assert record["original"]["Published"] is True
        else:
            assert record["normalized"]["recordings"][0]["url"].startswith("https://synthetic-city.granicus.com/")


def test_generic_sdk_caption_method_uses_documented_whole_transcript():
    from civic_data_connectors import Source
    result = create_engine(provider_transport=SupportingTransport()).fetch_captions(
        Source.from_dict(SOURCE), "7", context=context())
    assert result.status == "partial" and not result.errors
    assert result.data["records"][0]["identity"]["record_type"] == "caption"

GUID = "2e70d279-5765-4f42-bd56-58b3d5208a3c"


class AliasTransport(Transport):
    def __init__(self, wrong_uid=False):
        super().__init__()
        self.wrong_uid = wrong_uid

    def request(self, url, **kwargs):
        import xml.etree.ElementTree as ET
        method = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if method in {"Login", "Logout"}:
            return super().request(url, **kwargs)
        self.calls.append(method)
        assert kwargs["allow_redirects"] is False
        request = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}{method}")
        # Parameter names follow the pinned SDK's published signatures.
        key = ("MetaDataUID" if method == "GetMetaDataByUID" else
               "EventUID" if "Event" in method and method.endswith("ByUID") else "ClipUID")
        if method.endswith("ByUID"):
            assert request.findtext(key) == GUID
        elif method in {"GetEventsByForeignID", "GetClipsByForeignID"}:
            assert request.findtext("ForeignID") == "123"
        elif method == "GetEvents":
            assert not list(request)
        uid = "a0000000-0000-0000-0000-000000000000" if self.wrong_uid else GUID
        item = f'<ID xsi:type="xsd:int">7</ID><UID>{uid}</UID><ForeignID xsi:type="xsd:int">123</ForeignID><Name>Supplied alias</Name>'
        if method in {"GetEventByUID", "GetClipByUID", "GetMetaDataByUID"}:
            field = "event" if method == "GetEventByUID" else "clip" if method == "GetClipByUID" else "MetaData"
            payload = f'<{field}>{item}</{field}>'
        elif method == "GetClipCaptionsByUID":
            payload = "<captions>Whole supplied caption text</captions>"
        else:
            field = "events" if method.startswith("GetEvents") else "clips" if method == "GetClipsByForeignID" else "metadata"
            payload = f'<{field} e:arrayType="g:MetaDataData[1]"><item>{item}</item></{field}>'
        return Response(url, envelope(method, payload))


def test_documented_uid_and_foreign_id_aliases_preserve_numeric_canonical_identity():
    resources = ["event_uid", "clip_uid", "agenda_item_uid", "event_items_uid", "clip_items_uid",
                 "clip_indices_uid", "clip_captions_uid", "events_all", "events_foreign_id", "clips_foreign_id"]
    for resource in resources:
        transport = AliasTransport()
        result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE,
            "api_resource": resource, "external_id": "123" if "foreign_id" in resource else GUID}, context=context())
        assert result.status == "partial" and not result.errors, (resource, result.errors)
        record = result.data["records"][0]
        assert record["identity"]["external_id"] == ("clip_captions:7" if resource == "clip_captions_uid" else "7")
        if resource in {"event_items_uid", "clip_items_uid", "clip_indices_uid", "clip_captions_uid"}:
            assert record["identity"]["parent"]["external_id"] == "7"
            assert transport.calls[1] in {"GetEventByUID", "GetClipByUID"}
            assert result.data["extensions"]["parent_resolution"]["record"]["UID"] == GUID
            assert result.data["extensions"]["parent_resolution"]["content_base64"]
        assert result.coverage["catalog_complete"] is False


def test_uid_identity_mismatch_fails_without_returning_unverified_record():
    result = create_engine(provider_transport=AliasTransport(wrong_uid=True)).execute("fetch", {
        "source": SOURCE, "api_resource": "event_uid", "external_id": GUID}, context=context())
    assert result.status == "failed" and result.errors
    assert not result.data.get("records")
