"""Standalone native item records must appear in the existing item CSV projection."""
import base64
import csv
from copy import deepcopy
import io
import json

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash, source_identity_key
from civic_data_connectors.interchange import csv_projection
from civic_data_connectors.providers.primegov_public import outline_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from test_escribe_publishing import DATA, MEETING, SOURCE as ESCRIBE, identity_key, response, sample
from test_primegov_public_outline import SOURCE
from test_storage_search_imports import sample as neutral_sample


def item_bundle():
    raw = [{"id": 1, "meetingId": 4922, "name": "Business", "items": [
        {"id": 123456, "meetingId": 4922, "titleDisplayField": "Budget review"}]}]
    return outline_bundle(SOURCE, "wacotexas.primegov.com", json.dumps(raw).encode(), "4922", "agenda_item", 100)


def test_existing_reader_standalone_item_uses_explicit_native_meeting_relationship():
    bundle = item_bundle()
    record, = bundle["records"]
    payload, losses = csv_projection(bundle["records"], kind="items")
    rows = list(csv.DictReader(io.StringIO(payload.decode())))
    parent = next(r["identity"] for r in record["relationships"] if r["relation"] == "meeting")
    assert rows == [{"meeting_identity_key": source_identity_key(parent), "item_external_id": "123456",
        "title": "Budget review", "department": "", "source_url": SOURCE.url}]
    assert "normalized.title" not in losses["records"][0]["omitted_fields"]
    assert losses["lossless"] is False


@pytest.mark.parametrize("kind", ["Agenda", "AgendaItem", "Attachment"])
def test_escribe_native_compound_parents_become_explicit_portable_relationships(kind):
    bundle = soap.parse_bundle(ESCRIBE, "synthetic", response(kind + "GetById", sample(kind),
        namespace=DATA if kind == "Agenda" else soap.NS))
    record, = bundle["records"]
    links = {r["relation"]: r["identity"] for r in record["relationships"] if "identity" in r}
    assert links["meeting"]["external_id"] == MEETING
    if kind != "Agenda":
        assert links["agenda"]["external_id"] == identity_key(sample("Agenda")["Id"])
    if kind == "Attachment":
        assert links["agenda_item"]["external_id"] == identity_key(sample("AgendaItem")["Id"])
        assert links["document"]["external_id"] == "23"
    if kind == "AgendaItem":
        payload, _ = csv_projection([record], kind="items")
        row, = list(csv.DictReader(io.StringIO(payload.decode())))
        assert row["meeting_identity_key"] == source_identity_key(links["meeting"])
        assert row["item_external_id"] == record["identity"]["external_id"]


@pytest.mark.parametrize("case", ["missing", "conflicting", "invalid", "parent_only", "relationship_only", "duplicate"])
def test_item_projection_never_guesses_missing_or_conflicting_meeting_identity(case):
    record = deepcopy(item_bundle()["records"][0])
    parent = record["identity"]["parent"]
    if case == "missing":
        record["identity"].pop("parent")
        record["relationships"] = []
    elif case == "conflicting":
        record["relationships"][0]["identity"]["namespace"] = "other.example"
    elif case == "invalid":
        record["relationships"][0]["identity"].pop("external_id")
    elif case == "parent_only":
        record["relationships"] = []
    elif case == "relationship_only":
        record["identity"].pop("parent")
    else:
        record["relationships"].append(deepcopy(record["relationships"][0]))
    payload, losses = csv_projection([record], kind="items")
    row, = list(csv.DictReader(io.StringIO(payload.decode())))
    assert row["item_external_id"] == "123456"
    assert row["meeting_identity_key"] == ("" if case in {"missing", "conflicting", "invalid"}
                                            else source_identity_key(parent))
    assert bool(losses["records"][0].get("limitations")) == (case in {"missing", "conflicting", "invalid"})


def test_mixed_nested_and_standalone_items_keep_rows_formula_guard_and_input():
    nested = neutral_sample()["records"][0]
    item = item_bundle()["records"][0]
    item["normalized"]["title"] = '=SUM(1,2)\n"source"'
    before = deepcopy([nested, item])
    payload, losses = csv_projection([nested, item], kind="items")
    rows = list(csv.DictReader(io.StringIO(payload.decode(), newline="")))
    assert [row["title"] for row in rows] == ["Parks budget", "'" + item["normalized"]["title"]]
    assert [nested, item] == before
    assert len(losses["records"]) == 2
    assert "original.id" in losses["records"][1]["omitted_fields"]


def test_item_csv_exports_the_durable_reader_bundle_by_key_after_reopen(tmp_path):
    bundle = item_bundle()
    path = tmp_path / "items.sqlite"
    owner = create_engine(storage=SQLiteStorage(path))
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": bundle, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(path))
    result = reopened.execute("export", {"bundle_key": canonical_hash(bundle), "format": "csv-items"})
    assert result.status == "completed" and not result.errors, result.public_dict()
    payload = base64.b64decode(result.data["content_base64"])
    row, = list(csv.DictReader(io.StringIO(payload.decode())))
    assert row["item_external_id"] == "123456" and row["title"] == "Budget review"
    assert row["meeting_identity_key"]
    assert result.data["manifest"]["projection_losses"]["lossless"] is False
    assert result.data["manifest"]["byte_length"] == len(payload)
    assert reopened.storage.get("bundles", canonical_hash(bundle), scope=OperationContext().scope).value == bundle
