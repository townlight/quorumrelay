import base64
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from civic_data_connectors import Source, create_engine
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.utah_detail import enrich_bundle

CAPTURE = (Path(__file__).parent / "fixtures/baseline/utah-notice.response").read_bytes()
SOURCE = Source("utah-public-notice", "https://www.utah.gov/pmn/sitemap/notice/1101977.html",
                input_format="utah-notice-html")


def test_saved_labeled_notice_fields_relationship_existing_text_search_export():
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    value = record["normalized"]
    assert record["identity"]["external_id"] == "1101977"
    assert value["body"] == "City Council" and value["entity"] == "Sunset"
    assert value["government_type"] == "Municipality"
    assert value["public_body"] == {
        "external_id": "724", "url": "https://www.utah.gov/pmn/sitemap/publicbody/724.html",
        "title": "City Council"}
    assert {"relation": "public_body", "value": value["public_body"]} in record["relationships"]
    assert value["source_notice_types"] == "Notice, Meeting, Hearing"
    assert value["source_posted_on"] == "August 14, 2026 10:07 AM"
    assert value["source_last_edited_on"] == "September 17, 2026 09:55 AM"
    assert value["location"] == "200 W 1300 N Sunset, UT 84015-0000"
    assert value["time_zone_status"] == "unknown"
    assert "scheduled_start" not in value
    assert len(record["text"]) == 1 and record["text"][0]["field"] == "notice.text"
    assert "City Council Agenda" in record["text"][0]["text"]
    assert "ten (10) working days" in value["supplied_notice_fields"]["Other Information"]["text"]
    assert record["normalized_sha256"] == canonical_hash(value)
    assert canonical_hash(result.data["compatibility"]) == (
        "0b4eb776e87ce38937186b0e31eeb762a3f6968f4770956250ab9ab57569a693")
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    found = engine.execute("search", {"bundle": result.data, "query": {"body": "City Council",
        "terms": ["Sunset"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data
    assert enrich_bundle(result.data) == result.data


def test_default_configured_notice_get_retains_fields():
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append(url)
            return Response(url, CAPTURE, "text/html")

    result = create_engine(provider_transport=Transport()).discover(replace(SOURCE, input_format=None))
    assert result.status == "partial", result.public_dict()
    assert calls == [SOURCE.url]
    assert result.data["records"][0]["normalized"]["public_body"]["external_id"] == "724"


def test_public_body_field_revision_changes_rich_digest_not_native_identity_or_legacy_meetings():
    engine = create_engine()
    before = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data
    raw = CAPTURE.replace(b">City Council</a>", b">Council supplied revision</a>")
    assert raw != CAPTURE
    after = engine.normalize(SOURCE, raw, input_format=SOURCE.input_format).data
    assert before["compatibility"]["meetings"] == after["compatibility"]["meetings"]
    assert before["records"][0]["identity"] == after["records"][0]["identity"]
    assert before["records"][0]["normalized_sha256"] != after["records"][0]["normalized_sha256"]


def test_public_body_link_stays_source_bound_and_capture_binding_is_required():
    engine = create_engine()
    raw = CAPTURE.replace(b'href="/pmn/sitemap/publicbody/724.html"',
                          b'href="https://foreign.example/pmn/sitemap/publicbody/724.html"')
    result = engine.normalize(SOURCE, raw, input_format=SOURCE.input_format)
    record, = result.data["records"]
    assert record["normalized"]["body"] == "City Council"
    assert "public_body" not in record["normalized"]
    assert not any(r["relation"] == "public_body" for r in record["relationships"])
    assert record["normalized"]["supplied_notice_fields"]["Public Body"]["links"][0]["href"].startswith("https://foreign.example/")
    changed = deepcopy(result.data)
    changed["records"][0]["identity"]["external_id"] = "1101978"
    with pytest.raises(ValueError, match="identity"):
        enrich_bundle(changed)
    changed = deepcopy(result.data)
    changed["capture"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        enrich_bundle(changed)
