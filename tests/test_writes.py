"""Synthetic network responses exercise real documented adapter code, never live writes."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors.writes import register


class LegistarNetwork:
    mock = True

    def __init__(self):
        self.records = {}
        self.calls = []
        self.lose_response = False
        self.deny = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        self.calls.append((method, parsed.path, body, deepcopy(headers)))
        assert parsed.hostname == "webapi.legistar.com"
        assert parse_qs(parsed.query)["token"] == ["synthetic-secret"]
        assert deadline_seconds > 0
        if self.deny:
            return WriteResponse(403)
        if method == "POST":
            row = json.loads(body)
            assert "EventDate" in row
            assert "MeetingId" not in row
            row.update(EventId=100 + len(self.records), EventRowVersion="AQ==")
            self.records[str(row["EventId"])] = row
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("synthetic response loss after remote success")
            return WriteResponse(200, json.dumps(row).encode())
        if method == "PUT":
            row = json.loads(body)
            row["EventRowVersion"] = "Ag=="
            self.records[str(row["EventId"])] = row
            return WriteResponse(200, json.dumps(row).encode())
        if "$filter" in parse_qs(parsed.query):
            term = parse_qs(parsed.query)["$filter"][0]
            rows = [row for row in self.records.values() if row["EventGuid"] in term]
            return WriteResponse(200, json.dumps(rows).encode())
        record_id = parsed.path.rsplit("/", 1)[-1]
        return WriteResponse(200, json.dumps(self.records[record_id]).encode())


def setup(tmp_path, network=None):
    network = network or LegistarNetwork()
    store = SQLiteStorage(tmp_path / "writes.sqlite")
    engine = Engine(storage=store)
    register(engine, default_adapters(network))
    context = OperationContext(
        principal="synthetic-actor", client_id="fixture-sdk", tenant="fixture-city",
        authorization=frozenset({"write:plan", "write:commit"}),
        credentials={"legistar": {"namespace": "fixture-city", "token": "synthetic-secret",
                                 "permissions": ["event:create", "event:update"]}},
    )
    return engine, context, network


def create_request():
    return {
        "source": {"provider": "legistar", "url": "https://webapi.legistar.com/v1/fixture-city/events",
                   "namespace": "fixture-city"},
        "changes": [{"key": "event-1", "entity": "event", "operation": "create",
                     "fields": {"EventDate": "2026-11-11T00:00:00", "EventBodyId": 4}}],
    }


def plan(engine, context, request=None):
    result = engine.execute("plan_write", request or create_request(), context=context)
    assert result.status == "completed", result.public_dict()
    return {"plan_id": result.data["plan_id"], "plan_hash": result.data["plan_hash"]}


def test_exact_plan_commit_readback_receipt_and_duplicate(tmp_path):
    engine, context, network = setup(tmp_path)
    request = create_request()
    approval = plan(engine, context, request)
    request["changes"][0]["fields"]["EventBodyId"] = 99
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["mock"] is True
    assert result.data["live_acceptance"] == "NOT_RUN"
    assert result.data["items"][0]["readback"]["EventBodyId"] == 4
    assert "synthetic-secret" not in json.dumps(result.public_dict())
    assert engine.execute("receipt", {"plan_id": approval["plan_id"]}, context=context).data == result.data
    assert engine.execute("commit_write", approval, context=context).status == "completed"
    assert sum(c[0] == "POST" for c in network.calls) == 1


def test_response_loss_restart_read_only_reconciliation(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    network.lose_response = True
    first = engine.execute("commit_write", approval, context=context)
    assert first.status == "partial"
    assert first.data["items"][0]["state"] == "uncertain"
    restarted, context, _ = setup(tmp_path, network)
    second = restarted.execute("commit_write", approval, context=context)
    assert second.status == "completed", second.public_dict()
    assert second.data["items"][0]["reconciled"] is True
    assert sum(c[0] == "POST" for c in network.calls) == 1


def test_auth_hash_scope_permission_and_conflict(tmp_path):
    engine, context, network = setup(tmp_path)
    assert engine.execute("plan_write", create_request()).errors[0].code == "permission_denied"
    approval = plan(engine, context)
    bad = {**approval, "plan_hash": "0" * 64}
    assert engine.execute("commit_write", bad, context=context).errors[0].code == "plan_mismatch"
    context.client_id = "other-client"
    assert engine.execute("commit_write", approval, context=context).errors[0].code == "not_found"
    context.client_id = "fixture-sdk"
    network.deny = True
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert not network.records


def test_concurrent_commit_sends_create_at_most_once(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: engine.execute("commit_write", approval, context=context), range(4)))
    assert any(r.status == "completed" for r in results)
    assert sum(c[0] == "POST" for c in network.calls) == 1


def test_update_changed_provider_state_conflicts_before_put(tmp_path):
    engine, context, network = setup(tmp_path)
    engine.execute("commit_write", plan(engine, context), context=context)
    request = create_request()
    request["changes"] = [{"key": "update", "entity": "event", "operation": "update", "resource_id": 100,
                           "fields": {"EventLocation": "Synthetic Room"}, "expected_version": "AQ=="}]
    approval = plan(engine, context, request)
    network.records["100"]["EventLocation"] = "Someone else's update"
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "failed"
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(c[0] == "PUT" for c in network.calls)


def test_application_tenant_is_not_upstream_namespace(tmp_path):
    engine, context, network = setup(tmp_path)
    context.tenant = "newsroom-a"
    context.allowed_namespaces = frozenset({"fixture-city"})
    context.credentials["legistar"]["allowed_namespaces"] = ["fixture-city"]
    assert engine.execute("commit_write", plan(engine, context), context=context).status == "completed"
    context.credentials["legistar"]["allowed_namespaces"] = ["other-city"]
    assert engine.execute("plan_write", create_request(), context=context).errors[0].code == "permission_denied"


def test_policy_narrowing_after_plan_blocks_commit_and_receipt_without_mutation(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    context.allowed_namespaces = frozenset({"other-city"})
    assert engine.execute("commit_write", approval, context=context).errors[0].code == "permission_denied"
    assert engine.execute("receipt", {"plan_id": approval["plan_id"]}, context=context).errors[0].code == "permission_denied"
    assert not network.calls
    context.allowed_namespaces = frozenset({"fixture-city"})
    context.authorization = frozenset({"write:plan"})
    assert engine.execute("commit_write", approval, context=context).errors[0].code == "permission_denied"
    assert not network.calls
    context.credentials["legistar"]["allowed_namespaces"] = ["fixture-city"]
    context.allowed_namespaces = frozenset({"other-city"})
    assert engine.execute("plan_write", create_request(), context=context).errors[0].code == "permission_denied"
