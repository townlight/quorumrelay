"""A supplied native Minutes document remains separate from the meeting."""

import base64
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

SOURCE = Source("novusagenda", "https://hpwd.novusagenda.com/agendapublic/MeetingView.aspx?"
                "MeetingID=210&MinutesMeetingID=168&doctype=Minutes", input_format="novus-public-listing-html")
CONTENT = (Path(__file__).parent / "fixtures/novus-minutes-210.html").read_bytes()


class Network:
    def __init__(self, *, url=SOURCE.url, mime="text/html"):
        self.calls, self.url, self.mime = [], url, mime

    def request(self, url, **options):
        self.calls.append((url, options))
        assert url == SOURCE.url and options["allow_redirects"] is False
        assert options["allowed_origins"] == ("https://hpwd.novusagenda.com",)
        return Response(self.url, CONTENT, self.mime)


def test_actual_minutes_native_document_parent_text_and_original_bytes():
    assert hashlib.sha256(CONTENT).hexdigest() == "a5c4a1d251019fefca817de975193a1e77732c1c5e1e6d0ae6ab7c2bae1454d4"
    result = create_engine().normalize(SOURCE, CONTENT, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["record_type"] == "document"
    assert record["identity"]["external_id"] == "168"
    assert record["identity"]["parent"]["external_id"] == "210"
    assert record["relationships"] == [{"relation": "meeting", "identity": record["identity"]["parent"]}]
    value = record["normalized"]
    assert value["kind"] == "minutes" and value["meeting_date"] == "2021-08-17"
    assert value["source_start"] == "2021-08-17T10:00:00" and value["time_zone_status"] == "unknown"
    assert value["location"] == "HPWD Office, 2930 Avenue Q, Lubbock, TX 79411-2499"
    assert "Desired Future Conditions" in value["text"]
    assert record["text"][0]["text"] == value["text"]
    assert not {"votes", "attendance", "agenda_items", "motions"} & value.keys()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CONTENT


def test_default_fetch_persistence_search_reopen_and_exact_zip(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.fetch(replace(SOURCE, input_format=None), context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(network.calls) == 1 and len(result.data["records"]) == 1
    assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    found = reopened.execute("search", {"query": {"phrases": ["Desired Future Conditions"]}}, context=caller)
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = reopened.execute("export", {"bundle": result.data, "format": "zip"}, context=caller)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data


@pytest.mark.parametrize("before,after", [
    (b'action="./MeetingView.aspx?MeetingID=210', b'action="./MeetingView.aspx?MeetingID=211'),
    (b'&amp;MinutesMeetingID=168', b'&amp;MinutesMeetingID=169'),
    (b'&amp;doctype=Minutes', b'&amp;doctype=Agenda'),
    (b'Tuesday, August 17, 2021', b'Monday, August 17, 2021'),
    (b'10:00 AM', b'unknown time'),
    (b'id="Form1"', b'id="OtherForm"'),
])
def test_changed_form_native_context_or_heading_fails(before, after):
    assert before in CONTENT
    result = create_engine().normalize(SOURCE, CONTENT.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("url", [SOURCE.url + "&MeetingID=211", SOURCE.url + "#fragment",
    SOURCE.url.replace("MinutesMeetingID=168", "MinutesMeetingID=-1"),
    SOURCE.url.replace("https:", "http:")])
def test_invalid_context_fails_before_network(url):
    network = Network()
    result = create_engine(provider_transport=network).discover(replace(SOURCE, url=url))
    assert result.status == "failed", result.public_dict()
    assert not network.calls


@pytest.mark.parametrize("options", [{"url": SOURCE.url.replace("168", "169")}, {"mime": "application/pdf"}])
def test_wrong_native_response_or_mime_rejected(options):
    result = create_engine(provider_transport=Network(**options)).discover(SOURCE)
    assert result.errors and not result.data["records"], result.public_dict()


def test_transfer_limit_and_precancellation():
    network = Network()
    engine = create_engine(provider_transport=network)
    result = engine.discover(SOURCE, bounds=Bounds(transfer_bytes=16))
    assert result.errors and not result.data["records"], result.public_dict()
    assert network.calls[0][1]["byte_limit"] == 16
    caller = OperationContext()
    caller.cancellation.set()
    assert engine.discover(SOURCE, context=caller).status == "cancelled"
    assert len(network.calls) == 1


def test_explicit_meeting_date_filter_excludes_document():
    result = create_engine(provider_transport=Network()).discover(
        SOURCE, bounds=Bounds(date_from="2022-01-01", date_to="2022-12-31"))
    assert not result.errors and not result.data["records"], result.public_dict()
