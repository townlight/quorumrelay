import xml.etree.ElementTree as ET

from test_granicus_minutes import minutes_setup
from test_granicus_write import XSI, plan as minutes_plan, setup as granicus_reopen
from test_telvue_playlist_write import CHANGE, setup as telvue_setup, plan as telvue_plan
from civic_data_connectors.write_transport import WriteResponse
from quorumrelay import Engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.writes import register


def test_minutes_retained_boolean_readback_reopen_and_recovery(tmp_path):
    engine, network, context, change = minutes_setup(tmp_path)
    network.documents.append({"UID": "old-doc", "Name": "Old", "Type": "document", "Published": False, "Default": False})
    original = network.send
    bad = [True]

    def send(url, **kwargs):
        response = original(url, **kwargs)
        action = kwargs["headers"]["SOAPAction"].split("#")[-1].strip('"')
        if action == "GetClipMinutesDocuments" and network.mutations and bad[0]:
            root = ET.fromstring(response.content)
            element = root.find(".//MinutesDocuments/item/Published")
            element.set(f"{{{XSI}}}type", "xsd:int")
            element.text = "0"
            return WriteResponse(response.status, ET.tostring(root), response.headers, response.set_cookie_headers)
        return response

    network.send = send
    approval = minutes_plan(engine, context, change)
    assert engine.execute("commit_write", approval, context=context).status == "partial"
    reopened, _, _, _ = granicus_reopen(tmp_path, network)
    assert reopened.execute("commit_write", approval, context=context).status == "partial"
    bad[0] = False
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert network.mutations == 1


def test_telvue_retained_nested_id_readback_reopen_and_recovery(tmp_path):
    engine, context, network = telvue_setup(tmp_path)
    network.items[0]["playable"]["id"] = 1
    config = context.credentials["telvue"]
    config["permissions"].append("playlist_membership:create")
    config["medium_ids"] = ["143"]
    change = dict(CHANGE, key="add", entity="playlist_membership", operation="create", fields={"medium_ids": [143]})
    approval = telvue_plan(engine, context, change)
    original = network.send

    def send(url, **kwargs):
        response = original(url, **kwargs)
        if kwargs["method"] == "POST":
            network.items[0]["playable"]["id"] = True
        return response

    network.send = send
    assert engine.execute("commit_write", approval, context=context).status == "partial"
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(network))
    assert reopened.execute("commit_write", approval, context=context).status == "partial"
    network.items[0]["playable"]["id"] = 1
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(method == "POST" for method, _, _ in network.calls) == 1
