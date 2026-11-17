"""Pinned EventModel fields, synthetic transfers; no player or ASR inference."""

import base64
from copy import deepcopy
import json

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

API = "https://fishersin.api.civicclerk.com"
MEDIA = "https://cpmedia.azureedge.net"
SOURCE = Source("civicplus-select", API + "/v1/Events", options={"download_origins": [MEDIA]})
EVENT = {
    "id": 7,
    "agendaId": 91,
    "eventName": "Council caption evidence",
    "startDateTime": "2026-11-01T18:00:00Z",
    "isPublished": "Published",
    "isDeleted": False,
    "mediaSourcePathMp4": MEDIA + "/synthetic.mp4",
    "closedCaptionSourcePath": MEDIA + "/synthetic.vtt",
    "closedCaptionBlobPath": MEDIA + "/synthetic.vtt",
    "closedCaptionFileName": "Council.vtt",
    "unknown": {"preserve": [False, None]},
}
VTT = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nSupplied council words.\n"


class Network:
    def __init__(self):
        self.calls, self.redirect, self.cancel = [], False, None

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs.get("allow_redirects") is False
        if url == API + "/v1/Meetings/91":
            return Response(url, b'{"id":91,"items":[],"publishedFiles":[]}', "application/json")
        assert url in {EVENT["mediaSourcePathMp4"], EVENT["closedCaptionSourcePath"]}
        if self.cancel:
            self.cancel.cancellation.set()
        return Response(
            url + "/changed" if self.redirect else url,
            VTT if url.endswith(".vtt") else b"synthetic-video-bytes",
            "text/vtt" if url.endswith(".vtt") else "video/mp4",
        )


def setup(tmp_path, event=None):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "assets.sqlite"), provider_transport=network)
    original = json.dumps({"value": [event or EVENT]}).encode()
    result = engine.execute("discover", {"source": SOURCE.public_dict()}, content=original)
    assert result.status == "partial" and not result.errors, result.public_dict()
    return engine, network, original, result.data["bundles"][0]


def test_invalid_caption_title_remains_raw_without_becoming_normalized_text(tmp_path):
    event = {**EVENT, "closedCaptionFileName": {"unexpected": True}}
    _, _, _, bundle = setup(tmp_path, event)
    record = bundle["records"][0]
    assert record["original"] == event
    assert record["normalized"]["documents"][0]["title"] == "Supplied closed captions"


@pytest.mark.parametrize("detail", [False, True])
def test_supplied_assets_survive_detail_sqlite_reopen_transfer_and_exact_zip(tmp_path, detail):
    engine, network, original, bundle = setup(tmp_path)
    assert not network.calls
    assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    if detail:
        result = engine.fetch_record(SOURCE, "7")
        assert result.status == "partial" and not result.errors, result.public_dict()
        bundle = result.data
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    record = bundle["records"][0]
    normalized = record["normalized"]
    assert len(normalized["documents"]) == 1  # Same caption URL in two fields is one locator.
    assert normalized["documents"][0]["kind"] == "transcript"
    assert normalized["recordings"][0]["video_url"] == EVENT["mediaSourcePathMp4"]
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "assets.sqlite"), provider_transport=network)
    captions = reopened.fetch_attachment(SOURCE, record)
    video = reopened.fetch_attachment(SOURCE, record, kind="recordings", url_field="video_url")
    assert captions.status == video.status == "completed", (captions.public_dict(), video.public_dict())
    assert base64.b64decode(captions.data["attachment"]["content_base64"]) == VTT
    assert captions.data["attachment"]["text_availability"] == "not_extracted"
    archive = reopened.execute("export", {"bundle": bundle, "format": "zip"})
    restored = read_bundle(base64.b64decode(archive.data["content_base64"]), format="zip")
    assert restored == bundle
    if not detail:
        assert base64.b64decode(restored["capture"]["content_base64"]) == original
    else:
        assert restored["records"][0]["original"]["event"] == EVENT


@pytest.mark.parametrize(
    "url",
    [
        "/relative.vtt",
        "http://example.org/captions.vtt",
        "https://127.0.0.1/captions.vtt",
        "https://u:p@example.org/captions.vtt",
        "https://example.org/captions.vtt#fragment",
        "https://example.org/captions.vtt?token=secret",
    ],
)
def test_unsafe_or_unqualified_caption_paths_are_retained_raw_without_locator(tmp_path, url):
    event = deepcopy(EVENT)
    event.update(closedCaptionSourcePath=url, closedCaptionBlobPath=url)
    _, network, _, bundle = setup(tmp_path, event)
    assert bundle["records"][0]["normalized"]["documents"] == []
    assert bundle["records"][0]["original"]["closedCaptionSourcePath"] == url
    assert not network.calls


@pytest.mark.parametrize("fault", ["url", "native_id", "publication", "raw_url"])
def test_tampered_asset_binding_fails_before_network(tmp_path, fault):
    engine, network, _, bundle = setup(tmp_path)
    assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    record = bundle["records"][0]
    key = source_identity_key(record["identity"])
    scope = OperationContext().scope
    stored = engine.storage.get("records", key, scope=scope)
    value = deepcopy(stored.value)
    row = value.get("record", value)
    if fault == "url":
        row["normalized"]["documents"][0]["url"] = MEDIA + "/other.vtt"
    elif fault == "native_id":
        row["original"]["id"] = 8
    elif fault == "publication":
        row["original"]["isPublished"] = "Private"
    else:
        row["original"]["closedCaptionSourcePath"] = MEDIA + "/other.vtt"
    engine.storage.put("records", key, value, scope=scope, expected_version=stored.version)
    result = engine.fetch_attachment(SOURCE, record)
    assert result.status == "failed", result.public_dict()
    assert not network.calls


@pytest.mark.parametrize("fault", ["origin_policy", "redirect", "cancel"])
def test_transfer_requires_current_origin_exact_response_url_and_cancellation(tmp_path, fault):
    engine, network, raw, bundle = setup(tmp_path)
    source, context = SOURCE, OperationContext()
    if fault == "origin_policy":
        source = Source("civicplus-select", SOURCE.url)
    elif fault == "redirect":
        network.redirect = True
    else:
        network.cancel = context
    result = engine.fetch_attachment(source, bundle["records"][0], capture=raw, context=context)
    assert result.status == ("cancelled" if fault == "cancel" else "partial"), result.public_dict()
    if fault == "origin_policy":
        assert not network.calls


def test_mp4_property_does_not_expand_relative_paths_or_treat_player_as_media(tmp_path):
    event = deepcopy(EVENT)
    event["mediaSourcePathMp4"] = MEDIA + "/player"
    _, _, _, bundle = setup(tmp_path, event)
    assert bundle["records"][0]["normalized"].get("recordings", []) == []


@pytest.mark.parametrize("fault", ["field_removed", "unknown_field", "url", "raw_url"])
def test_recording_cannot_bypass_binding_by_removing_its_source_field(tmp_path, fault):
    engine, network, _, bundle = setup(tmp_path)
    assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    record = bundle["records"][0]
    key = source_identity_key(record["identity"])
    scope = OperationContext().scope
    stored = engine.storage.get("records", key, scope=scope)
    value = deepcopy(stored.value)
    row = value.get("record", value)
    selected = row["normalized"]["recordings"][0]
    if fault == "field_removed":
        selected.pop("source_field")
    elif fault == "unknown_field":
        selected["source_field"] = "invented"
    elif fault == "url":
        selected.update(url=MEDIA + "/other.mp4", video_url=MEDIA + "/other.mp4")
    else:
        row["original"]["mediaSourcePathMp4"] = MEDIA + "/other.mp4"
    engine.storage.put("records", key, value, scope=scope, expected_version=stored.version)
    assert (
        engine.fetch_attachment(SOURCE, record, kind="recordings", url_field="video_url").status == "failed"
    )
    assert not network.calls


def test_existing_media_stream_descriptor_remains_downloadable(tmp_path):
    event = deepcopy(EVENT)
    event["mediaStreamPath"] = event.pop("mediaSourcePathMp4")
    engine, network, raw, bundle = setup(tmp_path, event)
    result = engine.fetch_attachment(
        SOURCE, bundle["records"][0], kind="recordings", url_field="video_url", capture=raw
    )
    assert result.status == "completed", result.public_dict()
