"""Public literal iframe metadata and source captions; no player execution."""
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.providers import wistia_embed as embed
from civic_data_connectors.providers.contracts import Response

URL = "https://fast.wistia.net/embed/iframe/ylfk2zpd7f"
SOURCE = Source("wistia", URL, input_format=embed.FORMAT)
FIXTURE = Path(__file__).parent / "fixtures/wistia-public/iframe-ylfk2zpd7f.html"
VALUE = {"hashedId": "ylfk2zpd7f", "name": "Source media", "assets": [],
    "captions": [{"language": "eng", "text": "Literal source caption.", "unknown_native": 9}]}


def html(value):
    return ("<script>W.iframeInit(" + json.dumps(value) + ", {});</script>").encode()


class Server:
    def __init__(self, content=None):
        self.content = FIXTURE.read_bytes() if content is None else content
        self.status = 200
        self.mime = "text/html; charset=UTF-8"
        self.url = URL
        self.calls = []
        self.after = lambda: None

    def request(self, url, **options):
        assert url == URL and "Authorization" not in (options.get("headers") or {})
        assert options["allowed_origins"] == ("https://fast.wistia.net",)
        self.calls.append(options)
        self.after()
        return Response(self.url, self.content, self.mime, self.status)


def test_captured_public_player_source_text_search_reopen_and_all_exports(tmp_path):
    server = Server()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "public.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert server.calls[0]["allow_redirects"] is False
    recording, caption = result.data["records"]
    assert recording["identity"]["external_id"] == "ylfk2zpd7f"
    assert caption["original"]["language"] == "eng" and len(caption["original"]["text"]) == 1366
    assert caption["normalized"]["native_language_key"] == "eng"
    assert "timestamp_seconds" not in caption["text"][0]
    assert source_identity_key(caption["relationships"][0]["identity"]) == source_identity_key(recording["identity"])
    assert base64.b64decode(result.data["capture"]["content_base64"]) == FIXTURE.read_bytes()
    assert result.coverage["caption_tracks"] == 1 and not result.coverage["media_bytes_downloaded"]
    normalized = owner.normalize(SOURCE, FIXTURE.read_bytes(), input_format=embed.FORMAT)
    assert normalized.status == "completed", normalized.public_dict()
    assert normalized.data["records"][1]["original"] == caption["original"]
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "public.sqlite"))
    hits = reopened.execute("search", {"query": {"phrases": ["great time saver"],
        "record_types": ["transcript"]}}).data["hits"]
    assert len(hits) == 1 and hits[0]["record"]["identity"]["record_type"] == "transcript"
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("case", ["wrong_id", "expression", "duplicate_init", "duplicate_key", "duplicate_language",
    "caption_shape", "caption_text", "http", "mime", "origin", "record_bound", "byte_bound", "cancel", "deadline"])
def test_public_embed_failures_do_not_become_complete_empty_success(case, monkeypatch):
    value = deepcopy(VALUE)
    server = Server(html(value))
    caller, bounds = OperationContext(), Bounds()
    if case == "wrong_id":
        value["hashedId"] = "other"
    elif case == "duplicate_language":
        value["captions"] *= 2
    elif case == "caption_shape":
        value["captions"] = {}
    elif case == "caption_text":
        value["captions"][0]["text"] = 3
    if case in {"wrong_id", "duplicate_language", "caption_shape", "caption_text"}:
        server.content = html(value)
    elif case == "expression":
        server.content = b"<script>W.iframeInit(getData(), {});</script>"
    elif case == "duplicate_init":
        server.content *= 2
    elif case == "duplicate_key":
        server.content = server.content.replace(b'"name":', b'"name":"first","name":')
    elif case == "http":
        server.status = 403
    elif case == "mime":
        server.mime = "application/json"
    elif case == "origin":
        server.url = "https://example.org/"
    elif case == "record_bound":
        bounds = Bounds(max_records=1)
    elif case == "byte_bound":
        bounds = Bounds(transfer_bytes=16)
    elif case == "cancel":
        server.after = caller.cancellation.set
    elif case == "deadline":
        now = [100.0]
        monkeypatch.setattr(embed, "monotonic", lambda: now[0])
        server.after = lambda: now.__setitem__(0, 1000.0)
    result = create_engine(provider_transport=server).fetch(SOURCE, bounds=bounds, context=caller)
    assert result.status == ("cancelled" if case == "cancel" else "failed"), result.public_dict()
    assert result.data is None


@pytest.mark.parametrize("case", ["query", "host", "date", "external_id", "caption_language", "related"])
def test_unsupported_public_embed_selectors_rejected_before_network(case):
    server = Server()
    source, request, bounds = SOURCE, {}, Bounds()
    if case == "query":
        source = Source("wistia", URL + "?autoplay=1", input_format=embed.FORMAT)
    elif case == "host":
        source = Source("wistia", URL.replace("fast.", "api."), input_format=embed.FORMAT)
    elif case == "date":
        bounds = Bounds(date_from="2026-11-01", date_to="2026-11-30")
    else:
        request[case] = "unmapped"
    result = create_engine(provider_transport=server).fetch(source, request, bounds=bounds)
    assert result.status == "failed" and not server.calls


def test_explicit_iframe_discovery_resumes_within_caption_records_without_duplicates():
    server = Server()
    owner = create_engine(provider_transport=server)
    request = {"source": SOURCE.public_dict(), "bounds": {"max_records": 1}}
    first = owner.execute("discover", request)
    assert first.status == "partial" and first.coverage["checkpoint"], first.public_dict()
    request["bounds"]["checkpoint"] = first.coverage["checkpoint"]
    second = owner.execute("discover", request)
    assert second.status == "partial" and not second.errors and second.coverage["checkpoint"] is None, second.public_dict()
    assert [r["identity"]["record_type"] for r in first.data["records"] + second.data["records"]] == [
        "recording", "transcript"]
