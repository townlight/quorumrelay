import xml.etree.ElementTree as ET

import pytest

from test_granicus_metadata import metadata_setup
from test_granicus_write import XSI, plan, setup
from civic_data_connectors.write_transport import WriteResponse


@pytest.mark.parametrize("defect", ["field", "key"])
def test_typed_metadata_confirmation_reopens_without_replay(tmp_path, defect):
    engine, network, context, change = metadata_setup(tmp_path)
    original = network.send
    active = [True]

    def send(url, **kwargs):
        response = original(url, **kwargs)
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if action not in {"GetEventMetaData", "AddEventMetaData"} or not network.mutations:
            return response
        root = ET.fromstring(response.content)
        if defect == "field" and active[0] and action == "GetEventMetaData":
            element = root.find(".//metadata/item/OrderID")
            element.set(f"{{{XSI}}}type", "xsd:boolean")
            element.text = "false"
        if defect == "key":
            if action == "GetEventMetaData":
                root.find(".//metadata/item/ID").text = "1"
                root.findall(".//metadata/item")[1].find("ParentID").text = "1"
            else:
                element = root.find(".//KeyTable/item/GranicusID")
                element.set(f"{{{XSI}}}type", "xsd:boolean")
                element.text = "true"
        return WriteResponse(response.status, ET.tostring(root), response.headers, response.set_cookie_headers)

    network.send = send
    request = plan(engine, context, change)
    assert engine.execute("commit_write", request, context=context).status == "partial"
    reopened, _, _, _ = setup(tmp_path, network)
    assert reopened.execute("commit_write", request, context=context).status == "partial"
    if defect == "field":
        active[0] = False
        assert reopened.execute("commit_write", request, context=context).status == "completed"
    assert network.mutations == 1


@pytest.mark.parametrize("defect", ["parent", "native"])
def test_lost_ack_requires_typed_metadata_identity(tmp_path, defect):
    engine, network, context, change = metadata_setup(tmp_path)
    original = network.send
    active = [True]

    def send(url, **kwargs):
        response = original(url, **kwargs)
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if action != "GetEventMetaData" or not network.mutations or not active[0]:
            return response
        root = ET.fromstring(response.content)
        rows = root.findall(".//metadata/item")
        if defect == "parent":
            rows[0].find("ID").text = "1"
            element = rows[1].find("ParentID")
            element.set(f"{{{XSI}}}type", "xsd:boolean")
            element.text = "true"
        else:
            rows[0].find("ID").set(f"{{{XSI}}}type", "xsd:string")
        return WriteResponse(response.status, ET.tostring(root), response.headers, response.set_cookie_headers)

    network.send = send
    request = plan(engine, context, change)
    network.loss = True
    assert engine.execute("commit_write", request, context=context).status == "partial"
    reopened, _, _, _ = setup(tmp_path, network)
    assert reopened.execute("commit_write", request, context=context).status == "partial"
    active[0] = False
    assert reopened.execute("commit_write", request, context=context).status == "completed"
    assert network.mutations == 1
