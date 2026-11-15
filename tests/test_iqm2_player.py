"""Observed iQM2 player data; no evaluation, playback or automatic media transfer."""
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from quorumrelay import Source, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.interchange import read_bundle

EVIDENCE = json.loads((Path(__file__).parent / "fixtures/iqm2-player-6049.capture.json").read_bytes())
CAPTURE = base64.b64decode(EVIDENCE["content_base64"], validate=True)
SOURCE = Source("iqm2", EVIDENCE["source_url"], input_format="iqm2-public-player-html")


def test_observed_player_retains_exact_meeting_and_hls_without_claiming_mp4_or_captions():
    assert hashlib.sha256(CAPTURE).hexdigest() == EVIDENCE["sha256"]
    owner = create_engine()
    result = owner.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "6049"
    media = record["normalized"]["recordings"][0]
    assert media["playback_url"].endswith("3527_480.mp4/playlist.m3u8")
    assert media["playback_type"] == "application/x-mpegURL"
    assert media["caption_tracks"] == [] and media["playback_verified"] is False
    assert record["normalized"]["title_availability"] == "native_id_label_only"
    assert "meeting_date" not in record["normalized"]
    exported = owner.execute("export", {"format": "zip", "bundle": result.data})
    assert exported.status == "completed", exported.public_dict()
    restored = read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip")
    assert restored == result.data


def test_configured_player_gets_one_html_page_and_never_requests_declared_media():
    class Transport:
        def __init__(self): self.calls = []
        def request(self, url, **kwargs):
            self.calls.append(url)
            assert url == SOURCE.url
            return Response(url, CAPTURE, "text/html")
    network = Transport()
    result = create_engine(provider_transport=network).discover(replace(SOURCE, input_format=None))
    assert result.status == "partial" and len(result.data["records"]) == 1, result.public_dict()
    assert network.calls == [SOURCE.url]
    assert result.coverage["source_complete"] is False
    assert result.coverage["date_availability"] == "not_supplied_in_player_mapping"


def declared(sources, has_transcript="True"):
    start = CAPTURE.index(b"SetupJWPlayer(eval('")
    end = CAPTURE.index(b"; </script>", start)
    call = "SetupJWPlayer(eval('" + json.dumps(sources) + "'),'False','" + has_transcript + "')"
    return CAPTURE[:start] + call.encode() + CAPTURE[end:]


def test_literal_mp4_supplied_first_track_is_metadata_with_player_language_attribution():
    data = declared([{"file": "https://media.example.org/public.mp4", "tracks": [
        {"file": "https://media.example.org/public.vtt", "label": "English"}]}])
    result = create_engine().normalize(SOURCE, data, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    media = result.data["records"][0]["normalized"]["recordings"][0]
    assert media["playback_type"] == "video/mp4"
    assert media["caption_tracks"][0]["url"].endswith("public.vtt")
    assert media["caption_tracks"][0]["availability"] == "supplied_locator_not_fetched"
    assert media["caption_tracks"][0]["language_provenance"] == "player_hardcoded_srclang"


@pytest.mark.parametrize("data", [
    CAPTURE.replace(b'&ID=6049', b'&ID=6050'),
    CAPTURE.replace(b'id="OutlinePanelInner"', b'id="OtherPanel"'),
    CAPTURE.replace(b"SetupJWPlayer(eval('", b"SetupJWPlayer(run('"),
    CAPTURE.replace(b"; </script>", b"; SetupJWPlayer(computed); </script>"),
    declared([]),
    declared([{"file": "http://127.0.0.1/private.mp4"}]),
    declared([{"file": "https://media.example.org/page.html"}]),
    declared([{"file": "https://media.example.org/public.mp4", "tracks": [{"file": "file:///private.vtt"}]}]),
])
def test_unbound_computed_or_unsafe_player_is_rejected(data):
    assert data != CAPTURE
    result = create_engine().normalize(SOURCE, data, input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()
