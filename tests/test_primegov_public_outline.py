"""Real public JSON plus explicit synthetic outline items; no speaker submissions."""

import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures/primegov-public-outline"
SOURCE = Source("primegov", "https://wacotexas.primegov.com/public/portal", input_format="primegov-portal-json")
MEETING = "4922"


class Network:
    def __init__(self):
        self.calls = []
        self.raw = (ROOT / "waco-4922-sections.json").read_bytes()
        self.status, self.mime, self.redirect, self.cancel = 200, "application/json", False, None

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert (
            url
            == "https://wacotexas.primegov.com/api/PublicSpeakerAndComment/GetSectionsAndItemsForSpeakerRequest?meetingId=4922"
        )
        assert kwargs.get("method", "GET") == "GET" and kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == ("https://wacotexas.primegov.com",)
        if self.cancel:
            self.cancel.cancellation.set()
        return Response(url + "/redirect" if self.redirect else url, self.raw, self.mime, self.status)


def setup(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"), provider_transport=network)
    parent = engine.normalize(SOURCE, (ROOT / "waco-2026.json").read_bytes(), input_format="primegov-portal-json", bounds=Bounds(max_records=1000))
    assert parent.status == "completed", parent.public_dict()
    assert engine.execute("import_bundle", {"bundle": parent.data, "persist": True}).status == "completed"
    return engine, network


@pytest.mark.parametrize("kind,count", [("agenda_section", 6), ("agenda_item", 0)])
def test_actual_sections_empty_items_are_partial_and_exact_raw_survives(tmp_path, kind, count):
    engine, network = setup(tmp_path)
    r = engine.fetch_related(SOURCE, MEETING, kind)
    assert r.status == "partial" and not r.errors, r.public_dict()
    assert len(r.data["records"]) == count and len(network.calls) == 1
    assert not r.coverage["full_agenda_complete"] and not r.coverage["public_speaker_submission_performed"]
    assert base64.b64decode(r.data["capture"]["content_base64"]) == network.raw
    if count:
        first = r.data["records"][0]
        assert first["identity"]["external_id"] == "74061"
        assert first["identity"]["parent"]["external_id"] == MEETING
    exported = engine.execute("export", {"bundle": r.data, "format": "zip"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == r.data


def test_synthetic_items_keep_meeting_section_and_native_fields_through_reopen(tmp_path):
    engine, network = setup(tmp_path)
    payload = json.loads(network.raw)
    payload[0]["items"] = [
        {
            "id": 123456,
            "titleDisplayField": "Budget review",
            "number": "1",
            "level": 2,
            "parentId": 0,
            "systemItemId": 45678,
            "sectionTemplateId": 33628,
        }
    ]
    network.raw = json.dumps(payload).encode()
    r = engine.fetch_related(SOURCE, MEETING, "agenda_item")
    assert r.status == "partial" and not r.errors, r.public_dict()
    (item,) = r.data["records"]
    assert item["identity"]["external_id"] == "123456"
    assert item["normalized"]["section_external_id"] == "74061"
    assert item["normalized"]["source_system_item_id"] == 45678
    assert item["relationships"][1]["identity"]["parent"]["external_id"] == MEETING
    assert item["normalized_sha256"] == canonical_hash(item["normalized"])
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": r.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"))
    hit = reopened.execute("search", {"query": {"phrases": ["Budget review"]}})
    assert len(hit.data["hits"]) == 1
    exported = reopened.execute("export", {"bundle": r.data, "format": "zip"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == r.data


@pytest.mark.parametrize(
    "fault", ["meeting", "duplicate", "malformed", "denied", "redirect", "mime", "oversize", "cancel"]
)
def test_unverifiable_response_cannot_be_complete_empty(tmp_path, fault):
    engine, network = setup(tmp_path)
    payload = json.loads(network.raw)
    if fault == "meeting":
        payload[0]["meetingId"] = 1
    elif fault == "duplicate":
        payload.append(deepcopy(payload[0]))
    elif fault == "malformed":
        payload = {"not": "sections"}
    elif fault == "denied":
        network.status = 403
    elif fault == "redirect":
        network.redirect = True
    elif fault == "mime":
        network.mime = "text/html"
    elif fault == "cancel":
        network.cancel = OperationContext()
    network.raw = json.dumps(payload).encode()
    bounds = Bounds(parser_bytes=1) if fault == "oversize" else Bounds()
    r = engine.fetch_related(SOURCE, MEETING, "agenda_section", bounds=bounds, context=network.cancel)
    if fault == "cancel":
        assert r.status == "cancelled"
    else:
        assert r.errors and r.status in {"failed", "partial"}
    if r.data:
        assert not r.data["records"]


def test_explicit_cap_and_preflight_scope_native_meeting_gate(tmp_path):
    engine, network = setup(tmp_path)
    r = engine.fetch_related(SOURCE, MEETING, "agenda_section", bounds=Bounds(max_records=2))
    assert len(r.data["records"]) == 2 and r.coverage["record_limit_reached"]
    assert r.coverage["matching_records"] == 6
    for parent, kind, bounds, context in [
        ("338", "agenda_section", Bounds(), None),
        (MEETING, "document", Bounds(), None),
        (MEETING, "agenda_section", Bounds(checkpoint="x"), None),
        (MEETING, "agenda_section", Bounds(), OperationContext(tenant="other")),
    ]:
        before = len(network.calls)
        r = engine.fetch_related(SOURCE, parent, kind, bounds=bounds, context=context)
        assert r.status == "failed" and len(network.calls) == before


def test_rich_html_document_routes_corrected_without_legacy_change():
    raw = (ROOT / "waco-2026.json").read_bytes()
    r = create_engine().normalize(SOURCE, raw, input_format="primegov-portal-json", bounds=Bounds(max_records=1000))
    assert r.status == "completed"
    count = 0
    for record in r.data["records"]:
        for doc in record["normalized"]["documents"]:
            if doc["source_metadata"]["compile_output_type"] == 3:
                count += 1
                assert "/Portal/Meeting?meetingTemplateId=" in doc["url"]
                assert "compileOutputType" not in doc["url"]
                assert any(x["value"] == doc for x in record["relationships"])
    assert count == 21
    legacy = next(m for m in r.data["compatibility"]["meetings"] if m["external_id"] == "242")
    assert any(
        "/Public/CompiledDocument?" in d["url"] and "compileOutputType=3" in d["url"]
        for d in legacy["documents"]
    )


@pytest.mark.parametrize("output", [1, 2, 3])
def test_synthetic_vote_summary_uses_compiled_file_identity_and_link_precedes_format(output):
    from civic_data_connectors.providers.primegov_public import documents

    doc = {"id": 123, "meetingId": 4922, "templateId": 0, "compileOutputType": output, "link": None}
    result, unmapped = documents(SOURCE, {"id": 4922, "documentList": [doc]})
    assert not unmapped and "compiledMeetingDocumentFileId=123" in result[0]["url"]
    assert "meetingTemplateId" not in result[0]["url"]
    doc.update(link="/Public/supplied.pdf", compileOutputType=999)
    result, unmapped = documents(SOURCE, {"id": 4922, "documentList": [doc]})
    assert not unmapped and result[0]["url"].endswith("/Public/supplied.pdf")
    doc["meetingId"] = 1
    assert documents(SOURCE, {"id": 4922, "documentList": [doc]}) == ([], 1)
