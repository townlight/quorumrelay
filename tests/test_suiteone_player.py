"""Selected actual SuiteOne source transcript and native-event caption file."""
import base64
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash, source_identity_key
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import suiteone_player
from civic_data_connectors.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures/suiteone-player"
PLAYER, CAPTION = (ROOT / "event-2165.html").read_bytes(), (ROOT / "captions.vtt").read_bytes()
SOURCE = Source("suiteone-media", "https://watkinsvillega.suiteonemedia.com/event/?id=2165",
                input_format="suiteone-public-event-html")
TARGET = "https://watkinsvillega.suiteonemedia.com/Event/GetCaptions/?eventId=2165"


class Network:
    def __init__(self, caption=CAPTION, mime="text/vtt", response_url=TARGET, cancel=None):
        self.calls, self.caption, self.mime, self.response_url, self.cancel = [], caption, mime, response_url, cancel

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False
        assert options["allowed_origins"] == ("https://watkinsvillega.suiteonemedia.com",)
        if url == SOURCE.url:
            return Response(url, PLAYER, "text/html")
        assert url == TARGET
        if self.cancel:
            self.cancel.set()
        return Response(self.response_url, self.caption, self.mime)


def test_actual_rendered_table_native_identity_original_rows_and_no_duplicate_display_text():
    assert sha256(PLAYER).hexdigest() == "652eed6ff364a02791ea07a464f818e171d2b6671634664da9ca9af3bd6a2302"
    engine = create_engine()
    result = engine.normalize(SOURCE, PLAYER, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    value = record["normalized"]
    assert record["identity"]["external_id"] == "2165"
    assert value["title"] == "City Council Regular Meeting"
    assert len(value["transcript_rows"]) == 959 and len(value["supplied_transcript_text"]) == 46059
    assert value["transcript_rows"][0] == {"text": "We are fired up.", "source_start": "8.44",
        "source_end": "9.36", "source_timestamp_literal": "00:00:08"}
    assert record["text"][0]["text"] == value["supplied_transcript_text"]
    assert value["recordings"][0]["caption_tracks"][0]["url"] == TARGET
    assert not {"meeting_date", "body", "votes", "motions", "attendance"} & value.keys()
    assert record["normalized_sha256"] == canonical_hash(value)
    archive = engine.normalize(replace(SOURCE, url="https://watkinsvillega.suiteonemedia.com/",
        input_format="suiteone-archive-html"),
        (ROOT.parent / "baseline/suiteone.response").read_bytes(), input_format="suiteone-archive-html")
    parent = next(r for r in archive.data["records"] if r["identity"]["external_id"] == "2165")
    assert source_identity_key(parent["identity"]) == source_identity_key(record["identity"])
    assert base64.b64decode(result.data["capture"]["content_base64"]) == PLAYER


def test_default_configured_event_html_fetch_does_not_fetch_media_or_caption():
    network = Network()
    result = create_engine(provider_transport=network).fetch(replace(SOURCE, input_format=None))
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(network.calls) == 1
    assert not result.coverage["playback_verified"] and not result.coverage["generation_requested"]


@pytest.mark.parametrize("language", [None, "English"])
def test_actual_declared_vtt_text_bytes_hash_persistence_search_and_neutral_formats(tmp_path, language):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.fetch_captions(SOURCE, "2165", language=language, context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(network.calls) == 2
    record, = result.data["records"]
    assert record["normalized"]["supplied_caption_text"] == CAPTION.decode("utf-8")
    assert len(record["text"]) == 2
    capture, = result.data["captures"]
    assert capture["sha256"] == sha256(CAPTION).hexdigest() == "ee014e220eb3bccd4389db206523fa205826b557774b3a9cbd76810c0b5d4dc7"
    assert base64.b64decode(capture["content_base64"]) == CAPTION
    assert result.coverage["content_language"] is None and not result.coverage["generation_requested"]
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    assert reopened.execute("search", {"query": {"phrases": ["We are fired up"]}}, context=caller).data["hits"]
    for format in ("json", "jsonl", "zip"):
        exported = reopened.execute("export", {"bundle": result.data, "format": format}, context=caller)
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("before,after", [
    (b'data-eventid="2165"', b'data-eventid="2166"'),
    (b'GetCaptions/?eventId=2165', b'GetCaptions/?eventId=2166'),
    (b'id="transcriptPlayer"', b'id="unknownTranscript"'),
    (b"var src = 'https://s3.amazonaws.com", b"var src = 'http://s3.amazonaws.com"),
])
def test_native_context_or_player_mismatch_is_not_mapped(before, after):
    assert before in PLAYER
    result = create_engine().normalize(SOURCE, PLAYER.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("options", [
    {"caption": b"<html>Login</html>", "mime": "text/html"},
    {"caption": b"not WebVTT"},
    {"response_url": TARGET + "&redirect=1"},
])
def test_caption_failure_retains_independent_rendered_source_text(options):
    result = create_engine(provider_transport=Network(**options)).fetch_captions(SOURCE, "2165")
    assert result.status == "partial" and result.errors, result.public_dict()
    assert result.data["records"][0]["normalized"]["supplied_transcript_text"].startswith("We are fired up.")
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]


def test_bounds_identity_and_unknown_label_do_not_request_unsupplied_data():
    network = Network()
    engine = create_engine(provider_transport=network)
    assert engine.fetch_captions(SOURCE, "2166").status == "failed"
    assert engine.fetch_captions(SOURCE, "2165", bounds=Bounds(max_pages=1)).status == "failed"
    assert not network.calls
    result = engine.fetch_captions(SOURCE, "2165", language="en")
    assert result.status == "partial" and result.errors and len(network.calls) == 1
    network.calls.clear()
    result = engine.fetch_captions(SOURCE, "2165", bounds=Bounds(transfer_bytes=len(PLAYER) + 16))
    assert result.status == "partial" and result.errors and network.calls[-1][1]["byte_limit"] == 16


def test_post_response_cancellation_and_mapper_deadline_keep_partial_source(monkeypatch):
    caller = OperationContext()
    network = Network(cancel=caller.cancellation)
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "2165", context=caller)
    assert result.status == "cancelled" and len(network.calls) == 2
    original = suiteone_player.parse_bundle
    clock = [0.0]

    def delayed(*args):
        bundle = original(*args)
        clock[0] = 2.0
        return bundle

    monkeypatch.setattr(suiteone_player, "parse_bundle", delayed)
    monkeypatch.setattr(suiteone_player, "monotonic", lambda: clock[0])
    network = Network()
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "2165", bounds=Bounds(deadline_seconds=1))
    assert result.status == "partial" and result.errors and len(network.calls) == 1
