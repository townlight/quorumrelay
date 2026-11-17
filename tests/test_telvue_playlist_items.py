"""Synthetic account execution anchored to TelVue's published v2 example."""

import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from test_account_apis import TELVUE, Network, context

FIXTURE = Path(__file__).parent / "fixtures/telvue-playlist_item-example.json"


@pytest.mark.parametrize("detail", [False, True])
def test_documented_playlist_item_route_identity_relationships_and_saved_replay(detail):
    item = json.loads(FIXTURE.read_bytes())["playlist_item"]
    value = {"playlist_item": item} if detail else {"playlist_items": [item]}
    network = Network(value)
    engine = create_engine(provider_transport=network)
    source = Source("telvue", TELVUE, namespace="account-a")
    request = {"api_resource": "playlist_items", "playlist_id": "837"}
    if detail:
        request["external_id"] = "37883"
    result = engine.fetch(source, request, context=context("telvue"))
    assert result.status == "partial", result.public_dict()
    assert network.calls[0][0] == TELVUE + "/api/v2/playlists/837/playlist_items" + (
        "/37883" if detail else "") + ".json"
    record = result.data["records"][0]
    assert record["identity"]["record_type"] == "playlist_item"
    assert record["identity"]["external_id"] == "37883"
    assert record["identity"]["parent"]["external_id"] == "837"
    assert record["identity"]["parent"]["record_type"] == "playlist"
    playable = next(r["identity"] for r in record["relationships"] if r["relation"] == "playable")
    assert playable["record_type"] == "media" and playable["external_id"] == "32263"
    assert playable["namespace"] == "account-a" and playable["parent"] is None
    assert record["normalized"]["sequence_number"] == 2
    assert record["normalized"]["recordings"][0]["duration_seconds"] == 306
    assert record["original"] == item
    assert "meeting_date" not in record["normalized"]
    assert all(r["relation"] != "meeting" for r in record["relationships"])
    raw = base64.b64decode(result.data["capture"]["content_base64"])
    assert json.loads(raw) == value
    replay = engine.normalize(source, raw, input_format="telvue-connect-playlist_items-json")
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert result.coverage["catalog_complete"] is False
    assert "synthetic-long" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("change", ["playlist", "detail", "duplicate"])
def test_playlist_response_identity_mismatch_is_rejected(change):
    item = json.loads(FIXTURE.read_bytes())["playlist_item"]
    request = {"api_resource": "playlist_items", "playlist_id": "837"}
    if change == "playlist":
        item["playlist_id"] = 838
    if change == "detail":
        request["external_id"] = "37882"
    value = {"playlist_items": [item, deepcopy(item)] if change == "duplicate" else [item]}
    engine = create_engine(provider_transport=Network(value))
    assert engine.fetch(Source("telvue", TELVUE, namespace="account-a"), request,
                        context=context("telvue")).status == "failed"


def test_playlist_route_requires_path_safe_explicit_parent_before_network():
    network = Network({"playlist_items": []})
    engine = create_engine(provider_transport=network)
    source = Source("telvue", TELVUE, namespace="account-a")
    for parent in (None, "../837", "0", 837):
        result = engine.fetch(source, {"api_resource": "playlist_items", "playlist_id": parent},
                              context=context("telvue"))
        assert result.status == "failed"
    assert network.calls == []


def test_published_example_pin_and_unknown_playable_are_preserved():
    pin = json.loads((Path(__file__).parents[1] /
        "docs/capabilities/evidence/telvue-connect-playlist-items/source.json").read_bytes())
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == pin["sha256"]
    assert "transcription" in pin["proof"]
    item = json.loads(FIXTURE.read_bytes())["playlist_item"]
    item["playable"]["type"] = "vendor-unmapped-type"
    item["unknown"] = [None, False]
    result = create_engine().normalize(Source("telvue", TELVUE, namespace="account-a"),
        json.dumps({"playlist_item": item}).encode(), input_format="telvue-connect-playlist_items-json")
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["original"] == item
    assert all(r["relation"] != "playable" for r in record["relationships"])
