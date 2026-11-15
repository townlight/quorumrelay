"""Source-declared Utah calendar and audio locators, without event/time inference."""
import base64
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from test_utah_detail import CAPTURE, SOURCE

CALENDAR_URL = "https://www.utah.gov/pmn/sitemap/noticeical/1101977.ics"
AUDIO_URL = "https://www.utah.gov/pmn/files/1477057.mp3"
CALENDAR = (Path(__file__).parent / "fixtures/utah-notice-1101977.ics").read_bytes()


def test_declared_assets_preserve_identity_legacy_projection_and_source_time():
    result = create_engine().normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    value = record["normalized"]
    assert value["documents"][-1] == {"kind": "calendar", "url": CALENDAR_URL,
        "title": "Add Notice to Calendar"}
    assert value["recordings"] == [{"kind": "audio", "url": AUDIO_URL,
        "title": "08-14-2026.mp3", "source_category": "Audio Recording"}]
    assert value["source_start"] == "2026-08-18T18:30:00"
    assert value["time_zone_status"] == "unknown"
    assert len(result.data["compatibility"]["meetings"][0]["documents"]) == 3
    assert "recordings" not in result.data["compatibility"]["meetings"][0]
    assert b"UID:1101977" in CALENDAR


@pytest.mark.parametrize("before,after", [
    (b'/pmn/sitemap/noticeical/1101977.ics', b'/pmn/sitemap/noticeical/1101978.ics'),
    (b'/pmn/sitemap/noticeical/1101977.ics', b'https://foreign.example/pmn/sitemap/noticeical/1101977.ics'),
    (b'/pmn/sitemap/noticeical/1101977.ics', b'/pmn/sitemap/noticeical/1101977.ics?other=1'),
])
def test_calendar_locator_must_be_exact_source_notice(before, after):
    result = create_engine().normalize(SOURCE, CAPTURE.replace(before, after), input_format=SOURCE.input_format)
    assert not any(d["kind"] == "calendar" for d in result.data["records"][0]["normalized"]["documents"])


def test_foreign_audio_is_not_a_recording():
    raw = CAPTURE.replace(b'href="/pmn/files/1477057.mp3"',
        b'href="https://foreign.example/pmn/files/1477057.mp3"')
    result = create_engine().normalize(SOURCE, raw, input_format=SOURCE.input_format)
    assert result.data["records"][0]["normalized"]["recordings"] == []


class Network:
    def __init__(self, content=CALENDAR, content_type="text/calendar", response_url=CALENDAR_URL):
        self.calls = []
        self.response = Response(response_url, content, content_type)

    def request(self, url, **options):
        self.calls.append((url, options))
        assert url == CALENDAR_URL
        assert options["allow_redirects"] is False
        return self.response


def test_exact_calendar_bytes_transfer_retry_reopen_and_zip(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    bundle = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=caller).status == "completed"
    record, = bundle["records"]
    result = engine.fetch_attachment(SOURCE, record, index=3, capture=CAPTURE, context=caller)
    assert result.status == "completed", result.public_dict()
    assert base64.b64decode(result.data["attachment"]["content_base64"]) == CALENDAR
    assert result.data["bundle"]["capture"]["sha256"] == bundle["capture"]["sha256"]
    assert result.data["bundle"]["records"][0]["normalized"] == record["normalized"]
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    result = reopened.fetch_attachment(SOURCE, record, index=3, context=caller)
    assert result.status == "completed", result.public_dict()
    for format in ("json", "jsonl", "zip"):
        exported = reopened.execute("export", {"bundle": bundle, "format": format}, context=caller)
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == bundle


@pytest.mark.parametrize("content,content_type,response_url", [
    (b"<html>Login</html>", "text/html", CALENDAR_URL),
    (CALENDAR, "text/calendar", CALENDAR_URL + "?other=1"),
    (b"not calendar", "text/calendar", CALENDAR_URL),
])
def test_calendar_failure_retains_notice(content, content_type, response_url):
    engine = create_engine(provider_transport=Network(content, content_type, response_url))
    record, = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data["records"]
    result = engine.fetch_attachment(SOURCE, record, index=3, capture=CAPTURE)
    assert result.status == "partial" and result.errors, result.public_dict()
    assert result.data["record"]["identity"] == record["identity"]
    assert result.data["attachment"] is None


def test_calendar_transfer_bound_and_cancel_before_network():
    network = Network()
    engine = create_engine(provider_transport=network)
    record, = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data["records"]
    result = engine.fetch_attachment(SOURCE, record, index=3, capture=CAPTURE,
        bounds=Bounds(transfer_bytes=16))
    assert result.status == "partial" and result.errors, result.public_dict()
    assert network.calls[0][1]["byte_limit"] == 16
    network.calls.clear()
    cancelled = OperationContext()
    cancelled.cancellation.set()
    result = engine.fetch_attachment(SOURCE, record, index=3, capture=CAPTURE,
        context=cancelled)
    assert result.status == "cancelled", result.public_dict()
    assert not network.calls


def test_audio_metadata_and_opaque_bytes_are_separate_from_playback():
    calls = []

    class Audio:
        def request(self, url, **options):
            calls.append((url, options))
            assert url == AUDIO_URL and options["allow_redirects"] is False
            return Response(url, b"synthetic audio transfer", "audio/mpeg")

    engine = create_engine(provider_transport=Audio())
    record, = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data["records"]
    result = engine.fetch_attachment(SOURCE, record, index=0, kind="recordings", capture=CAPTURE)
    assert result.status == "completed", result.public_dict()
    assert result.data["attachment"]["text_availability"] == "not_extracted"
    assert len(calls) == 1
    assert not {"recording_date", "transcript", "duration"} & record["normalized"]["recordings"][0].keys()


def test_hidden_or_differently_labeled_audio_is_not_inferred():
    for raw in (CAPTURE.replace(b'Audio Recording', b'Other Information'),
                CAPTURE.replace(b'<table>', b'<table hidden>')):
        result = create_engine().normalize(SOURCE, raw, input_format=SOURCE.input_format)
        assert result.data["records"][0]["normalized"]["recordings"] == []


def test_cancellation_during_calendar_response_retains_notice():
    caller = OperationContext()

    class Cancels(Network):
        def request(self, url, **options):
            response = super().request(url, **options)
            caller.cancellation.set()
            return response

    network = Cancels()
    engine = create_engine(provider_transport=network)
    record, = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data["records"]
    result = engine.fetch_attachment(SOURCE, record, index=3, capture=CAPTURE, context=caller)
    assert result.status == "cancelled", result.public_dict()
    assert result.data["record"]["identity"] == record["identity"]
    assert len(network.calls) == 1
