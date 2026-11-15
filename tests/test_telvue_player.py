"""Actual native public TelVue player/caption captures, no account or generation."""
import base64
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import telvue_player
from civic_data_connectors.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures/telvue-player"
PLAYER, CAPTION = (ROOT / "player.html").read_bytes(), (ROOT / "captions.vtt").read_bytes()
SOURCE = Source("telvue", "https://videoplayer.telvue.com/player/4jeRlBTetCoFJdyT5ssIvBrB9VUvRN0M/playlists/1757/media/1066963?showtabssearch=true&fullscreen=false", input_format="telvue-public-player-html")
TRACK = "/closed_captions/W1siZiIsIjc4NTkyMDYwLTQ2YzctMDEzMC04MjAyLTUyNTQwMDQ3MTQ4ZS84NDdmOTcwZC00ZWZmLTQ5OTItOGNlNS0wZTgxMzc4MTdhMzQvY2xvc2VkX2NhcHRpb25zL3ByaW1hcnktZW4tY2FwdGlvbnMtMTc5Mzc1NDA0Ni52dHQiXV0?sha=fb4bfea3acc1b7f2"
TARGET = "https://videoplayer.telvue.com" + TRACK


class Network:
    def __init__(self, caption=CAPTION, mime="text/vtt", response_url=TARGET, cancel=None):
        self.calls = []
        self.caption, self.mime, self.response_url, self.cancel = caption, mime, response_url, cancel

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False
        assert options["allowed_origins"] == ("https://videoplayer.telvue.com",)
        if url == SOURCE.url:
            return Response(url, PLAYER, "text/html")
        assert url == TARGET
        if self.cancel:
            self.cancel.set()
        return Response(self.response_url, self.caption, self.mime)


def test_actual_player_literal_json_native_id_and_source_labels_without_date_inference():
    assert sha256(PLAYER).hexdigest() == "7a1da6118ed1f7645d1fe87dba67d5da813a906bbfe12386de2da12fe12eddbd"
    result = create_engine().normalize(SOURCE, PLAYER, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["external_id"] == "1066963"
    assert record["identity"]["record_type"] == "recording"
    value = record["normalized"]
    assert value["title"] == "City Council - November 3, 2026"
    assert not {"meeting_date", "body", "scheduled_start"} & value.keys()
    recording, = value["recordings"]
    assert recording["source_duration"] == 4145
    assert [t["source_label"] for t in recording["caption_tracks"]] == ["English", "Spanish"]
    assert recording["caption_tracks"][0]["url"] == TARGET
    assert "source_language" not in recording["caption_tracks"][0]
    assert record["normalized_sha256"] == canonical_hash(value)
    assert base64.b64decode(result.data["capture"]["content_base64"]) == PLAYER


def test_default_configured_player_fetch_does_not_fetch_media_or_captions():
    network = Network()
    result = create_engine(provider_transport=network).fetch(replace(SOURCE, input_format=None))
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.data["records"][0]["identity"]["external_id"] == "1066963"
    assert len(network.calls) == 1 and network.calls[0][0] == SOURCE.url


@pytest.mark.parametrize("language", [None, "English"])
def test_supplied_caption_exact_bytes_hash_search_persist_reopen_and_neutral_exports(tmp_path, language):
    network = Network()
    engine = create_engine(provider_transport=network, storage=SQLiteStorage(tmp_path / "data.sqlite"))
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.fetch_captions(SOURCE, "1066963", language=language, context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["normalized"]["supplied_caption_text"] == CAPTION.decode("utf-8")
    assert len(network.calls) == 2 and result.coverage["caption_file_received"]
    assert result.coverage["content_language"] is None and not result.coverage["generation_requested"]
    capture, = result.data["captures"]
    assert sha256(CAPTION).hexdigest() == capture["sha256"] == "99a71131f7422cd27b3062dc95a57cb8eebd8025d97a0420a0145565104cdbde"
    assert base64.b64decode(capture["content_base64"]) == CAPTION
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    assert reopened.execute("search", {"query": {"phrases": ["Little city"]}}, context=caller).data["hits"]
    for format in ("json", "jsonl", "zip"):
        exported = reopened.execute("export", {"bundle": result.data, "format": format}, context=caller)
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("before,after", [
    (b'"mediaid":"medium/1066963"', b'"mediaid":"medium/1066964"'),
    (b"Player.setupData['playlist'] = [", b"Player.setupData['playlist'] = executable(["),
    (b'"file":"/closed_captions/', b'"file":"https://foreign.example/closed_captions/'),
    (b'"file":"https://telvuevod-secure.akamaized.net', b'"file":"http://telvuevod-secure.akamaized.net'),
])
def test_wrong_identity_nonliteral_or_unsafe_locator_is_not_mapped(before, after):
    assert before in PLAYER
    result = create_engine().normalize(SOURCE, PLAYER.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("options", [
    {"caption": b"<html>Login</html>", "mime": "text/html"},
    {"caption": b"not WebVTT"},
    {"response_url": TARGET + "&redirect=1"},
])
def test_failed_caption_retains_player_and_does_not_claim_text(options):
    network = Network(**options)
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "1066963")
    assert result.status == "partial" and result.errors, result.public_dict()
    assert result.data["records"][0]["identity"]["external_id"] == "1066963"
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]


def test_unknown_label_not_inferred_from_filename_and_bad_id_bound_before_network():
    network = Network()
    engine = create_engine(provider_transport=network)
    assert engine.fetch_captions(SOURCE, "1066964").status == "failed"
    assert engine.fetch_captions(SOURCE, "1066963", bounds=Bounds(max_pages=1)).status == "failed"
    assert not network.calls
    result = engine.fetch_captions(SOURCE, "1066963", language="en")
    assert result.status == "partial" and result.errors
    assert len(network.calls) == 1


def test_aggregate_budget_and_post_response_cancellation():
    network = Network()
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "1066963",
        bounds=Bounds(transfer_bytes=len(PLAYER) + 16))
    assert result.status == "partial" and result.errors
    assert network.calls[1][1]["byte_limit"] == 16
    caller = OperationContext()
    network = Network(cancel=caller.cancellation)
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "1066963", context=caller)
    assert result.status == "cancelled" and len(network.calls) == 2


def test_mapping_deadline_prevents_caption_request(monkeypatch):
    clock = [0.0]
    original = telvue_player.parse_bundle

    def delayed(*args):
        result = original(*args)
        clock[0] = 2.0
        return result

    monkeypatch.setattr(telvue_player, "parse_bundle", delayed)
    monkeypatch.setattr(telvue_player, "monotonic", lambda: clock[0])
    network = Network()
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "1066963",
        bounds=Bounds(deadline_seconds=1))
    assert result.status == "partial" and result.errors and len(network.calls) == 1
