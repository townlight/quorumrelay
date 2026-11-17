"""Pinned WSDL generated-minutes creation over the real durable coordinator."""

import xml.etree.ElementTree as ET

import pytest

from test_granicus_write import Network, WSDL, SOAP, RPC, ENC, XSI, SOURCE, model_fields, setup, plan
from civic_data_connectors.write_transport import WriteResponse

CLIP_UID = "b6b28c4e-ab07-49e1-b66d-69c72cd448db"
TEMPLATE_UID = "8ca106cd-0585-45ee-a166-9af606102016"


class MinutesNetwork(Network):
    def __init__(self, loss="none"):
        super().__init__("ClipData", "GetClip", "UpdateClip", "clip")
        self.values["UID"] = CLIP_UID
        self.documents = []
        self.loss = loss

    def send(self, url, **kwargs):
        method = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if method not in {"GetClipMinutesDocuments", "CreateClipGeneratedMinutesDocument"}:
            return super().send(url, **kwargs)
        assert kwargs["headers"]["Cookie"] == "SID=synthetic-private-session"
        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        response = ET.SubElement(ET.SubElement(envelope, f"{{{SOAP}}}Body"), f"{{{RPC}}}{method}Response")
        if method == "CreateClipGeneratedMinutesDocument":
            sent = ET.fromstring(kwargs["body"]).find(f"{{{SOAP}}}Body/{{{RPC}}}{method}")
            message = WSDL.find(f'.//{{http://schemas.xmlsoap.org/wsdl/}}message[@name="{method}Request"]')
            assert {node.tag for node in sent} == {node.get("name") for node in message}
            assert sent.findtext("clipUid") == CLIP_UID
            assert sent.findtext("templateUid") == TEMPLATE_UID
            self.documents.append({"UID": "provided-document-guid", "Name": sent.findtext("name"), "Type": "provided-type",
                "Published": sent.findtext("isPublished") == "true", "Default": sent.findtext("isDefault") == "true"})
            self.mutations += 1
            if self.loss == "reply":
                self.loss = "none"
                raise TimeoutError("Synthetic minutes response loss")
        else:
            if self.documents and self.loss == "readback":
                self.loss = "none"
                raise TimeoutError("Synthetic minutes readback loss")
            collection = ET.SubElement(response, "MinutesDocuments", {f"{{{ENC}}}arrayType": "g:MinutesDocumentData[0]"})
            for doc in self.documents:
                item = ET.SubElement(collection, "item")
                for key, typ in model_fields("MinutesDocumentData").items():
                    ET.SubElement(item, key, {f"{{{XSI}}}type": typ}).text = str(doc[key]).lower() if type(doc[key]) is bool else doc[key]
        return WriteResponse(200, ET.tostring(envelope))


def minutes_setup(tmp_path, loss="none"):
    network = MinutesNetwork(loss)
    engine, _, context, change = setup(tmp_path, network)
    context.credentials["granicus"].update(permissions=["generated_minutes:create"], meeting_ids=["11"])
    change.update(entity="generated_minutes", operation="create", meeting_id="11", fields={
        "clipUid": CLIP_UID, "name": "Approved draft minutes", "templateUid": TEMPLATE_UID,
        "isPublished": False, "isDefault": False})
    return engine, network, context, change


@pytest.mark.parametrize("loss", ["none", "reply", "readback"])
def test_generated_minutes_are_approved_creation_with_scoped_readback_and_no_replay(tmp_path, loss):
    engine, network, context, change = minutes_setup(tmp_path, loss)
    request = plan(engine, context, change)
    assert network.mutations == 0
    first = engine.execute("commit_write", request, context=context)
    assert first.status == ("completed" if loss == "none" else "partial"), first.errors
    result = engine.execute("commit_write", request, context=context)
    assert result.status == "completed", result.errors
    assert network.mutations == 1
    item = result.data["items"][0]
    assert item["document_uid"] == "provided-document-guid"
    assert item["publication_requested"] is False and item["default_requested"] is False
    assert item["submitted_only_fields"] == ["templateUid"] and item["document_bytes_verified"] is False


def test_generated_minutes_reject_missing_flags_and_uid_parent_mismatch(tmp_path):
    engine, network, context, change = minutes_setup(tmp_path)
    del change["fields"]["isPublished"]
    assert engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context).status == "failed"
    change["fields"]["isPublished"] = False
    change["fields"]["clipUid"] = TEMPLATE_UID
    assert engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context).status == "failed"
    assert network.mutations == 0
