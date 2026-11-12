"""Agenda Add/Import transactions anchored to the pinned vendor WSDL models."""

from copy import deepcopy
import json
import xml.etree.ElementTree as ET

import pytest

from test_granicus_write import Network, SOAP, RPC, WSDL, XSI, ENC, SOURCE, setup, plan, model_fields
from civic_data_connectors.write_transport import WriteResponse


def node(foreign=101):
    fields = model_fields("MetaDataData")
    result = {key: 0 if typ == "xsd:int" else [] if typ.startswith("ns5:") else "" for key, typ in fields.items()}
    result.update(ForeignID=foreign, Name="Provided agenda item", Payload="Provided note")
    return result


def encode(parent, model, value):
    for key, typ in model_fields(model).items():
        child = ET.SubElement(parent, key)
        val = value[key]
        if key == "Children":
            child.set(f"{{{ENC}}}arrayType", "g:MetaDataData[0]")
            for row in val:
                encode(ET.SubElement(child, "item"), "MetaDataData", row)
        else:
            child.set(f"{{{XSI}}}type", typ if typ != "xsd:anyType" else "xsd:string")
            child.text = str(val)


def decode(element):
    fields = model_fields("MetaDataData")
    assert {c.tag for c in element} == set(fields)
    result = {}
    for key, typ in fields.items():
        child = element.find(key)
        result[key] = ([decode(row) for row in child] if key == "Children" else
                       int(child.text) if typ == "xsd:int" else child.text or "")
    return result


class MetadataNetwork(Network):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.loss = False
        self.corrupt = False
        self.calls = []

    def send(self, url, **kwargs):
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if action in {"Login", "Logout"}:
            return super().send(url, **kwargs)
        assert kwargs["headers"]["Cookie"] == "SID=synthetic-private-session"
        self.calls.append(action)
        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        response = ET.SubElement(ET.SubElement(envelope, f"{{{SOAP}}}Body"), f"{{{RPC}}}{action}Response")
        if action in {"GetEventMetaData", "GetClipMetaData"}:
            collection = ET.SubElement(response, "metadata", {f"{{{ENC}}}arrayType": "g:MetaDataData[0]"})
            for row in self.rows:
                encode(ET.SubElement(collection, "item"), "MetaDataData", row)
        else:
            assert action in {"AddEventMetaData", "AddClipMetaData", "ImportEventMetaData", "ImportClipMetaData"}
            sent = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}{action}")
            message = WSDL.find(f'.//{{http://schemas.xmlsoap.org/wsdl/}}message[@name="{action}Request"]')
            assert {c.tag for c in sent} == {p.get("name") for p in message}
            is_import = action.startswith("Import")
            supplied = [decode(row) for row in sent.find("MetaData")] if is_import else [decode(sent.find("MetaDataData"))]
            if is_import and sent.findtext("ClearExisting") == "true":
                self.rows = []
            pairs = []
            def add(row, parent=None):
                stored = deepcopy(row)
                stored.update(ID=1000+len(self.rows), UID="provided-uid-"+str(len(self.rows)), Children=[])
                if parent:
                    stored.update(ParentID=parent["ID"], ParentUID=parent["UID"])
                if self.corrupt:
                    stored["Name"] = "Unintended value"
                self.rows.append(stored)
                pairs.append({"ForeignID": stored["ForeignID"], "GranicusID": stored["ID"]})
                for child in row["Children"]:
                    add(child, stored)
            for row in supplied:
                add(row)
            self.mutations += 1
            if self.loss:
                self.loss = False
                raise TimeoutError("Synthetic metadata acknowledgement lost")
            keys = ET.SubElement(response, "KeyTable", {f"{{{ENC}}}arrayType": "g:KeyMapping[0]"})
            for pair in pairs:
                item = ET.SubElement(keys, "item")
                for key, typ in model_fields("KeyMapping").items():
                    ET.SubElement(item, key, {f"{{{XSI}}}type": typ}).text = str(pair[key])
        return WriteResponse(200, ET.tostring(envelope))


def metadata_setup(tmp_path, parent_type="event", operation="create"):
    network = MetadataNetwork()
    engine, _, context, change = setup(tmp_path, network)
    context.credentials["granicus"].update(permissions=["agenda_tree:create", "agenda_tree:update"],
        meeting_ids=["11"], foreign_ids=["101", "102"])
    root = node()
    root["Children"] = [node(102)]
    fields = {"ParentType": parent_type}
    fields.update({"MetaDataData": root} if operation == "create" else
                  {"MetaData": [root], "ClearExisting": False, "AsTree": True})
    change.update(entity="agenda_tree", operation=operation, meeting_id="11", fields=fields)
    return engine, network, context, change


@pytest.mark.parametrize("parent_type,operation", [("event", "create"), ("clip", "create"), ("event", "update"), ("clip", "update")])
def test_documented_add_import_exact_nodes_ids_and_parent_readback(tmp_path, parent_type, operation):
    engine, network, context, change = metadata_setup(tmp_path, parent_type, operation)
    request = plan(engine, context, change)
    assert network.mutations == 0
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "completed", result.errors
    item = result.data["items"][0]
    assert item["resolved_foreign_ids"] == {"101": 1000, "102": 1001}
    assert item["readback"][1]["ParentID"] == 1000
    assert item["readback"][1]["ParentUID"] == item["readback"][0]["UID"]
    assert item["agenda_replacement_requested"] is False
    assert engine.execute("commit_write", request, context=context).status == "completed"
    assert network.mutations == 1
    assert "synthetic-private-session" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("corrupt", [False, True])
def test_metadata_lost_reply_reconciles_unique_foreign_ids_without_replay(tmp_path, corrupt):
    engine, network, context, change = metadata_setup(tmp_path)
    request = plan(engine, context, change)
    network.loss, network.corrupt = True, corrupt
    assert engine.execute("commit_write", request, context=context).status == "partial"
    result = engine.execute("commit_write", request, context=context)
    assert result.status == ("partial" if corrupt else "completed"), result.errors
    assert network.mutations == 1


def test_metadata_rejects_destructive_clearing_and_duplicate_keys(tmp_path):
    engine, network, context, change = metadata_setup(tmp_path, operation="update")
    change["fields"]["ClearExisting"] = True
    assert engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context).status == "failed"
    change["fields"]["ClearExisting"] = False
    change["fields"]["MetaData"][0]["Children"][0]["ForeignID"] = 101
    assert engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context).status == "failed"
    assert network.mutations == 0
