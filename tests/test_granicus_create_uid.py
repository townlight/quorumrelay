"""Caller-assigned EventData UID through WSDL-shaped coordinator transactions."""
from copy import deepcopy
import xml.etree.ElementTree as ET

import pytest

from test_granicus_write import Network, RPC, SOAP, SOURCE, plan, setup
from test_granicus_write_identity import reopen

UID = "9c133a18-4273-4f86-97db-6cd3a6d55093"


class UIDNetwork(Network):
    def __init__(self):
        super().__init__()
        self.defect = None

    def send(self, url, **kwargs):
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if action != "CreateEvent":
            return super().send(url, **kwargs)
        sent = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}CreateEvent/EventData/UID")
        try:
            return super().send(url, **kwargs)
        finally:
            if sent is not None and sent.text:
                self.values["UID"] = sent.text

    def _record(self, event):
        super()._record(event)
        if self.mutations and self.defect == "wrong":
            event.find("UID").text = "11111111-1111-1111-1111-111111111111"
        elif self.mutations and self.defect == "missing":
            event.remove(event.find("UID"))


def create_plan(tmp_path, uid=UID):
    engine, network, context, change = setup(tmp_path, UIDNetwork())
    context.credentials["granicus"].update(permissions=["event:create"], foreign_ids=["9001"])
    change.update(operation="create", resource_id=None, fields={
        **deepcopy(network.values), "ID": 0, "UID": uid, "ForeignID": 9001, "Name": "Created"})
    return engine, network, context, change


@pytest.mark.parametrize("uid", [UID, UID.upper(), UID.replace("-", ""), "{" + UID + "}"])
def test_create_accepts_caller_guid_and_confirms_readback(tmp_path, uid):
    engine, network, context, change = create_plan(tmp_path, uid)
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "succeeded"
    assert result.data["items"][0]["readback"]["UID"] == uid and network.mutations == 1


@pytest.mark.parametrize("defect", ["wrong", "missing"])
@pytest.mark.parametrize("lost", [False, True])
def test_caller_uid_readback_required_after_reopen_without_replay(tmp_path, defect, lost):
    engine, network, context, change = create_plan(tmp_path)
    approval = plan(engine, context, change)
    network.defect, network.lose_response = defect, lost
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    reopened = reopen(tmp_path, network)
    assert reopened.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    network.defect = None
    assert reopened.execute("commit_write", approval, context=context).data["items"][0]["state"] == "succeeded"
    assert network.mutations == 1


def test_empty_uid_retains_server_assignment(tmp_path):
    engine, network, context, change = create_plan(tmp_path, "")
    result = engine.execute("commit_write", plan(engine, context, change), context=context)
    assert result.data["items"][0]["state"] == "succeeded"
    assert result.data["items"][0]["readback"]["UID"] == "synthetic-provider-guid"


@pytest.mark.parametrize("uid", ["not-a-guid", 123, None])
def test_invalid_uid_rejected_before_mutation(tmp_path, uid):
    engine, network, context, change = create_plan(tmp_path, uid)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed" and network.mutations == 0


def test_event_uid_update_remains_disallowed(tmp_path):
    engine, network, context, change = setup(tmp_path, UIDNetwork())
    change["fields"] = {"UID": UID}
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed" and network.mutations == 0
