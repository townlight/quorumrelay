"""Actual supplied Swagit transcript/caption captures, not generated text."""

import base64
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers import swagit_player

FIXTURES = Path(__file__).parent / "fixtures/swagit-player"
PLAYER, CAPTION = (FIXTURES / "player.html").read_bytes(), (FIXTURES / "captions.vtt").read_bytes()
SOURCE = Source("swagit", "https://princetontx.new.swagit.com/videos/405841",
    input_format="swagit-public-player-html", options={"download_origins": ["https://swagit-video.granicus.com"]})
TARGET = "https://swagit-video.granicus.com/princetontx/32ea54ff-1e43-4027-a587-1b5c771d8755-en.vtt"


class Network:
    def __init__(self, *, player=PLAYER, caption=CAPTION, mime="application/octet-stream", redirect=False, cancel=None):
        self.calls, self.player, self.caption = [], player, caption
        self.mime, self.redirect, self.cancel = mime, redirect, cancel

    def request(self, url, **options):
        self.calls.append((url, options))
        assert url in {SOURCE.url, TARGET}
        assert options["allow_redirects"] is False and options["deadline_seconds"] > 0
        assert url.startswith(options["allowed_origins"][-1])
        if url == SOURCE.url:
            return Response(url, self.player, "text/html")
        if self.cancel:
            self.cancel.set()
        return Response(url + "?redirect" if self.redirect else url, self.caption, self.mime)


def test_actual_player_retains_native_identity_date_supplied_text_and_locators():
    assert hashlib.sha256(PLAYER).hexdigest() == "a29e96d76b464ddf4b104811195bd76ddd399e497a9e9324bcf0fe40934192f7"
    result = create_engine().normalize(SOURCE, PLAYER, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["external_id"] == "405841" and record["identity"]["record_type"] == "meeting"
    value = record["normalized"]
    assert value["meeting_date"] == "2026-11-03"
    assert value["title"] == "Parks and Recreation Advisory Board Meeting"
    assert value["recordings"][0]["caption_tracks"][0]["url"] == TARGET
    assert value["recordings"][0]["url"].endswith("playlist.m3u8?wowzacaptionfile=none")
    assert len(value["supplied_transcript_text"]) == 62736
    assert "WE'RE GOING TO CALL THIS MEETING TO ORDER" in value["supplied_transcript_text"]
    assert record["text"][0]["text"] == value["supplied_transcript_text"]
    assert not {"votes", "motions", "attendance", "agenda_items"} & value.keys()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == PLAYER


def test_default_player_fetch_and_listing_native_identity_match():
    network = Network()
    engine = create_engine(provider_transport=network)
    result = engine.fetch(replace(SOURCE, input_format=None))
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(network.calls) == 1 and not result.coverage["playback_verified"]
    listing = engine.normalize(replace(SOURCE, url="https://princetontx.new.swagit.com/videos/search?q=Council"),
        (Path(__file__).parent / "fixtures/swagit-native-search/page-1.html").read_bytes(), input_format="swagit-listing-html")
    assert listing.data["records"][0]["identity"] == result.data["records"][0]["identity"]


@pytest.mark.parametrize("language", [None, "en"])
def test_actual_supplied_webvtt_persists_searches_reopens_and_exports_exactly(tmp_path, language):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.fetch_captions(SOURCE, "405841", language=language, context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.coverage["pages"] == 2 and result.coverage["generation_requested"] is False
    assert hashlib.sha256(CAPTION).hexdigest() == "917de417c68b1db2f3aa5dc5596da2a74a21f0b07b26240be61c1c7d335ae6be"
    record = result.data["records"][0]
    assert record["normalized"]["supplied_caption_text"] == CAPTION.decode("utf-8-sig")
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])
    assert record["text"][-1]["provenance"]["content_language"] == "not_verified"
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == CAPTION
    assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    found = reopened.execute("search", {"query": {"phrases": ["CALL THIS MEETING TO ORDER"]}}, context=caller)
    assert found.data["hits"], found.public_dict()
    exported = reopened.execute("export", {"format": "zip", "bundle": result.data}, context=caller)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data


@pytest.mark.parametrize("before,after", [
    (b'href="/videos/405841/transcript"', b'href="/videos/405842/transcript"'),
    (b'id="transcript-fragments"', b'id="other-fragments"'),
    (b'Nov 03, 2026 Parks', b'bad date Parks'),
    (b'id="vjs-player"', b'id="other-player"'),
    (b'src="https://swagit-video.granicus.com/', b'src="http://swagit-video.granicus.com/'),
    (b'player.src({type:', b'notPlayer.src({type:'),
])
def test_changed_native_context_structure_or_locator_rejected(before, after):
    assert before in PLAYER
    result = create_engine().normalize(SOURCE, PLAYER.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("url", [SOURCE.url + "?ts=2", SOURCE.url + "#fragment",
    SOURCE.url.replace("https:", "http:"), SOURCE.url.replace("405841", "0")])
def test_invalid_player_context_fails_before_network(url):
    network = Network()
    result = create_engine(provider_transport=network).discover(replace(SOURCE, url=url))
    assert result.status == "failed", result.public_dict()
    assert not network.calls


def test_wrong_id_or_insufficient_pages_fail_before_network():
    network = Network()
    engine = create_engine(provider_transport=network)
    assert engine.fetch_captions(SOURCE, "405842").status == "failed"
    assert engine.fetch_captions(SOURCE, "405841", bounds=Bounds(max_pages=1)).status == "failed"
    assert not network.calls


def test_cross_origin_and_language_selection_do_not_authorize_unlisted_requests():
    network = Network()
    engine = create_engine(provider_transport=network)
    for source, language in [(replace(SOURCE, options={}), None), (SOURCE, "fr")]:
        result = engine.fetch_captions(source, "405841", language=language)
        assert result.status == "partial" and result.errors, result.public_dict()
        assert "supplied_caption_text" not in result.data["records"][0]["normalized"]
    assert [c[0] for c in network.calls] == [SOURCE.url, SOURCE.url]


@pytest.mark.parametrize("options", [{"caption": b'<html>Sign in</html>'}, {"mime": "text/html"},
    {"redirect": True}, {"caption": b'WEBVTT\n\n\xff'}, {"caption": b'WEBVTT --> invalid\n'}])
def test_bad_caption_retains_independent_inline_text_and_partial_error(options):
    result = create_engine(provider_transport=Network(**options)).fetch_captions(SOURCE, "405841")
    assert result.status == "partial" and result.errors, result.public_dict()
    assert result.data["records"][0]["normalized"]["supplied_transcript_text"]
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]


def test_aggregate_byte_bound_and_cancellation_prevent_success():
    network = Network()
    result = create_engine(provider_transport=network).fetch_captions(
        SOURCE, "405841", bounds=Bounds(transfer_bytes=len(PLAYER) + 16))
    assert result.errors and result.status == "partial", result.public_dict()
    assert network.calls[1][1]["byte_limit"] == 16
    caller = OperationContext()
    network = Network(cancel=caller.cancellation)
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "405841", context=caller)
    assert result.status == "cancelled" and len(network.calls) == 2
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]


def test_deadline_expiry_during_player_mapping_prevents_caption_request(monkeypatch):
    clock = [0.0]
    original = swagit_player.parse_bundle

    def expire(*args):
        bundle = original(*args)
        clock[0] = 2.0
        return bundle

    monkeypatch.setattr(swagit_player, "monotonic", lambda: clock[0])
    monkeypatch.setattr(swagit_player, "parse_bundle", expire)
    network = Network()
    result = create_engine(provider_transport=network).fetch_captions(
        SOURCE, "405841", bounds=Bounds(deadline_seconds=1))
    assert result.status == "partial" and result.errors and len(network.calls) == 1
