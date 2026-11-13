import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from civic_data_connectors import Source, create_engine
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.towpath_detail import enrich_bundle

CAPTURE = (Path(__file__).parent / "fixtures/baseline/digital-towpath-detail.response").read_bytes()
SOURCE = Source("digital-towpath", "https://townofberkshireny.gov/meetings/detail/64",
                input_format="digital-towpath-detail-html")


def test_saved_native_detail_fields_text_search_export_and_pinned_compatibility():
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    value = record["normalized"]
    assert value["category"] == "Town Board" and "body" not in value
    assert value["location"] == "Town Hall, 18 Railroad Ave, Berkshire, NY 13736"
    assert value["source_start"] == "2026-11-12T19:00:00"
    assert value["time_zone_status"] == "unknown"
    assert "scheduled_start" not in value
    assert value["description"] == "2027 Final Budget hearing"
    assert "Meeting minutes pending." in value["source_document_states"]["minutes"]
    assert not any(d["kind"] == "minutes" for d in value["documents"])
    assert record["identity"]["external_id"] == "64"
    assert record["normalized_sha256"] == canonical_hash(value)
    assert record["text"][0]["provenance"]["capture_sha256"] == hashlib.sha256(CAPTURE).hexdigest()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    assert canonical_hash(result.data["compatibility"]) == (
        "064ebc05ee3542b18ebbeefa66e526c8f76fc83b4031ec3564224570d943f20d")
    searched = engine.execute("search", {"bundle": result.data,
        "query": {"phrases": ["2027 Final Budget hearing"]}})
    assert len(searched.data["hits"]) == 1
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data
    assert enrich_bundle(result.data) == result.data


def test_default_configured_detail_uses_exact_supplied_get():
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append(url)
            return Response(url, CAPTURE, "text/html")

    result = create_engine(provider_transport=Transport()).discover(replace(SOURCE, input_format=None))
    assert result.status == "partial", result.public_dict()
    assert calls == [SOURCE.url]
    assert result.data["records"][0]["normalized"]["category"] == "Town Board"
    assert result.data["records"][0]["text"][0]["text"] == "2027 Final Budget hearing"


def test_description_revision_changes_rich_hash_not_legacy_output_or_identity():
    engine = create_engine()
    before = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data
    changed = CAPTURE.replace(b"2027 Final Budget hearing", b"Updated supplied budget hearing")
    assert changed != CAPTURE
    after = engine.normalize(SOURCE, changed, input_format=SOURCE.input_format).data
    assert before["compatibility"]["meetings"] == after["compatibility"]["meetings"]
    assert before["records"][0]["identity"] == after["records"][0]["identity"]
    assert before["records"][0]["normalized_sha256"] != after["records"][0]["normalized_sha256"]


def test_capture_binding_and_ambiguous_fields_rejected_without_script_content():
    engine = create_engine()
    bundle = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data
    changed = deepcopy(bundle)
    changed["records"][0]["identity"]["external_id"] = "65"
    with pytest.raises(ValueError, match="identity"):
        enrich_bundle(changed)
    changed = deepcopy(bundle)
    changed["capture"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        enrich_bundle(changed)
    raw = CAPTURE.replace(b"2027 Final Budget hearing", b"Native prose<script>secret_script_token</script>")
    value = engine.normalize(SOURCE, raw, input_format=SOURCE.input_format).data["records"][0]
    assert value["text"][0]["text"] == "Native prose"
    assert "secret_script_token" not in value["normalized"]["description"]
    raw = CAPTURE.replace(b'</body>', b'<div class="dtp-meeting-description">Other</div></body>')
    assert engine.normalize(SOURCE, raw, input_format=SOURCE.input_format).status == "failed"
