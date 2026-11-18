"""Optional OriginalFile evidence uses existing approved reads, with no CDN fetch."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from civic_data_connectors.providers.wistia_swap_readback import swap_asset_evidence
from tests.test_wistia_swap import plan, setup


def media(identity, asset_name):
    return {"hashed_id": identity, "type": "Video", "assets": [{
        "type": "OriginalFile", "url": f"https://embed-ssl.wistia.com/deliveries/{asset_name}.bin",
        "file_size": 12345, "content_type": "video/mp4"}]}


def test_modern_asset_fields_and_public_url_structure_are_vendor_documented():
    contracts = json.loads((Path(__file__).parents[1] /
        "docs/capabilities/provider-api-contracts.json").read_text(encoding="utf-8"))
    contract = next(row for row in contracts["wistia"]
                    if row["source_url"].endswith("get_medias-mediahashedid.md"))
    schema = contract["spec"]["paths"]["/medias/{mediaHashedId}"]["get"]["responses"]["200"][
        "content"]["application/json"]["schema"]
    assert contract["spec"]["info"]["version"] == "2026.09.0"
    assert "https://fast.wistia.com/embed/medias/{hashed_id}.m3u8" in schema["allOf"][0]["description"]
    assets_schema = next(row["properties"]["assets"] for row in schema["allOf"]
                         if "assets" in row.get("properties", {}))
    assert "OriginalFile" in assets_schema["items"]["properties"]["type"]["description"]
    Draft202012Validator(assets_schema).validate(media("original", "old")["assets"])


def test_finished_job_adds_asset_evidence_without_extra_reads(tmp_path):
    engine, context, network, request = setup(tmp_path)
    network.rows = {"original": media("original", "old"), "replacement": media("replacement", "intended")}
    _, approval = plan(engine, context, request)
    engine.execute("commit_write", approval, context=context)
    network.rows["original"]["assets"] = deepcopy(network.rows["replacement"]["assets"])
    network.job["status"] = "finished"
    network.calls.clear()
    result = engine.execute("commit_write", approval, context=context)
    item = result.data["items"][0]
    assert item["state"] == "succeeded"
    evidence = item["asset_verification"]
    assert evidence["state"] == "matched"
    assert evidence["original_asset"]["url_sha256"] != evidence["target_asset"]["url_sha256"]
    assert evidence["intended_asset"] == evidence["target_asset"]
    assert evidence["public_media_url"]["identity_preserved"] is True
    assert evidence["public_media_url"]["reachability_verified"] is False
    assert evidence["public_media_url"]["hashed_id"] == "original"
    assert "https://" not in json.dumps(evidence)
    assert network.calls == [("GET", "/modern/background_job_status/job7"), ("GET", "/modern/medias/original")]


@pytest.mark.parametrize("problem", ["missing", "ambiguous", "same_original", "unchanged_target",
    "wrong_size", "wrong_mime", "null_size", "boolean_size", "old_field_names", "unsafe_url", "wrong_id", "audio"])
def test_incomplete_or_nonmatching_evidence_never_claims_match(problem):
    original = media("original", "old")
    intended = media("replacement", "intended")
    target = media("original", "intended")
    asset = target["assets"][0]
    if problem == "missing":
        target.pop("assets")
    elif problem == "ambiguous":
        target["assets"].append(deepcopy(asset))
    elif problem == "same_original":
        original["assets"] = deepcopy(intended["assets"])
    elif problem == "unchanged_target":
        target["assets"] = deepcopy(original["assets"])
    elif problem == "wrong_size":
        asset["file_size"] += 1
    elif problem == "wrong_mime":
        asset["content_type"] = "video/quicktime"
    elif problem == "null_size":
        asset["file_size"] = None
    elif problem == "boolean_size":
        asset["file_size"] = True
    elif problem == "old_field_names":
        asset["fileSize"] = asset.pop("file_size")
    elif problem == "unsafe_url":
        asset["url"] = "https://user:secret@example.com/file.bin"
    elif problem == "wrong_id":
        target["hashed_id"] = "other"
    elif problem == "audio":
        original["type"] = intended["type"] = target["type"] = "Audio"
    assert swap_asset_evidence(original, intended, target)["state"] == "inconclusive"


def test_missing_asset_evidence_keeps_existing_job_completion(tmp_path):
    engine, context, network, request = setup(tmp_path)
    _, approval = plan(engine, context, request)
    engine.execute("commit_write", approval, context=context)
    network.job["status"] = "finished"
    result = engine.execute("commit_write", approval, context=context)
    item = result.data["items"][0]
    assert item["state"] == "succeeded"
    assert item["asset_verification"]["state"] == "inconclusive"
