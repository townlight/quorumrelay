"""One-record retrieval exercises the real engine with an isolated no-network transport."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response


class EventTransport:
    def __init__(self, value=None, status=200):
        self.calls = []
        self.value = value if value is not None else {
            "EventId": 7, "EventBodyName": "Council", "EventDate": "2026-11-11T00:00:00",
            "EventRowVersion": "revision-1", "EventItems": [{
                "EventItemId": 8, "EventItemTitle": "Water budget", "EventItemAgendaNote": "Supplied note",
                "EventItemPassedFlag": 1, "EventItemMatterAttachments": [{
                    "MatterAttachmentId": 9, "MatterAttachmentName": "Water packet",
                    "MatterAttachmentHyperlink": "https://city.example/packet.pdf", "unknown": [None, False],
                }], "unknown_vote": {"raw": 0},
            }], "unknown": {"keep": "original"},
        }
        self.status = status

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(url, json.dumps(self.value).encode(), "application/json", self.status)


def test_event_detail_preserves_identity_capture_items_and_attachment_relationships():
    transport = EventTransport()
    engine = create_engine(provider_transport=transport)
    source = Source("legistar", "https://webapi.legistar.com/v1/city")
    result = engine.fetch_record(source, "7")
    assert result.status == "completed", result.public_dict()
    assert len(transport.calls) == 1
    url, kwargs = transport.calls[0]
    assert urlsplit(url).path == "/v1/city/Events/7"
    assert parse_qs(urlsplit(url).query) == {
        "EventItems": ["1"], "AgendaNote": ["1"], "MinutesNote": ["1"], "EventItemAttachments": ["1"],
    }
    assert kwargs["allowed_origins"] == ("https://webapi.legistar.com",)
    assert kwargs["byte_limit"] == Bounds().parser_bytes
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "7"
    assert record["original"] == transport.value
    assert json.loads(base64.b64decode(result.data["capture"]["content_base64"])) == transport.value
    assert record["source_revision"]["value"]["EventRowVersion"] == "revision-1"
    assert record["normalized"]["agenda_items"][0]["source_fields"]["unknown_vote"] == {"raw": 0}
    document = record["normalized"]["documents"][0]
    assert document["agenda_item_external_id"] == "8"
    assert document["source_fields"]["unknown"] == [None, False]
    assert any(r["relation"] == "document" for r in record["relationships"])
    assert result.coverage["catalog_complete"] is False
    replay = engine.normalize(source, base64.b64decode(result.data["capture"]["content_base64"]),
                              input_format="legistar-event-json")
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert replay.data["records"][0]["normalized"] == record["normalized"]


@pytest.mark.parametrize("external_id", ["../7", "7?token=secret", 7, "0", "-1", ""])
def test_detail_identity_rejects_paths_and_noncanonical_ids(external_id):
    transport = EventTransport()
    result = create_engine(provider_transport=transport).fetch_record(
        Source("legistar", "https://webapi.legistar.com/v1/city"), external_id)
    assert result.status == "failed"
    assert not transport.calls


def test_detail_failures_and_revocation_never_become_successful_empty_results():
    source = Source("legistar", "https://webapi.legistar.com/v1/city")
    for transport in (EventTransport(status=404), EventTransport(value={"EventId": 8}),
                      EventTransport(value=[])):
        result = create_engine(provider_transport=transport).fetch_record(source, "7")
        assert result.status == "failed"
        assert result.data is None
        assert result.coverage["failures"]
    transport = EventTransport()
    engine = create_engine(provider_transport=transport)
    result = engine.fetch_record(source, "7", context=OperationContext(allowed_namespaces=frozenset()))
    assert result.status == "failed"
    assert not transport.calls
    result = engine.fetch_record(source, "7", bounds=Bounds(parser_bytes=1))
    assert result.status == "failed"
    result = engine.fetch_record(Source("first-party", "https://city.example/calendar.ics"), "7")
    assert result.status == "unsupported"
    assert "not verified" in result.errors[0].message


def test_detail_cancellation_and_credentials_stay_in_trusted_context():
    transport = EventTransport()
    context = OperationContext(credentials={"legistar_token": "secret-token"})
    context.cancellation.set()
    source = Source("legistar", "https://webapi.legistar.com/v1/city")
    engine = create_engine(provider_transport=transport)
    assert engine.fetch_record(source, "7", context=context).status == "cancelled"
    assert not transport.calls
    context.cancellation.clear()
    result = engine.fetch_record(source, "7", context=context)
    assert result.status == "completed"
    assert "secret-token" in transport.calls[0][0]
    assert "secret-token" not in json.dumps(result.public_dict())

def test_public_detail_fixture_roundtrip_and_actual_supplied_items():
    import hashlib
    from pathlib import Path
    from quorumrelay.interchange import write_bundle, read_bundle
    import io

    raw = (Path(__file__).parent / "fixtures/brief-discovery/legistar-olympia-event-7011.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "34e882748bb749339329d7013f5d0e3a1a41b6d714572f7711e572f178e69e85"
    engine = create_engine()
    result = engine.normalize(Source("legistar", "https://webapi.legistar.com/v1/olympia"), raw,
                              input_format="legistar-event-json")
    assert result.status == "completed"
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "7011"
    assert len(record["normalized"]["agenda_items"]) == 10
    assert len(record["normalized"]["documents"]) == 9
    assert record["original"] == json.loads(raw)
    output = io.BytesIO()
    write_bundle(result.data, output)
    restored = read_bundle(output.getvalue())
    assert restored == result.data
    hits = engine.execute("search", {"records": restored["records"], "query": {}})
    assert hits.data["hits"][0]["record"]["identity"] == record["identity"]

def test_wistia_single_media_detail_exact_capture_asset_metadata_and_no_invented_transcript():
    raw = {"hashed_id": "media1", "name": "Council", "description": "Supplied metadata",
           "created": "2026-11-11T01:00:00Z", "updated": "2026-11-11T02:00:00Z", "folder": None,
           "assets": [{"url": "https://embed-ssl.wistia.com/deliveries/asset.mp4",
                       "width": 640, "height": 360, "file_size": 1024, "content_type": "video/mp4",
                       "type": "OriginalFile", "unknown_asset": False}], "unknown": [None, False]}
    transport = EventTransport(value=raw)
    engine = create_engine(provider_transport=transport)
    source = Source("wistia", "https://api.wistia.com/modern/medias")
    context = OperationContext(credentials={"wistia_token": "read-token"})
    result = engine.fetch_record(source, "media1", context=context)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["record_type"] == "recording"
    assert record["identity"]["external_id"] == "media1"
    assert record["original"] == raw
    assert record["text"] == []
    assert "meeting_date" not in record["normalized"]
    assert record["normalized"]["recordings"][1]["source_fields"]["unknown_asset"] is False
    assert base64.b64decode(result.data["capture"]["content_base64"]) == json.dumps(raw).encode()
    assert transport.calls[0][0] == "https://api.wistia.com/modern/medias/media1"
    assert transport.calls[0][1]["headers"]["Authorization"] == "Bearer read-token"
    assert "read-token" not in json.dumps(result.public_dict())
    replay = engine.normalize(source, json.dumps(raw).encode(), input_format="wistia-media-detail-json")
    assert replay.data["records"][0]["normalized"] == record["normalized"]
    assert engine.fetch_record(source, "../media1", context=context).status == "failed"
    assert engine.fetch_record(source, "media1").errors[0].code == "credentials_required"
    bad = create_engine(provider_transport=EventTransport(value={**raw, "hashed_id": "other"}))
    assert bad.fetch_record(source, "media1", context=context).status == "failed"

def test_champ_observed_public_detail_route_preserves_baseline_identity_and_bounds():
    from pathlib import Path
    raw = (Path(__file__).parent / "fixtures/baseline/champ-event.response").read_bytes()
    class ChampTransport:
        calls = []
        def request(self, url, **kwargs):
            self.calls.append((url, kwargs))
            # The observed API publishes JSON with a text/html MIME type.
            return Response(url, raw, "text/html; charset=UTF-8")
    transport = ChampTransport()
    engine = create_engine(provider_transport=transport)
    source = Source("champ", "https://play.champds.com/lakezurichil/event/164")
    detail = engine.fetch_record(source, "164")
    assert detail.status == "completed", detail.public_dict()
    assert transport.calls[0][0] == "https://playapi.champds.com/lakezurichil/event/164"
    assert transport.calls[0][1]["allowed_origins"] == ("https://playapi.champds.com",)
    assert detail.data["records"][0]["identity"]["namespace"] == "//champds.com/lakezurichil"
    assert detail.data["records"][0]["original"] == json.loads(raw)
    assert base64.b64decode(detail.data["capture"]["content_base64"]) == raw
    assert detail.coverage["catalog_complete"] is False
    listing = engine.discover(source)
    assert listing.status == "partial"
    assert "configured capture" in listing.coverage["scope"]
    assert engine.fetch_record(source, "../164").status == "failed"
    assert engine.fetch_record(source, "165").status == "failed"  # mismatched response identity
    blocked = engine.fetch_record(source, "164", context=OperationContext(allowed_namespaces=frozenset()))
    assert blocked.status == "failed"
    limited = engine.fetch_record(source, "164", bounds=Bounds(parser_bytes=1))
    assert limited.status == "failed"

def test_wistia_supplied_captions_use_read_routes_preserve_parent_and_search_time_anchors():
    caption = {"id": "track1", "media_id": "media1", "language": "eng", "is_draft": False,
               "version": 3, "text": "1\n00:00:01,000 --> 00:00:02,000\nWater budget approved\n",
               "segments": [{"start_ms": 1000, "end_ms": 2000, "text": "Water budget approved"}],
               "unknown": [False, None]}
    transport = EventTransport(value=caption)
    engine = create_engine(provider_transport=transport)
    source = Source("wistia", "https://api.wistia.com/modern/medias")
    context = OperationContext(credentials={"wistia_token": "read-token"})
    result = engine.fetch_captions(source, "media1", language="eng", context=context)
    assert result.status == "completed", result.public_dict()
    assert transport.calls[0][0] == "https://api.wistia.com/modern/medias/media1/captions/eng?include=segments"
    assert "diarized" not in transport.calls[0][0]
    record = result.data["records"][0]
    assert record["identity"]["record_type"] == "transcript"
    assert record["identity"]["parent"]["external_id"] == "media1"
    assert record["original"] == caption
    assert record["source_revision"]["value"] == {"version": 3}
    assert result.coverage["generation_requested"] is False
    hits = engine.execute("search", {"bundle": result.data, "query": {"phrases": ["water budget"]}})
    assert hits.data["hits"][0]["matches"][0]["timestamp_seconds"] == 1
    replay = engine.normalize(source, json.dumps(caption).encode(), input_format="wistia-caption-json")
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert replay.data["records"][0]["text"] == record["text"]
    listing = EventTransport(value=[caption])
    listed = create_engine(provider_transport=listing).fetch_captions(source, "media1", context=context)
    assert listed.status == "completed"
    assert listing.calls[0][0].endswith("/media1/captions")
    empty = create_engine(provider_transport=EventTransport(value=[])).fetch_captions(source, "media1", context=context)
    assert empty.status == "partial"
    assert "delegated" in empty.coverage["permission_limits"]
    wrong = {**caption, "media_id": "other"}
    assert create_engine(provider_transport=EventTransport(value=wrong)).fetch_captions(
        source, "media1", language="eng", context=context).status == "failed"
    assert engine.fetch_captions(Source("legistar", "https://webapi.legistar.com/v1/city"), "1").status == "unsupported"
