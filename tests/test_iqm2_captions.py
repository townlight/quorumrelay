"""Active-track branch is synthetic; the actual6049 player has no supplied track."""
import base64
from dataclasses import replace
import hashlib

import pytest
from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from test_iqm2_player import CAPTURE, SOURCE, declared

TARGET = "https://media.example.org/public.vtt"
PLAYER = declared([{"file": "https://media.example.org/public.mp4", "tracks": [{"file": TARGET}]}])
SOURCE = replace(SOURCE, options={"download_origins": ["https://media.example.org"]})
VTT = b"WEBVTT\n\n00:00.000 --> 00:02.000\nSupplied council testimony.\n"


class Network:
    def __init__(self, *, player=PLAYER, response=None):
        self.calls, self.player, self.after_request = [], player, None
        self.response = response or Response(TARGET, VTT, "text/vtt; charset=utf-8")

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False and options["deadline_seconds"] > 0
        if self.after_request:
            self.after_request()
        if url == SOURCE.url:
            return Response(url, self.player, "text/html")
        assert url == TARGET and options["allowed_origins"] == (
            "https://kentwa.iqm2.com", "https://media.example.org")
        return self.response


def test_supplied_webvtt_exact_text_bytes_provenance_reopen_search_and_zip(tmp_path):
    network = Network()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    context = OperationContext(principal="reader", tenant="city", client_id="app")
    result = owner.fetch_captions(SOURCE, "6049", context=context)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "6049"
    assert record["normalized"]["supplied_caption_text"] == VTT.decode()
    assert record["normalized"]["content_language"] is None
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])
    assert record["relationships"][0]["value"] == record["normalized"]["recordings"][0]
    captured = result.data["captures"][0]
    assert captured["source_url"] == TARGET and base64.b64decode(captured["content_base64"]) == VTT
    assert captured["sha256"] == hashlib.sha256(VTT).hexdigest()
    assert record["text"][0]["provenance"]["capture_sha256"] == captured["sha256"]
    assert len(network.calls) == 2 and result.coverage["pages"] == 2
    assert network.calls[1][1]["byte_limit"] == min(Bounds().parser_bytes, Bounds().transfer_bytes - len(PLAYER))
    assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}, context=context).status == "completed"
    owner = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    found = owner.execute("search", {"query": {"phrases": ["Supplied council testimony"]}}, context=context)
    assert found.data["hits"], found.public_dict()
    exported = owner.execute("export", {"format": "zip", "bundle": result.data}, context=context)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data


def test_actual_player_with_no_active_track_never_guesses_a_caption_url():
    network = Network(player=CAPTURE)
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "6049")
    assert result.status == "partial" and not result.errors
    assert result.coverage["caption_file_received"] is False and len(network.calls) == 1


@pytest.mark.parametrize("case", ["identity", "language", "one_page", "checkpoint", "wrong_source", "permission"])
def test_unbound_or_unsupported_caption_selection_is_rejected_before_io(case):
    network = Network()
    source, identity, options = SOURCE, "6049", {}
    if case == "identity":
        identity = "6050"
    elif case == "language":
        options["language"] = "en"
    elif case == "one_page":
        options["bounds"] = Bounds(max_pages=1)
    elif case == "checkpoint":
        options["bounds"] = Bounds(checkpoint="unbound")
    elif case == "wrong_source":
        source = Source("iqm2", "https://kentwa.iqm2.com/Citizens/Detail_Meeting.aspx?ID=6049")
    else:
        options["context"] = OperationContext(allowed_operations=frozenset({"parse"}))
    result = create_engine(provider_transport=network).fetch_captions(source, identity, **options)
    assert result.status in {"failed", "unsupported"}, result.public_dict()
    assert not network.calls


@pytest.mark.parametrize("response", [Response(TARGET, b"<html>Sign in</html>", "text/html"),
    Response(TARGET, b"not a VTT", "text/vtt"), Response(TARGET, b"WEBVTT --> invalid\n", "text/vtt"),
    Response(TARGET, b"WEBVTT\n\xff", "text/vtt"), Response(TARGET, VTT, "text/vtt", 403),
    Response(TARGET + "?other=1", VTT, "text/vtt")])
def test_failed_track_keeps_player_partial_and_never_indexes_unrecognized_bytes(response):
    result = create_engine(provider_transport=Network(response=response)).fetch_captions(SOURCE, "6049")
    assert result.status == "partial" and result.errors, result.public_dict()
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]
    assert not result.data.get("captures")


def test_cross_origin_requires_explicit_permission_and_cancellation_stops_requests():
    network = Network()
    owner = create_engine(provider_transport=network)
    result = owner.fetch_captions(replace(SOURCE, options={}), "6049")
    assert result.status == "partial" and result.errors and len(network.calls) == 1
    context = OperationContext()
    context.cancellation.set()
    assert owner.fetch_captions(SOURCE, "6049", context=context).status == "cancelled"
    assert len(network.calls) == 1
    context.cancellation.clear()
    network.after_request = context.cancellation.set
    assert owner.fetch_captions(SOURCE, "6049", context=context).status == "cancelled"
    assert len(network.calls) == 2


def test_aggregate_transfer_and_post_response_deadline_are_enforced(monkeypatch):
    network = Network()
    owner = create_engine(provider_transport=network)
    result = owner.fetch_captions(SOURCE, "6049", bounds=Bounds(transfer_bytes=len(PLAYER)+len(VTT)-1))
    assert result.status == "partial" and result.errors
    assert network.calls[1][1]["byte_limit"] == len(VTT)-1
    from civic_data_connectors.providers import iqm2_player
    clock = [0.0]
    monkeypatch.setattr(iqm2_player, "monotonic", lambda: clock[0])
    network.after_request = lambda: clock.__setitem__(0, 2.0)
    result = owner.fetch_captions(SOURCE, "6049", bounds=Bounds(deadline_seconds=1))
    assert result.status == "failed" and len(network.calls) == 3


def test_cancellation_after_track_read_keeps_only_the_captured_player():
    network = Network()
    context = OperationContext()
    network.after_request = lambda: context.cancellation.set() if len(network.calls) == 2 else None
    result = create_engine(provider_transport=network).fetch_captions(SOURCE, "6049", context=context)
    assert result.status == "cancelled" and len(network.calls) == 2
    assert "supplied_caption_text" not in result.data["records"][0]["normalized"]
    assert not result.data.get("captures")


def test_utf8_bom_and_empty_supplied_caption_are_preserved_without_generation():
    content = b"\xef\xbb\xbfWEBVTT\r\n\r\n"
    result = create_engine(provider_transport=Network(response=Response(TARGET, content, "text/vtt"))).fetch_captions(SOURCE, "6049")
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.data["records"][0]["normalized"]["supplied_caption_text"] == "WEBVTT\r\n\r\n"
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == content
    assert result.coverage["generation_requested"] is False
