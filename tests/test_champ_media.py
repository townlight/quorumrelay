"""CHAMP media mapping tests use captured public event data only."""

import json
from copy import deepcopy
from pathlib import Path

from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.providers.champ_media import enrich_bundle


FIXTURE = Path(__file__).parent / "fixtures" / "brief-discovery" / "champ-lakezurich-event-json.json"
PLAYER = "https://play.champds.com/lakezurichil/event/164"
MANIFEST = (
    "https://securestream10.champds.com/VOD/event/LakeZurichIL/164/1755743324000/"
    "NbM2X6jRuGoNVYQKKU3uOQ/master.m3u8"
)
DIRECT = "https://securestream10.champds.com/2025-08/840e60104998127e7aa69b10329168b16101a3b8.mp4"


def bundle_for(raw=None):
    original = deepcopy(raw if raw is not None else json.loads(FIXTURE.read_text(encoding="utf-8")))
    normalized = {
        "external_id": "164",
        "title": "Regular Meeting",
        "url": PLAYER,
        "recordings": [{"url": PLAYER}],
    }
    return {
        "source": {"provider": "champ", "url": "https://play.champds.com/lakezurichil/event/164"},
        "records": [{
            "identity": {"provider": "champ", "external_id": "164"},
            "original": original,
            "normalized": normalized,
            "normalized_sha256": canonical_hash(normalized),
            "relationships": [{"relation": "recording", "value": {"url": PLAYER}}],
            "citation_urls": [PLAYER],
        }],
    }


def playback_record(bundle):
    records = bundle["records"][0]["normalized"]["recordings"]
    return next(item for item in records if item.get("url") != PLAYER)


def test_vod2_adds_hls_manifest_and_keeps_original_player_and_capture():
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle = bundle_for(original)

    enriched = enrich_bundle(bundle)

    record = enriched["records"][0]
    playback = playback_record(enriched)
    assert playback["url"] == MANIFEST
    assert playback["representation"] == "hls_manifest"
    assert playback["citation_url"] == PLAYER
    assert "video_url" not in playback
    assert playback["source_fields"]["media_info"] == original["MediaInfo"]
    assert playback["source_fields"]["service_info"] == original["ServicesAndMachineInfo"]["8"]
    assert record["normalized"]["recordings"][0] == {"url": PLAYER}
    assert record["relationships"][0]["value"] == {"url": PLAYER}
    assert record["relationships"][-1]["value"] == playback
    assert record["citation_urls"] == [PLAYER]
    assert record["original"] == original
    assert bundle["records"][0]["original"] == original
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])


def test_fallback_uses_service_eight_and_replaces_only_first_media_token():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["MediaInfo"]["VOD2"] = ""
    raw["ServicesAndMachineInfo"]["8"]["URLFilename"] = "%MEDIA_PATH%?PLAY&mirror=%MEDIA_PATH%"
    bundle = bundle_for(raw)

    enriched = enrich_bundle(bundle)

    playback = playback_record(enriched)
    assert playback["url"] == DIRECT + "?PLAY&mirror=%MEDIA_PATH%"
    assert playback["representation"] == "direct_media"
    assert playback["video_url"] == playback["url"]
    assert playback["citation_url"] == PLAYER


def test_vod2_uses_service_2048_when_present():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["ServicesAndMachineInfo"]["2048"] = {
        "CustomerServiceID": 9,
        "ServiceTypeID": 2048,
        "URLBase": "https://vod.example.invalid",
        "URLFilename": "%MEDIA_PATH%/unused.mp4",
    }
    bundle = bundle_for(raw)

    enriched = enrich_bundle(bundle)

    playback = playback_record(enriched)
    assert playback["url"] == "https://vod.example.invalid" + raw["MediaInfo"]["VOD2"]
    assert playback["representation"] == "hls_manifest"
    assert playback["source_fields"]["service_info"]["ServiceTypeID"] == 2048
    assert "video_url" not in playback


def test_non_vod_unknown_extension_and_invalid_urls_fail_closed():
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = []

    not_vod = deepcopy(base)
    not_vod["MediaInfo"]["MediaType"] = "LIVE"
    cases.append(not_vod)

    unknown_extension = deepcopy(base)
    unknown_extension["MediaInfo"]["VOD2"] = "/VOD/event/164/master.webm"
    cases.append(unknown_extension)

    private_base = deepcopy(base)
    private_base["ServicesAndMachineInfo"]["8"]["URLBase"] = "https://127.0.0.1/stream"
    cases.append(private_base)

    non_https_base = deepcopy(base)
    non_https_base["ServicesAndMachineInfo"]["8"]["URLBase"] = "http://stream.example.invalid"
    cases.append(non_https_base)

    cross_origin_media_path = deepcopy(base)
    cross_origin_media_path["MediaInfo"]["VOD2"] = "https://media.example.invalid/a/master.m3u8"
    cases.append(cross_origin_media_path)

    credentialed_base = deepcopy(base)
    credentialed_base["ServicesAndMachineInfo"]["8"]["URLBase"] = (
        "https://user:password@securestream10.champds.com"
    )
    cases.append(credentialed_base)

    for raw in cases:
        bundle = bundle_for(raw)
        enriched = enrich_bundle(bundle)
        assert enriched["records"][0]["normalized"]["recordings"] == [{"url": PLAYER}]
        assert enriched["records"][0]["relationships"] == [
            {"relation": "recording", "value": {"url": PLAYER}}
        ]
        assert enriched["records"][0]["original"] == raw


def test_wrong_event_identity_is_not_enriched_and_repeated_enrichment_is_idempotent():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mismatched = bundle_for(raw)
    mismatched["records"][0]["identity"]["external_id"] = "999"
    assert enrich_bundle(mismatched)["records"][0]["normalized"]["recordings"] == [{"url": PLAYER}]

    first = enrich_bundle(bundle_for(raw))
    second = enrich_bundle(first)
    assert len(second["records"][0]["normalized"]["recordings"]) == 2
    assert len(second["records"][0]["relationships"]) == 2
    assert second["records"][0]["normalized_sha256"] == first["records"][0]["normalized_sha256"]


def test_discovery_wires_additive_playback_without_changing_saved_normalization():
    from quorumrelay import Source, create_engine

    engine = create_engine()
    source = Source("champ", PLAYER, input_format="champ-event-json")
    content = FIXTURE.read_bytes()
    result = engine.execute("discover", {"source": source.public_dict()}, content=content)
    assert result.data["records"], result.public_dict()
    record = result.data["records"][0]
    assert any(item.get("url") == MANIFEST for item in record["normalized"]["recordings"])
    assert record["original"] == json.loads(content)
