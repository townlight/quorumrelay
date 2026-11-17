"""Synthetic transcription of the captured Town Hall Streams player contract."""

import base64

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response

URL = "https://townhallstreams.com/stream.php?location_id=72&id=74003"
HLS = "https://cdn.townhallstreams.com/vod/_definst_/mp4:hollis_nh/event.mp4/playlist.m3u8"
SOURCE = Source("town-hall-streams", URL, input_format="town-hall-streams-event-html",
                options={"download_origins": ["https://cdn.townhallstreams.com"]})
HTML = ('''<p><a href="town.php?id=72">Back</a> | Budget Committee<br>
<span>Nov, 10 2026 07:00 pm - 11:30 pm</span></p>
<script>var url="stream.php?location_id=72&id=74003&action=get_transcriptions";
var originalFile = "''' + HLS + '''";
var resolveFile = thsPlayableHlsUrl(originalFile);
resolveFile.then(function(file) { jwplayer("myElement").setup({ file: file, type: "hls" }); });
</script>''').encode()


def test_saved_exact_event_player_and_hls_locator_keep_provenance():
    result = create_engine().normalize(SOURCE, HTML, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "74003"
    assert record["identity"]["namespace"] == "//townhallstreams.com?location_id=72"
    assert record["normalized"]["title"] == "Budget Committee"
    assert record["normalized"]["scheduled_start"] == "2026-11-10T19:00:00"
    assert record["normalized"]["time_zone_status"] == "unknown"
    recording = record["normalized"]["recordings"][0]
    assert recording["url"] == URL and recording["playback_url"] == HLS
    assert recording["media_bytes_verified"] is False
    assert "video_url" not in recording
    assert base64.b64decode(result.data["capture"]["content_base64"]) == HTML


def test_configured_engine_get_then_explicit_hls_playlist_transfer_only():
    class Transport:
        def __init__(self):
            self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            assert "action=" not in url
            return Response(url, HTML if url == URL else b"#EXTM3U\nsegment.ts\n",
                            "text/html" if url == URL else "application/vnd.apple.mpegurl")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.fetch(SOURCE)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record = result.data["records"][0]
    playlist = engine.fetch_attachment(SOURCE, record, kind="recordings", url_field="playback_url", capture=HTML)
    assert playlist.status == "completed", playlist.public_dict()
    assert playlist.data["attachment"]["content_type"] == "application/vnd.apple.mpegurl"
    assert transport.calls == [URL, HLS]  # No segment request or transcript AJAX.
    ungranted = Source(SOURCE.provider, SOURCE.url, input_format=SOURCE.input_format)
    denied = engine.fetch_attachment(ungranted, record, kind="recordings", url_field="playback_url", capture=HTML)
    assert denied.status == "partial"
    assert transport.calls == [URL, HLS]


@pytest.mark.parametrize("media", ["https://other.example/vod/file/playlist.m3u8",
                                  HLS + "?token=opaque", "http://cdn.townhallstreams.com/vod/x/playlist.m3u8"])
def test_unverified_or_private_query_media_is_not_promoted(media):
    result = create_engine().normalize(SOURCE, HTML.replace(HLS.encode(), media.encode()), input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert "playback_url" not in result.data["records"][0]["normalized"]["recordings"][0]


@pytest.mark.parametrize("body", [HTML.replace(b"id=74003", b"id=74004"),
                                 HTML.replace(b"town.php?id=72", b"town.php?id=73"), b"<html>Shell</html>"])
def test_wrong_event_location_or_missing_header_fails(body):
    assert create_engine().normalize(SOURCE, body, input_format=SOURCE.input_format).status == "failed"
