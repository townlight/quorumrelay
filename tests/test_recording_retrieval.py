import base64
from dataclasses import replace
import io
import json

from starlette.testclient import TestClient

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response
from civic_data_connectors.cli import main
from civic_data_connectors.transports.http import create_app
from test_interfaces import TOKEN_A, config

SOURCE = Source("granicus", "https://townofsuperior.granicus.com/ViewPublisher.php?view_id=2",
    input_format="granicus-listing-html", options={"download_origins": ["https://archive-video.granicus.com"]})
VIDEO = "https://archive-video.granicus.com/townofsuperior/synthetic.mp4"
CAPTURE = b'''<table><tr><td headers="Name">Council</td><td headers="Date">November 10, 2026</td>
<td headers="VideoLink"><a href="MediaPlayer.php?view_id=2&amp;clip_id=100">Video</a></td>
<td headers="MP4Link"><a href="https://archive-video.granicus.com/townofsuperior/synthetic.mp4">MP4</a></td></tr></table>'''
MEDIA = b"synthetic-mp4-test-bytes" * 500


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == VIDEO:
            return Response(url, MEDIA, "video/mp4")
        return Response(url, b"synthetic player HTML", "text/html")


def setup():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.execute("discover", {"source": SOURCE.public_dict()}, content=CAPTURE)
    record = result.data["records"][0]
    return engine, transport, record


def test_selected_captured_video_uses_transfer_ceiling_and_keeps_player_citation():
    engine, transport, record = setup()
    bounds = Bounds(parser_bytes=1024, transfer_bytes=20000)
    default = engine.fetch_attachment(SOURCE, record, kind="recordings", capture=CAPTURE, bounds=bounds)
    assert default.data["attachment"]["content_type"] == "text/html"
    result = engine.fetch_attachment(SOURCE, record, kind="recordings", url_field="video_url", capture=CAPTURE, bounds=bounds)
    assert result.status == "completed", result.public_dict()
    attachment = result.data["attachment"]
    assert attachment["citation_url"].startswith("https://townofsuperior.granicus.com/MediaPlayer.php")
    assert attachment["selected_url_field"] == "video_url" and base64.b64decode(attachment["content_base64"]) == MEDIA
    assert transport.calls[-1][1]["byte_limit"] == 20000 and len(MEDIA) > 1024
    ungranted = replace(SOURCE, options={})
    count = len(transport.calls)
    assert engine.fetch_attachment(ungranted, record, kind="recordings", url_field="video_url", capture=CAPTURE).status == "partial"
    assert len(transport.calls) == count


def test_selector_cannot_supply_urls_access_unknown_fields_or_bypass_current_namespace():
    engine, transport, record = setup()
    for field in ["https://other.example/file", "source_fields", "__dict__"]:
        assert engine.fetch_attachment(SOURCE, record, kind="recordings", url_field=field, capture=CAPTURE).status == "failed"
    assert engine.fetch_attachment(SOURCE, record, kind="documents", url_field="video_url", capture=CAPTURE).status == "failed"
    denied = engine.fetch_attachment(SOURCE, record, kind="recordings", url_field="video_url", capture=CAPTURE,
        context=OperationContext(allowed_namespaces=frozenset()))
    assert denied.status == "failed" and not transport.calls


def test_cli_and_http_forward_the_same_scoped_captured_selector():
    engine, transport, record = setup()
    request = {"source": SOURCE.public_dict(), "content_base64": base64.b64encode(CAPTURE).decode(),
        "attachment": {"record_key": source_identity_key(record["identity"]), "index": 0,
                       "kind": "recordings", "url_field": "video_url"}}
    stdout, stderr = io.StringIO(), io.StringIO()
    assert main(["fetch"], stdin=io.StringIO(json.dumps(request)), stdout=stdout, stderr=stderr, engine=engine) == 0
    assert json.loads(stdout.getvalue())["data"]["attachment"]["selected_url_field"] == "video_url"
    with TestClient(create_app(engine, config()), base_url="http://127.0.0.1") as client:
        result = client.post("/v1/operations/fetch", headers={"Authorization": "Bearer " + TOKEN_A}, json=request).json()
        assert result["status"] == "completed", result
        assert result["data"]["attachment"]["content_type"] == "video/mp4"
    assert len(transport.calls) == 2 and all(url == VIDEO for url, _ in transport.calls)
