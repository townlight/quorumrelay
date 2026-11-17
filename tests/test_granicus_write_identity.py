"""Synthetic SOAP coordinator regressions for full-model write confirmation."""
from copy import deepcopy

import pytest

from civic_data_connectors import Engine
from civic_data_connectors.providers.granicus_write import GranicusWriteAdapter
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.writes import register
from test_granicus_write import Network, XSI, plan, setup


class AlteredReadback(Network):
    def __init__(self, defect):
        super().__init__()
        self.defect = defect
        self.null_description = defect in {"missing_null", "wrong_type"}

    def _record(self, event):
        super()._record(event)
        field = event.find("Description")
        if field is not None and self.null_description:
            field.set(f"{{{XSI}}}nil", "true")
            field.text = None
        if not self.mutations:
            return
        if self.defect == "missing_null":
            event.remove(field)
        elif self.defect == "wrong_type":
            value = event.find("CameraID")
            value.set(f"{{{XSI}}}type", "xsd:boolean")
            value.text = "false"
        elif self.defect == "wrong_id":
            event.find("ID").text = "9"
        elif self.defect == "missing_id":
            event.remove(event.find("ID"))
        elif self.defect == "zero_id":
            event.find("ID").text = "0"
        elif self.defect == "string_id":
            event.find("ID").set(f"{{{XSI}}}type", "xsd:string")


def reopen(tmp_path, network):
    engine = Engine(storage=SQLiteStorage(tmp_path / "soap-writes.sqlite"))
    register(engine, {"granicus": GranicusWriteAdapter(network)})
    return engine


@pytest.mark.parametrize("defect", ["missing_null", "wrong_type"])
def test_update_readback_requires_planned_presence_and_types(tmp_path, defect):
    engine, network, context, change = setup(tmp_path, AlteredReadback(defect))
    approval = plan(engine, context, change)
    first = engine.execute("commit_write", approval, context=context)
    assert first.data["items"][0]["state"] == "uncertain"
    network.defect = None
    recovered = reopen(tmp_path, network).execute("commit_write", approval, context=context)
    assert recovered.data["items"][0]["state"] == "succeeded" and network.mutations == 1


@pytest.mark.parametrize("defect", ["wrong_id", "missing_id", "zero_id", "string_id"])
def test_created_event_must_bind_acknowledged_positive_id(tmp_path, defect):
    engine, network, context, change = setup(tmp_path, AlteredReadback(defect))
    context.credentials["granicus"].update(permissions=["event:create"], foreign_ids=["9001"])
    fields = {**deepcopy(network.values), "ID": 0, "UID": "", "ForeignID": 9001, "Name": "Created"}
    change.update(operation="create", resource_id=None, fields=fields)
    approval = plan(engine, context, change)
    first = engine.execute("commit_write", approval, context=context)
    assert first.data["items"][0]["state"] == "uncertain"
    retry = reopen(tmp_path, network).execute("commit_write", approval, context=context)
    assert retry.data["items"][0]["state"] == "uncertain" and network.mutations == 1
    network.defect = None
    recovered = reopen(tmp_path, network).execute("commit_write", approval, context=context)
    assert recovered.data["items"][0]["state"] == "succeeded" and network.mutations == 1


@pytest.mark.parametrize("defect", ["missing_id", "zero_id"])
def test_lost_create_ack_does_not_persist_invalid_candidate_id(tmp_path, defect):
    engine, network, context, change = setup(tmp_path, AlteredReadback(defect))
    context.credentials["granicus"].update(permissions=["event:create"], foreign_ids=["9001"])
    change.update(operation="create", resource_id=None, fields={
        **deepcopy(network.values), "ID": 0, "UID": "", "ForeignID": 9001, "Name": "Created"})
    approval = plan(engine, context, change)
    network.lose_response = True
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    item = reopen(tmp_path, network).execute("commit_write", approval, context=context).data["items"][0]
    assert item["state"] == "uncertain" and item.get("resource_id") is None
    network.defect = None
    recovered = reopen(tmp_path, network).execute("commit_write", approval, context=context)
    assert recovered.data["items"][0]["state"] == "succeeded" and network.mutations == 1


def test_nested_payload_readback_type_change_stays_uncertain(tmp_path):
    class PayloadNetwork(Network):
        def _record(self, event):
            super()._record(event)
            if self.mutations:
                value = event.find("Payload/MotionText")
                value.set(f"{{{XSI}}}type", "xsd:boolean")
                value.text = "false"

    network = PayloadNetwork("MetaDataData", "GetMetaData", "UpdateMetaData", "MetaData")
    before = {"Mover": "A", "Seconder": "B", "Type": "motion", "MotionText": "before"}
    network.values["Payload"] = {"$type": "Motion", "value": before}
    engine, _, context, change = setup(tmp_path, network)
    context.credentials["granicus"].update(permissions=["agenda_item:update"], meeting_ids=["11"])
    change.update(entity="agenda_item", meeting_id="11", fields={
        "Payload": {"$type": "Motion", "value": {**before, "MotionText": "false"}}})
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain" and network.mutations == 1
