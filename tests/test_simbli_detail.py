"""Captured anonymous JSON stays distinct from privileged/opaque page controls."""

import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.simbli_detail import DETAIL, ITEMS

ROOT = Path(__file__).parent / "fixtures" / "simbli-detail"
SOURCE = {"provider": "simbli", "url": "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36031063&MID=4942"}
FORM = b"""var isUserLoggedIn='False';var did='36031063';var meetingID='4942';var enCuUID='';
var enDID='synthetic-district';var enMeetingID='synthetic-meeting';
var encrTZ='synthetic-timezone';var sToken='synthetic-private-control';var enAjSFlag='';"""


class Transport:
    def __init__(self, page=FORM, fail=None):
        self.calls, self.page, self.fail = [], page, fail

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == ("https://simbli.eboardsolutions.com",)
        path = urlsplit(url).path
        if path == "/SB_Meetings/ViewMeeting.aspx":
            return Response(url, self.page, "text/html", set_cookie_headers=("anon=synthetic; Path=/; Secure",))
        assert "anon=synthetic" in kwargs["headers"]["Cookie"]
        query = parse_qs(urlsplit(url).query)
        assert query["endid"] == ["synthetic-district"]
        file = {"/Services/api/GetMeeting/": "meeting.json",
                "/Services/api/MeetingView/GetItemsTreeDTO/": "items.json",
                "/Services/api/GetSupportingDocuments/": "supporting.json"}.get(path)
        content = (ROOT / file).read_bytes() if file else b"null"
        return Response(url, content, "application/json", 403 if path == self.fail else 200)


def test_registered_detail_and_agenda_raw_parent_identity_and_private_controls():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and not result.errors, result.public_dict()
    records = result.data["records"]
    assert len(records) > 12
    assert records[0]["identity"]["external_id"] == "4942"
    assert records[0]["normalized"]["meeting_date"] == "2026-11-10"
    assert records[0]["normalized"]["time_zone_status"] == "unknown"
    agenda = records[0]["normalized"]["documents"][0]
    assert agenda["url"] == "https://simbli.eboardsolutions.com/SB_Meetings/PrintAgenda.aspx?S=36031063&MID=4942"
    assert agenda["availability"] == "client_declared_print_locator_unverified"
    assert "format" not in agenda and "external_id" not in agenda
    items = [r for r in records if r["identity"]["record_type"] == "agenda_item"]
    assert all(r["identity"]["parent"]["external_id"] == "4942" for r in items)
    assert any(any(rel["relation"] == "parent_agenda_item" for rel in r["relationships"]) for r in items)
    assert all(not r["normalized"]["documents"] for r in items)
    assert base64.b64decode(result.data["bundles"][1]["capture"]["content_base64"]) == (ROOT / "items.json").read_bytes()
    assert "synthetic-private-control" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("format,file", [(DETAIL, "meeting.json"), (ITEMS, "items.json")])
def test_additive_saved_formats_preserve_originals(format, file):
    result = create_engine().execute("normalize", {"source": {**SOURCE, "input_format": format}},
                                     content=(ROOT / file).read_bytes())
    assert result.status == "completed", result.public_dict()
    assert result.data["capture"]["original_values"] == json.loads((ROOT / file).read_bytes())


@pytest.mark.parametrize("page", [FORM.replace(b"'False'", b"'True'"),
                                  FORM.replace(b"'4942'", b"'4943'"),
                                  FORM.replace(b"enCuUID=''", b"enCuUID='user'")])
def test_non_anonymous_or_changed_identity_fails_before_service_reads(page):
    transport = Transport(page)
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "failed" and len(transport.calls) == 1
    assert "synthetic-private-control" not in json.dumps(result.public_dict())


def test_partial_child_failure_limits_scope_and_revocation():
    transport = Transport(fail="/Services/api/MeetingView/GetItemsTreeDTO/")
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and result.errors
    assert len(result.data["records"]) == 1
    limited = create_engine(provider_transport=Transport()).execute("fetch", {
        "source": SOURCE, "bounds": {"max_records": 2, "max_pages": 2}})
    assert len(limited.data["records"]) == 2 and limited.coverage["truncated"]
    assert create_engine(provider_transport=Transport()).execute("fetch", {"source": SOURCE},
        context=OperationContext(allowed_operations=frozenset())).status == "failed"


class ContentTransport(Transport):
    def __init__(self, *, mismatch=False, null=False):
        super().__init__(FORM + b"var viewMode='publicview';")
        self.mismatch, self.null = mismatch, null

    def request(self, url, **kwargs):
        if urlsplit(url).path != "/Services/api/MeetingView/GetMeetingItemDetailsModel/":
            return super().request(url, **kwargs)
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        assert query["enuid"] == [""] and query["view"] == ["publicview"]
        assert query["stab"] == ["1"]
        data = None if self.null else {"ItemDetails": {
            "EncrID": "changed" if self.mismatch else query["enitemid"][0], "Title": "Supplied content"},
            "ItemContents": [{"FieldName": "abstract", "ControlType": 11,
                "Content": "<p>Actual supplied item text</p>", "HasData": True,
                "Attachments": [{"AttachmentID": 131003, "Title": "Sign in sheet",
                    "FileName": "sheet.pdf", "SchoolID": "36031063", "EnitityID": 4942, "SecurityToken": "private-synthetic-attachment"}]}]}
        return Response(url, json.dumps(data).encode(), "application/json")


def _selected_source():
    tree = json.loads((ROOT / "items.json").read_bytes())
    return {**SOURCE, "options": {"agenda_item_id": tree["Items"][0]["AgendaID"]}}


def test_selected_content_uses_fresh_tree_identity_and_retains_raw_fields():
    transport = ContentTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": _selected_source()})
    assert not result.errors, result.public_dict()
    identities = [(r["identity"]["record_type"], r["identity"]["external_id"])
                  for r in result.data["records"]]
    assert len(identities) == len(set(identities))
    content = next(b for b in result.data["bundles"] if b["capture"]["input_format"] == "simbli-item-content-json")
    record = content["records"][0]
    assert record["identity"]["parent"]["external_id"] == "4942"
    assert record["normalized"]["level"] == json.loads((ROOT / "items.json").read_bytes())["Items"][0]["Level"]
    assert record["normalized"]["content_fields"][0]["Content"] == "<p>Actual supplied item text</p>"
    assert record["text"][0]["text"] == "Actual supplied item text"
    assert record["text"][0]["provenance"]["source_control_type"] == 11
    assert record["text"][0]["provenance"]["capture_sha256"] == content["capture"]["sha256"]
    assert record["normalized"]["documents"][0]["external_id"] == "131003"
    assert record["normalized"]["documents"][0]["url"] == "https://simbli.eboardsolutions.com/Meetings/Attachment.aspx?S=36031063&AID=131003&MID=4942"
    assert "private-synthetic-attachment" not in json.dumps(record["normalized"])
    assert content["capture"]["original_values"]["response"]["ItemContents"][0]["Attachments"][0]["SecurityToken"] == "private-synthetic-attachment"
    saved = create_engine().execute("normalize", {"source": {**SOURCE,
        "input_format": "simbli-item-content-json"}}, content=base64.b64decode(content["capture"]["content_base64"]))
    assert saved.status == "completed"
    assert saved.data["records"][0]["identity"] == record["identity"]


@pytest.mark.parametrize("kwargs", [{"mismatch": True}, {"null": True}])
def test_selected_content_rejects_wrong_identity_or_unavailable_response(kwargs):
    result = create_engine(provider_transport=ContentTransport(**kwargs)).execute("fetch", {"source": _selected_source()})
    assert result.status == "partial" and result.errors
    assert {b["capture"]["input_format"] for b in result.data["bundles"]} == {
        "simbli-meeting-detail-json", "simbli-agenda-items-json",
        "simbli-supporting-documents-json", "simbli-simple-minutes-json"}


def test_unlisted_item_does_not_make_content_request():
    transport = ContentTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {
        "source": {**SOURCE, "options": {"agenda_item_id": 999999999}}})
    assert result.errors and len(transport.calls) == 5


def test_selected_content_respects_page_budget_before_item_request():
    transport = ContentTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {
        "source": _selected_source(), "bounds": {"max_pages": 4}})
    assert result.errors and len(transport.calls) == 5
    assert not any("GetMeetingItemDetailsModel" in call for call in transport.calls)


def test_saved_content_never_maps_foreign_meeting_attachment_url():
    source = {**SOURCE, "input_format": "simbli-item-content-json"}
    payload = {"meeting_id": "4942", "agenda_item_id": 176766,
        "response": {"ItemDetails": {"Title": "Captured item"}, "ItemContents": [{
            "Attachments": [{"AttachmentID": 131003, "SchoolID": "36031063", "EnitityID": 4943}]}]}}
    result = create_engine().execute("normalize", {"source": source}, content=json.dumps(payload).encode())
    assert result.status == "completed"
    assert "url" not in result.data["records"][0]["normalized"]["documents"][0]


def test_only_supplied_available_rich_text_controls_emit_text_without_script_execution():
    fields = [
        {"ControlType": 11, "HasData": True, "FieldName": "description",
         "Content": "<p>Supplied description</p><script>not supplied prose</script>"},
        {"ControlType": 99, "HasData": True, "Content": "unknown control content"},
        {"ControlType": 11, "HasData": False, "Content": "unavailable control content"},
    ]
    payload = {"meeting_id": "4942", "agenda_item_id": 176766,
        "response": {"ItemDetails": {"Title": "Captured item"}, "ItemContents": fields}}
    result = create_engine().execute("normalize", {
        "source": {**SOURCE, "input_format": "simbli-item-content-json"}}, content=json.dumps(payload).encode())
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert [s["text"] for s in record["text"]] == ["Supplied description"]
    assert record["normalized"]["content_fields"][1]["Content"] == "unknown control content"
    assert result.data["capture"]["original_values"] == payload


def test_selected_content_attachment_flows_through_capture_verified_engine_transfer():
    pdf = b"%PDF-1.7 synthetic supplied attachment"

    class FileTransport(ContentTransport):
        def request(self, url, **kwargs):
            if urlsplit(url).path == "/Meetings/Attachment.aspx":
                self.calls.append(url)
                assert parse_qs(urlsplit(url).query) == {
                    "S": ["36031063"], "AID": ["131003"], "MID": ["4942"]}
                assert kwargs["allowed_origins"] == ("https://simbli.eboardsolutions.com",)
                return Response(url, pdf, "application/pdf")
            return super().request(url, **kwargs)

    transport = FileTransport()
    engine = create_engine(provider_transport=transport)
    result = engine.execute("fetch", {"source": _selected_source()})
    bundle = next(b for b in result.data["bundles"] if b["capture"]["input_format"] == "simbli-item-content-json")
    capture = base64.b64decode(bundle["capture"]["content_base64"])
    fetched = engine.fetch_attachment(Source(**SOURCE, input_format="simbli-item-content-json"),
        bundle["records"][0], capture=capture)
    assert fetched.status == "completed", fetched.public_dict()
    assert base64.b64decode(fetched.data["attachment"]["content_base64"]) == pdf
    assert fetched.data["attachment"]["citation_url"].endswith("S=36031063&AID=131003&MID=4942")


class SupportingTransport(Transport):
    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def request(self, url, **kwargs):
        path = urlsplit(url).path
        if path == "/Services/api/GetSupportingDocuments/":
            self.calls.append(url)
            return Response(url, json.dumps(self.payload).encode(), "application/json")
        if path == "/Meetings/Attachment.aspx":
            self.calls.append(url)
            assert parse_qs(urlsplit(url).query) == {"S": ["36031063"], "AID": ["131003"], "MID": ["4942"]}
            return Response(url, b"%PDF-1.7 supporting document", "application/pdf")
        return super().request(url, **kwargs)


def test_supporting_attachment_capture_parent_and_verified_transfer():
    attachment = {"AttachmentID": 131003, "SchoolID": "36031063", "EnitityID": 4942,
                  "Title": "Meeting packet", "FileName": "packet.pdf", "unknown": "preserved"}
    payload = {"Attachment": [attachment], "HyperLink": [{"HUrl": "https://example.org/"}]}
    transport = SupportingTransport(payload)
    engine = create_engine(provider_transport=transport)
    result = engine.execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and not result.errors, result.public_dict()
    bundle = next(b for b in result.data["bundles"] if b["capture"]["input_format"] == "simbli-supporting-documents-json")
    record = bundle["records"][0]
    assert record["identity"]["record_type"] == "document"
    assert record["identity"]["external_id"] == "131003"
    assert record["identity"]["parent"]["external_id"] == "4942"
    assert record["original"] == attachment
    captured = base64.b64decode(bundle["capture"]["content_base64"])
    assert json.loads(captured) == payload
    downloaded = engine.fetch_attachment(Source(**SOURCE, input_format="simbli-supporting-documents-json"), record, capture=captured)
    assert downloaded.status == "completed", downloaded.public_dict()
    assert base64.b64decode(downloaded.data["attachment"]["content_base64"]) == b"%PDF-1.7 supporting document"


@pytest.mark.parametrize("change", [{"SchoolID": "other"}, {"EnitityID": 4943}])
def test_supporting_foreign_parent_is_not_attributed(change):
    attachment = {"AttachmentID": 131003, "SchoolID": "36031063", "EnitityID": 4942, **change}
    payload = {"Attachment": [attachment], "HyperLink": []}
    source = {**SOURCE, "input_format": "simbli-supporting-documents-json"}
    result = create_engine().execute("normalize", {"source": source}, content=json.dumps(payload).encode())
    assert result.status == "completed"
    assert result.data["records"] == []
    assert result.data["capture"]["original_values"] == payload


def test_malformed_supporting_response_retains_earlier_independent_records():
    transport = SupportingTransport({"Attachment": [None], "HyperLink": []})
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and result.errors
    assert any(r["identity"]["record_type"] == "meeting" for r in result.data["records"])
    assert any(r["identity"]["record_type"] == "agenda_item" for r in result.data["records"])
    assert any(c.get("observed_read_route") == "/Services/api/GetSupportingDocuments/" for c in result.data["captures"])
    assert any(urlsplit(call).path == "/Services/api/GetMinutes/" for call in transport.calls)


def test_supporting_bundle_reopen_search_and_neutral_export(tmp_path):
    from civic_data_connectors.interchange import read_bundle
    from civic_data_connectors.storage import SQLiteStorage

    payload = {"Attachment": [{"AttachmentID": 131003, "SchoolID": "36031063", "EnitityID": 4942,
               "Title": "District budget packet", "FileName": "packet.pdf"}], "HyperLink": []}
    database = tmp_path / "simbli.sqlite"
    engine = create_engine(storage=SQLiteStorage(database), provider_transport=SupportingTransport(payload))
    result = engine.execute("fetch", {"source": SOURCE})
    bundle = next(b for b in result.data["bundles"] if b["capture"]["input_format"] == "simbli-supporting-documents-json")
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert imported.status == "completed", imported.public_dict()
    key = imported.data["bundle_key"]
    reopened = create_engine(storage=SQLiteStorage(database))
    found = reopened.execute("search", {"query": {"phrases": ["district budget packet"]}})
    assert any(r["identity"]["external_id"] == "131003" for r in found.data["records"])
    exported = reopened.execute("export", {"bundle_key": key, "format": "zip"})
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == bundle


def test_supporting_http_failure_keeps_independent_minutes_read():
    transport = Transport(fail="/Services/api/GetSupportingDocuments/")
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and result.errors
    assert any(r["identity"]["record_type"] == "meeting" for r in result.data["records"])
    assert any(c.get("observed_read_route") == "/Services/api/GetMinutes/" for c in result.data["captures"])


def test_failed_supporting_request_consumes_page_budget_for_selected_item():
    transport = ContentTransport()
    transport.fail = "/Services/api/GetSupportingDocuments/"
    result = create_engine(provider_transport=transport).execute("fetch", {
        "source": _selected_source(), "bounds": {"max_pages": 4}})
    assert result.status == "partial" and result.errors
    assert len(transport.calls) == 5
    assert not any("GetMeetingItemDetailsModel" in call for call in transport.calls)


def test_supporting_transport_exception_consumes_page_budget():
    class FailedTransport(ContentTransport):
        def request(self, url, **kwargs):
            if urlsplit(url).path == "/Services/api/GetSupportingDocuments/":
                self.calls.append(url)
                raise OSError("synthetic transport failure")
            return super().request(url, **kwargs)

    transport = FailedTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {
        "source": _selected_source(), "bounds": {"max_pages": 4}})
    assert result.status == "partial" and result.errors
    assert len(transport.calls) == 5
    assert not any("GetMeetingItemDetailsModel" in call for call in transport.calls)
