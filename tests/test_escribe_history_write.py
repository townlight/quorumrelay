"""Pinned-WSDL history creation through a synthetic independent SOAP server."""
from copy import deepcopy
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.escribe_write import EscribeWriteAdapter
from civic_data_connectors.providers.identification import validate_source
from civic_data_connectors.write_transport import WriteResponse
from test_escribe_publishing import SOURCE, URL, PORTAL, MEETING, response, plan
from test_escribe_history import VALUE, fields

ENTITY = "agenda_item_history_step"
STEP = {"AgendaItemId": 12, "Category": None, "Comments": "Literal supplied history",
        "Date": "2026-11-15T18:30:00", "Id": {"AgendaItemHistoryId": 42, "Id": 7, "PortalId": PORTAL},
        "MeetingDate": None, "MeetingId": MEETING, "MeetingTypeId": None, "MeetingTypeName": None,
        "Number": None, "Sponsor": None, "Stage": None, "Status": "Literal status"}


class Server:
    mock = True

    def __init__(self):
        self.value = deepcopy(VALUE)
        self.calls, self.mutations = [], 0
        self.lose = None
        self.wrong_id = False
        self.wrong_readback = False
        self.on_read = lambda: None

    def send(self, url, **options):
        assert url == URL and options["method"] == "POST"
        request = ET.fromstring(options["body"])
        node = request.find("{" + soap.SOAP + "}Body")[0]
        method = node.tag.split("}")[1]
        self.calls.append(method)
        relation = request.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        if method == "AgendaItemHistoryCreate":
            assert len(node) == 1 and node[0].tag == "{" + soap.NS + "}history"
            assert [c.tag.split("}")[1] for c in node[0]] == list(STEP)
            assert node[0].findtext("{" + soap.NS + "}Comments") == STEP["Comments"]
            self.mutations += 1
            assigned = {**STEP["Id"], "Id": 8}
            value = {**deepcopy(STEP), "Id": assigned}
            if self.wrong_readback:
                value["Comments"] = "Different source text"
            votes = self.value.pop("Votes", None)
            self.value["Steps"] = {"AgendaItemHistoryStep": [value]}
            if votes is not None:
                self.value["Votes"] = votes
            if self.lose == "response":
                raise OSError("Synthetic response loss")
            if self.wrong_id:
                assigned = {**assigned, "AgendaItemHistoryId": 999}
            raw = response(method, assigned, relation=relation)
        else:
            assert method == "AgendaItemItemHistoryView"
            assert [c.text for c in node] == [MEETING, "12"]
            if self.lose == "readback" and self.mutations:
                raise OSError("Synthetic readback loss")
            envelope = ET.fromstring(response(method, {}, relation=relation))
            fields(envelope.find("{" + soap.SOAP + "}Body")[0][0], self.value, soap.NS)
            raw = ET.tostring(envelope)
            self.on_read()
        return WriteResponse(200, raw, {"Content-Type": "application/soap+xml"}, True)


def setup(tmp_path):
    server = Server()
    source = replace(SOURCE, namespace=validate_source(SOURCE))
    ctx = OperationContext(tenant="test", authorization=frozenset({"write:plan", "write:commit"}),
        credentials={"escribe": {"endpoint": URL, "tenant": "test", "allowed_namespaces": [source.namespace],
            "permissions": [ENTITY + ":create"], "meeting_ids": [MEETING], "agenda_item_ids": ["12"],
            "portal_ids": [PORTAL]}})
    owner = create_engine(storage=SQLiteStorage(tmp_path / "history-write.sqlite"),
                          write_adapters={"escribe": EscribeWriteAdapter(server)})
    change = {"key": "step", "entity": ENTITY, "operation": "create", "meeting_id": MEETING,
              "parent_id": "12", "fields": deepcopy(STEP)}
    return owner, server, source, ctx, change


def test_exact_history_plan_commit_readback_reopen_and_no_duplicate(tmp_path):
    owner, server, source, ctx, change = setup(tmp_path)
    approval = plan(owner, source, ctx, change)
    assert not server.mutations
    result = owner.execute("commit_write", approval, context=ctx)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"] == server.value
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "history-write.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(server)})
    assert reopened.execute("commit_write", approval, context=ctx).status == "completed"
    assert server.mutations == 1
    duplicate = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=ctx)
    assert duplicate.status == "failed" and server.mutations == 1


@pytest.mark.parametrize("case", ["portal", "meeting", "item", "history", "permission", "missing", "unknown"])
def test_unapproved_or_unbound_history_never_creates(tmp_path, case):
    owner, server, source, ctx, change = setup(tmp_path)
    if case == "portal":
        change["fields"]["Id"]["PortalId"] = MEETING
    elif case == "meeting":
        change["fields"]["MeetingId"] = PORTAL
    elif case == "item":
        change["fields"]["AgendaItemId"] = 99
    elif case == "history":
        change["fields"]["Id"]["AgendaItemHistoryId"] = 99
    elif case == "permission":
        ctx.credentials["escribe"]["permissions"] = []
    elif case == "missing":
        del change["fields"]["Comments"]
    else:
        change["fields"]["unmapped"] = "value"
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=ctx)
    assert result.status == "failed" and not server.mutations


def test_history_changed_after_plan_cannot_mutate(tmp_path):
    owner, server, source, ctx, change = setup(tmp_path)
    approval = plan(owner, source, ctx, change)
    server.value["History"]["Comments"] = "Concurrent change"
    assert owner.execute("commit_write", approval, context=ctx).status != "completed"
    assert not server.mutations


@pytest.mark.parametrize("case", ["response", "readback", "wrong_id", "wrong_readback"])
def test_uncertain_create_never_replays_and_only_exact_readback_reconciles(tmp_path, case):
    owner, server, source, ctx, change = setup(tmp_path)
    approval = plan(owner, source, ctx, change)
    if case in {"response", "readback"}:
        server.lose = case
    else:
        setattr(server, case, True)
    assert owner.execute("commit_write", approval, context=ctx).status == "partial"
    assert server.mutations == 1
    server.lose = None
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "history-write.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(server)})
    result = reopened.execute("commit_write", approval, context=ctx)
    assert result.status == ("completed" if case == "readback" else "partial"), result.public_dict()
    assert server.mutations == 1


def test_cancellation_during_preflight_prevents_mutation(tmp_path):
    owner, server, source, ctx, change = setup(tmp_path)
    approval = plan(owner, source, ctx, change)
    server.on_read = ctx.cancellation.set
    assert owner.execute("commit_write", approval, context=ctx).status != "completed"
    assert not server.mutations


@pytest.mark.parametrize("max_pages", [1, 2])
def test_insufficient_commit_call_budget_fails_during_plan_without_network(tmp_path, max_pages):
    owner, server, source, ctx, change = setup(tmp_path)
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change],
        "bounds": {"max_pages": max_pages}}, context=ctx)
    assert result.status == "failed" and not server.calls and not server.mutations
