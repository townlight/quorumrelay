"""Synthetic swap requests checked against the separately captured vendor schema."""
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from jsonschema import Draft202012Validator

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors.writes import register

EVIDENCE = Path(__file__).parents[1] / "docs/capabilities/evidence/wistia-swap"


def contract(name):
    text = (EVIDENCE / (name + ".md")).read_text(encoding="utf-8")
    return json.loads(re.search(r"````json\s*(.*?)\s*````", text, re.S).group(1))


class Network:
    mock = True

    def __init__(self):
        self.rows = {key: {"hashed_id": key, "id": index, "type": "Video", "updated": "2026-11-12"}
                     for index, key in enumerate(("original", "replacement"), 1)}
        self.job = {"id": 7, "hashed_id": "job7", "status": "queued"}
        self.calls = []
        self.lost = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.netloc == "api.wistia.com"
        assert headers["X-Wistia-API-Version"] == "2026-09"
        assert headers["Authorization"] == "Bearer synthetic-swap-token"
        assert byte_limit > 0 and deadline_seconds > 0
        self.calls.append((method, parsed.path))
        if method == "PUT":
            assert parsed.path == "/modern/medias/original/swap"
            data = json.loads(body)
            spec = contract("put_medias-mediahashedid-swap")
            op = spec["paths"]["/medias/{mediaHashedId}/swap"]["put"]
            Draft202012Validator(op["requestBody"]["content"]["application/json"]["schema"]).validate(data)
            assert data == {"replacement_media_id": "replacement"}
            if self.lost:
                raise TimeoutError("synthetic lost acknowledgement")
            value = {"message": "queued", "background_job_status": deepcopy(self.job)}
            Draft202012Validator(op["responses"]["200"]["content"]["application/json"]["schema"]).validate(value)
        elif parsed.path == "/modern/background_job_status/job7":
            value = {"background_job_status": deepcopy(self.job)}
        else:
            assert method == "GET"
            value = deepcopy(self.rows[parsed.path.rsplit("/", 1)[-1]])
        return WriteResponse(200, json.dumps(value).encode())


def setup(tmp_path):
    network = Network()
    engine = Engine(storage=SQLiteStorage(tmp_path / "state.sqlite"))
    register(engine, default_adapters(network))
    namespace = "//fixture-account.wistia.com"
    context = OperationContext(principal="editor", client_id="swap-fixture", tenant="newsroom",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({namespace}),
        credentials={"wistia": {"token": "synthetic-swap-token", "allowed_namespaces": [namespace],
            "permissions": ["media_swap:update"], "meeting_ids": ["meeting1"],
            "resource_ids": ["original", "replacement"]}})
    request = {"source": {"provider": "wistia", "namespace": namespace,
                         "url": "https://fixture-account.wistia.com/"},
        "changes": [{"key": "swap1", "entity": "media_swap", "operation": "update",
                     "resource_id": "original", "meeting_id": "meeting1",
                     "fields": {"replacement_media_id": "replacement"}}]}
    return engine, context, network, request


def plan(engine, context, request):
    result = engine.execute("plan_write", request, context=context)
    assert result.status == "completed", result.public_dict()
    assert "synthetic-swap-token" not in json.dumps(result.public_dict())
    return result, {k: result.data[k] for k in ("plan_id", "plan_hash")}


def test_vendor_evidence_hashes_and_swap_request_contract():
    source = json.loads((EVIDENCE / "source.json").read_text(encoding="utf-8"))
    for capture in source["captures"]:
        value = (EVIDENCE / capture["file"]).read_bytes()
        assert len(value) == capture["byte_length"]
        assert hashlib.sha256(value).hexdigest() == capture["sha256"]
    spec = contract("put_medias-mediahashedid-swap")
    assert spec["info"]["version"] == "2026.09.0"
    assert set(spec["paths"]["/medias/{mediaHashedId}/swap"]) >= {"put"}


@pytest.mark.parametrize("status,expected", [("queued", "pending"), ("started", "pending"),
                                            ("failed", "failed"), ("finished", "uncertain")])
def test_swap_queued_receipt_reconciliation_never_replays(tmp_path, status, expected):
    engine, context, network, request = setup(tmp_path)
    planned, approval = plan(engine, context, request)
    change = planned.data["plan"]["changes"][0]
    assert change["effects"]["replaces_content_at_existing_embeds_and_urls"] is True
    assert change["before"]["replacement"]["hashed_id"] == "replacement"
    assert all(method == "GET" for method, _ in network.calls)
    committed = engine.execute("commit_write", approval, context=context)
    assert committed.data["items"][0]["state"] == "pending"
    network.job["status"] = status
    # New engine/coordinator proves durable receipt recovery across process-style reopen.
    reopened = Engine(storage=SQLiteStorage(tmp_path / "state.sqlite"))
    register(reopened, default_adapters(network))
    reconciled = reopened.execute("commit_write", approval, context=context)
    assert reconciled.data["items"][0]["state"] == expected
    if status == "finished":
        assert reconciled.data["items"][0]["readback"]["hashed_id"] == "original"
    assert sum(method == "PUT" for method, _ in network.calls) == 1


@pytest.mark.parametrize("problem", ["wrong_type", "replacement_changed", "denied_replacement", "lost_ack"])
def test_swap_validation_conflict_policy_and_lost_ack(tmp_path, problem):
    engine, context, network, request = setup(tmp_path)
    if problem == "wrong_type":
        network.rows["replacement"]["type"] = "Audio"
        assert engine.execute("plan_write", request, context=context).status == "failed"
        assert not any(method == "PUT" for method, _ in network.calls)
        return
    _, approval = plan(engine, context, request)
    if problem == "replacement_changed":
        network.rows["replacement"]["updated"] = "changed"
    elif problem == "denied_replacement":
        context.credentials["wistia"]["resource_ids"] = ["original"]
    else:
        network.lost = True
    result = engine.execute("commit_write", approval, context=context)
    if problem == "denied_replacement":
        assert result.status == "failed"
    else:
        assert result.data["items"][0]["state"] == ("uncertain" if problem == "lost_ack" else "conflict")
    engine.execute("commit_write", approval, context=context)
    assert sum(method == "PUT" for method, _ in network.calls) == (1 if problem == "lost_ack" else 0)


@pytest.mark.parametrize("problem", ["same_id", "revoked_grant", "wrong_job"])
def test_swap_exact_targets_current_grant_and_exact_job(tmp_path, problem):
    engine, context, network, request = setup(tmp_path)
    if problem == "same_id":
        request["changes"][0]["fields"]["replacement_media_id"] = "original"
        assert engine.execute("plan_write", request, context=context).status == "failed"
        assert network.calls == []
        return
    _, approval = plan(engine, context, request)
    if problem == "revoked_grant":
        context.credentials["wistia"]["permissions"] = []
        assert engine.execute("commit_write", approval, context=context).status == "failed"
        assert not any(method == "PUT" for method, _ in network.calls)
    else:
        engine.execute("commit_write", approval, context=context)
        network.job["hashed_id"] = "other-job"
        result = engine.execute("commit_write", approval, context=context)
        assert result.data["items"][0]["state"] == "uncertain"
        assert sum(method == "PUT" for method, _ in network.calls) == 1
