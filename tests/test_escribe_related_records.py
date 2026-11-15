"""Pinned native package/bookmark contracts; entirely synthetic, no vendor calls."""
import base64
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.escribe_write import EscribeWriteAdapter
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.write_transport import WriteResponse
from test_escribe_publishing import (MEETING, PORTAL, SOURCE, Server, SendOnly,
                                     identity_key, plan, response, sample, setup, xml_fields)


@pytest.mark.parametrize("model", ["Package", "Bookmark", "Resolution"])
@pytest.mark.parametrize("create", [False, True])
def test_related_record_loss_reconciles_reads_without_replay(tmp_path, model, create):
    owner, server, source, context, change = setup(tmp_path, model, create)
    approval = plan(owner, source, context, change)
    server.lose_response = True
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
        write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    result = reopened.execute("commit_write", approval, context=context)
    assert result.status == ("partial" if create else "completed"), result.public_dict()
    assert server.mutations == 1


@pytest.mark.parametrize("model", ["Package", "Bookmark", "Resolution"])
@pytest.mark.parametrize("case", ["parent", "permission", "concurrent", "fields"])
def test_related_record_rejects_wrong_parent_grant_or_changed_state(tmp_path, model, case):
    owner, server, source, context, change = setup(tmp_path, model)
    if case == "parent":
        if model == "Package":
            server.value["MeetingId"] = PORTAL
        else:
            server.value["Id"]["MeetingId"] = PORTAL
        result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    elif case == "fields":
        change["fields"] = {"Unknown": 4}
        result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    else:
        approval = plan(owner, source, context, change)
        if case == "permission":
            context.credentials["escribe"]["meeting_ids"] = []
        else:
            server.value[{"Package": "DocumentId", "Bookmark": "TimeEnd", "Resolution": "MovedBy"}[model]] += 1
        result = owner.execute("commit_write", approval, context=context)
    assert result.status == "failed", result.public_dict()
    assert server.mutations == 0


@pytest.mark.parametrize("model", ["Package", "Bookmark", "Resolution"])
def test_native_relations_and_uninterpreted_values_roundtrip(tmp_path, model):
    server = Server(model)
    owner = create_engine(storage=SQLiteStorage(tmp_path / "read.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE, {"api_method": model + "GetById", "api_parameters": {"Id": server.value["Id"]}})
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    links = {r["relation"]: r["identity"] for r in record["relationships"] if "identity" in r}
    assert links["meeting"]["external_id"] == MEETING
    assert links["meeting"]["namespace"] == record["identity"]["namespace"]
    if model == "Package":
        assert links["document"]["external_id"] == "23"
        assert record["normalized"]["native_fields"]["LanguageId"] == 1033
        assert record["normalized"]["documents"] == []  # ID is not a guessed file URL.
    elif model == "Resolution":
        assert "agenda_item" not in links
        partial, = [r["value"] for r in record["relationships"] if r["relation"] == "agenda_item_reference"]
        assert partial["native_agenda_item_id"] == 12
        assert partial["agenda_type_availability"] == "not_supplied_by_resolution_identifier"
        assert record["normalized"]["source_resolution"]["MovedBy"] == 7
        assert record["normalized"]["source_resolution"]["Result"] == "Source result"
        assert record["text"][0]["text"] == "Literal source resolution"
    else:
        assert links["agenda_item"]["external_id"] == identity_key(sample("AgendaItem")["Id"])
        assert record["normalized"]["native_fields"]["TimeStart"] == 120
        assert record["normalized"]["timing_units"] == "not_declared_by_pinned_schema"
        assert record["normalized"]["recordings"] == []
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "read.sqlite"))
    saved = reopened.execute("search", {"query": {"record_types": [model.lower()]}})
    assert len(saved.data["hits"]) == 1
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("model", ["Package", "Bookmark", "Resolution"])
def test_collection_record_bound_does_not_publish_truncated_success(model):
    method = model + "GetByMeeting"

    class Collection:
        def request(self, url, **options):
            envelope = ET.fromstring(options["body"])
            relation = envelope.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
            payload = ET.fromstring(response(method, {}, relation=relation))
            result = payload.find("{" + soap.SOAP + "}Body")[0][0]
            for _ in range(2):
                xml_fields(ET.SubElement(result, "{" + soap.NS + "}" + model + ".Record"), sample(model), soap.NS)
            return Response(url, ET.tostring(payload), "application/soap+xml")

    result = create_engine(provider_transport=Collection()).fetch(SOURCE,
        {"api_method": method, "api_parameters": {"MeetingId": MEETING}}, bounds=Bounds(max_records=1))
    assert result.status == "failed" and result.errors and result.data is None


@pytest.mark.parametrize("model", ["Package", "Bookmark", "Resolution"])
def test_different_after_send_native_readback_stays_uncertain(tmp_path, model):
    owner, server, source, context, change = setup(tmp_path, model)
    approval = plan(owner, source, context, change)
    original = server.send

    def changed(url, **options):
        value = original(url, **options)
        if server.mutations and server.calls[-1].endswith("Update"):
            server.value[{"Package": "DocumentId", "Bookmark": "TimeEnd", "Resolution": "MovedBy"}[model]] += 1
        return value

    server.send = changed
    owner = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
        write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    assert server.mutations == 1


def test_bookmark_create_returning_other_parent_cannot_be_adopted(tmp_path):
    owner, server, source, context, change = setup(tmp_path, "Bookmark", True)
    approval = plan(owner, source, context, change)
    original = server.send

    def wrong_parent(url, **options):
        value = original(url, **options)
        if server.calls[-1] == "BookmarkCreate":
            envelope = ET.fromstring(options["body"])
            relation = envelope.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
            identity = deepcopy(server.value["Id"])
            identity["MeetingId"] = PORTAL
            return WriteResponse(200, response("BookmarkCreate", identity, relation=relation),
                                 {"content-type": "application/soap+xml"})
        return value

    server.send = wrong_parent
    owner = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
        write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    assert server.mutations == 1
