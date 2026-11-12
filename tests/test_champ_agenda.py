"""Rich supplied CHAMP fields anchored to the existing captured event fixture."""

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.champ_agenda import enrich_bundle
from civic_data_connectors.providers.contracts import Response

FIXTURE = Path(__file__).parent / "fixtures/brief-discovery/champ-lakezurich-event-json.json"
SOURCE = Source("champ", "https://play.champds.com/lakezurichil/event/164", input_format="champ-event-json")


def test_timeline_mapping_is_anchored_to_exact_captured_vendor_player():
    path = Path(__file__).parents[1] / "docs/capabilities/evidence/champ-public-player/source.json"
    evidence = json.loads(path.read_bytes())
    raw = base64.b64decode(evidence["content_base64"], validate=True)
    assert len(raw) == 65250 and hashlib.sha256(raw).hexdigest() == evidence["sha256"]
    script = raw.decode("utf-8")
    assert "tlItem.ContainerTypeID == 2) //ContainerTypeID 2 == Agenda Item" in script
    assert "extraClasses = 'cdsAgendaItemRef_' + tlItem.ContainerID" in script
    assert "var start = Math.max((timelineItem.TimeStartSeconds), 0)" in script
    assert "setTime(start)" in script


def payload():
    raw = json.loads(FIXTURE.read_bytes())
    parent = raw["Agenda"]["AgendaItems"][1]
    child = {**deepcopy(parent), "CustomerAgendaItemID": 999, "Title": "Nested report",
             "Description": "<p>Quinoa funding discussion</p><script>do not execute</script>",
             "OrderParentID": parent["CustomerAgendaItemID"], "Children": [], "Attachments": []}
    parent["Children"] = [child]
    raw["Timeline"].append({"CustomerTimelineID": 888, "ContainerTypeID": 2,
        "ContainerID": 999, "CustomerEventID": 164, "TimeStartSeconds": 141, "TimeEndSeconds": 170})
    return raw


def normalize(raw):
    result = create_engine().normalize(SOURCE, json.dumps(raw).encode(), input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    return result


def test_actual_normalize_search_and_export_preserve_native_relationships_and_timestamp():
    raw = payload()
    result = normalize(raw)
    record = result.data["records"][0]
    items = {item["external_id"]: item for item in record["normalized"]["agenda_items"]}
    assert items["999"]["parent_external_id"] == "2950"
    assert items["999"]["meeting_external_id"] == "164"
    assert items["999"]["description"] == "Quinoa funding discussion"
    assert items["999"]["timeline"][0]["start_seconds"] == 141
    document = items["2950"]["documents"][0]
    assert document["external_id"] == "2266" and document["agenda_item_external_id"] == "2950"
    assert document["source_fields"] == raw["Agenda"]["AgendaItems"][1]["Attachments"][0]
    assert record["original"] == raw
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])
    assert enrich_bundle(result.data) == result.data
    found = create_engine().execute("search", {"bundle": result.data, "query": {"terms": ["quinoa"]}})
    assert found.status == "partial", found.public_dict()
    assert found.coverage["incomplete_text"] is True
    assert len(found.data["hits"]) == 1
    assert any(m.get("timestamp") == "00:02:21" for m in found.data["hits"][0]["matches"])
    exported = create_engine().execute("export", {"bundle": result.data, "format": "json"})
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_configured_event_read_uses_same_rich_mapping():
    content = json.dumps(payload()).encode()

    class Transport:
        def request(self, url, **kwargs):
            assert url == "https://playapi.champds.com/lakezurichil/event/164"
            return Response(url, content, "application/json")

    result = create_engine(provider_transport=Transport()).fetch(SOURCE)
    assert result.status in {"completed", "partial"} and not result.errors, result.public_dict()
    item = next(i for i in result.data["records"][0]["normalized"]["agenda_items"] if i["external_id"] == "999")
    assert item["parent_external_id"] == "2950" and item["timeline"][0]["units"] == "seconds"


def test_description_only_revision_changes_rich_digest_not_legacy_meeting_projection():
    raw = payload()
    first = normalize(raw).data
    raw["Agenda"]["AgendaItems"][1]["Children"][0]["Description"] = "Changed supplied description"
    second = normalize(raw).data
    assert first["compatibility"]["meetings"] == second["compatibility"]["meetings"]
    a, b = first["records"][0], second["records"][0]
    assert a["identity"] == b["identity"] and a["normalized_sha256"] != b["normalized_sha256"]


@pytest.mark.parametrize("change", [{"ContainerTypeID": 1}, {"CustomerEventID": 999},
                                   {"ContainerID": 777}, {"TimeStartSeconds": -1},
                                   {"ContainerTypeID": 2.0}, {"CustomerEventID": 164.0},
                                   {"ContainerID": 999.0}])
def test_unassociated_or_invalid_timeline_does_not_invent_item_anchor(change):
    raw = payload()
    raw["Timeline"][-1].update(change)
    record = normalize(raw).data["records"][0]
    item = next(i for i in record["normalized"]["agenda_items"] if i["external_id"] == "999")
    assert item["timeline"] == []
    assert raw["Timeline"][-1] in record["normalized"]["unassociated_timeline"]
    assert all("timestamp" not in s for s in record["text"] if s["field"] == "agenda_items.999.description")


def test_ambiguous_parent_preserves_meeting_raw_and_legacy_items_without_claiming_relationships():
    raw = payload()
    raw["Agenda"]["AgendaItems"][1]["Children"][0]["OrderParentID"] = 12345
    record = normalize(raw).data["records"][0]
    assert record["normalized"]["agenda_relationships_availability"] == "unmapped_ambiguous_source_binding"
    assert record["original"] == raw
    assert not any("parent_external_id" in i for i in record["normalized"]["agenda_items"])
