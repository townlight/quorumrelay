"""Synthetic vendor-client reorder and documented v2 readback transactions."""

from copy import deepcopy
from dataclasses import replace
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

ORIGIN = "https://connect.telvue.com"
SOURCE = {"provider": "telvue", "url": ORIGIN, "namespace": "telvue:fixture"}
CHANGE = {"key": "reorder", "entity": "playlist_order", "operation": "update",
          "resource_id": "837", "meeting_id": "7", "fields": {"playlist_item_ids": [42, 41]}}


class Vendor:
    mock = True

    def __init__(self):
        self.items = [{"id": i, "playlist_id": 837, "sequence_number": n,
                       "playable": {"id": i + 100, "type": "media"}, "unknown": "retained"}
                      for n, i in enumerate([41, 42], 1)]
        self.calls = []
        self.count = 2
        self.fail_after_send = False
        self.ignore = False
        self.echo = False
        self.deny = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert deadline_seconds > 0 and urlsplit(url).netloc == "connect.telvue.com"
        self.calls.append((method, urlsplit(url).path, body))
        if method == "POST":
            assert headers["Cookie"] == "_connect_session=private-cookie"
            assert headers["X-CSRF-Token"] == "private-csrf"
            assert "CONNECT-ACCESS-KEY" not in headers
            if self.deny:
                return WriteResponse(403)
            fields = parse_qs(body.decode())
            if "medium_ids[]" in fields:
                assert url.endswith("/bulk/playlists/837/playlist_items/create")
                if not self.ignore:
                    for medium in fields["medium_ids[]"]:
                        self.items.append({"id": 1000 + int(medium), "playlist_id": 837,
                            "sequence_number": len(self.items) + 1, "playable": {"id": int(medium), "type": "media"}})
                    self.count = len(self.items)
            else:
                order = fields["playlist_item[]"]
                assert order == ["42", "41"]
                if not self.ignore:
                    for item in self.items:
                        item["sequence_number"] = order.index(str(item["id"])) + 1
            if self.fail_after_send:
                raise TimeoutError("secret transport details must not escape")
            return WriteResponse(200, b"saved")
        assert headers["CONNECT-ACCESS-KEY"] == "private-key"
        assert headers["CONNECT-SECRET-PASSPHRASE"] == "private-passphrase"
        assert "Cookie" not in headers and "Authorization" not in headers
        value = ({"playlist": {"id": 837, "playables_count": self.count}}
                 if url.endswith("/837.json") else {"playlist_items": deepcopy(self.items)})
        if self.echo:
            value["echo"] = self.echo
        return WriteResponse(200, json.dumps(value).encode())


def setup(tmp_path):
    network = Vendor()
    context = OperationContext(principal="editor", client_id="fixture", tenant="newsroom",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({SOURCE["namespace"]}), credentials={"telvue": {
            "tenant": "newsroom", "origin": ORIGIN, "allowed_namespaces": [SOURCE["namespace"]],
            "session_cookie": "_connect_session=private-cookie", "csrf_token": "private-csrf",
            "access_key": "private-key", "secret_passphrase": "private-passphrase",
            "permissions": ["playlist_order:update"], "meeting_ids": ["7"], "playlist_ids": ["837"]}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(network))
    return engine, context, network


def plan(engine, context, change=None):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change or CHANGE]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


def test_exact_reorder_readback_reopen_and_no_replay(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    assert all(method == "GET" for method, _, _ in network.calls)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert [r["id"] for r in result.data["items"][0]["readback"]["playlist_items"]] == [42, 41]
    assert all(r["unknown"] == "retained" for r in result.data["items"][0]["readback"]["playlist_items"])
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(network))
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(m == "POST" for m, _, _ in network.calls) == 1
    receipt = reopened.execute("receipt", {"plan_id": approval["plan_id"]}, context=context)
    assert "private-" not in json.dumps(receipt.public_dict())


@pytest.mark.parametrize("fault", ["count", "parent", "duplicate", "sequence", "membership", "echo"])
def test_incomplete_or_malformed_snapshots_prevent_plan(tmp_path, fault):
    engine, context, network = setup(tmp_path)
    if fault == "count":
        network.count = 3
    elif fault == "parent":
        network.items[0]["playlist_id"] = 999
    elif fault == "duplicate":
        network.items[0]["id"] = 42
    elif fault == "sequence":
        network.items[0]["sequence_number"] = 3
    elif fault == "membership":
        network.items[0]["id"] = 43
    else:
        network.echo = "private-csrf"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "failed"
    assert not any(m == "POST" for m, _, _ in network.calls)
    assert "private-" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("fault", ["tenant", "origin", "namespace", "permission", "meeting", "playlist", "header"])
def test_policy_and_session_fail_before_network(tmp_path, fault):
    engine, context, network = setup(tmp_path)
    config = deepcopy(context.credentials["telvue"])
    if fault == "header":
        config["session_cookie"] += "\r\nInjected: value"
    else:
        key = {"tenant": "tenant", "origin": "origin", "namespace": "allowed_namespaces",
               "permission": "permissions", "meeting": "meeting_ids", "playlist": "playlist_ids"}[fault]
        config[key] = "other" if fault in {"tenant", "origin"} else []
    denied = replace(context, credentials={"telvue": config})
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=denied)
    assert result.status == "failed" and not network.calls


def test_preflight_conflict_and_uncertain_readback_do_not_replay(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    network.items[0]["unknown"] = "changed"
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert not any(m == "POST" for m, _, _ in network.calls)
    approval = plan(engine, context)
    network.ignore = True
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "partial" and result.data["items"][0]["state"] == "uncertain"
    assert engine.execute("commit_write", approval, context=context).status == "partial"
    assert sum(m == "POST" for m, _, _ in network.calls) == 1


def test_timeout_after_send_reconciles_without_resending(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    network.fail_after_send = True
    assert engine.execute("commit_write", approval, context=context).status == "partial"
    assert engine.execute("commit_write", approval, context=context).status == "completed"
    assert sum(m == "POST" for m, _, _ in network.calls) == 1


def test_current_transfer_bound_limits_preflight_response_and_prevents_mutation(tmp_path):
    engine, context, network = setup(tmp_path)
    limits = []
    send = network.send
    def bounded_response(url, **options):
        limits.append(options["byte_limit"])
        # Deliberately ignore the declared limit: the adapter must also reject
        # oversized injected responses before approving a mutation plan.
        return send(url, **options)
    network.send = bounded_response
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE],
        "bounds": {"transfer_bytes": 16}}, context=context)
    assert result.status == "failed", result.public_dict()
    assert limits == [16]
    assert not any(method == "POST" for method, _, _ in network.calls)


def test_oversized_post_response_is_uncertain_then_reconciles_without_resend(tmp_path):
    engine, context, network = setup(tmp_path)
    planned = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE],
        "bounds": {"transfer_bytes": 512}}, context=context)
    assert planned.status == "completed", planned.public_dict()
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    send = network.send
    limits = []
    def oversized_post(url, **options):
        response = send(url, **options)
        limits.append(options["byte_limit"])
        if options["method"] == "POST":
            return WriteResponse(200, b"x" * 513)
        return response
    network.send = oversized_post
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "partial", result.public_dict()
    assert result.data["items"][0]["state"] == "uncertain"
    assert limits and set(limits) == {512}
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(network))
    reconciled = reopened.execute("commit_write", approval, context=context)
    assert reconciled.status == "completed", reconciled.public_dict()
    assert sum(method == "POST" for method, _, _ in network.calls) == 1


@pytest.mark.parametrize("secret", ["private-key", "private-passphrase", "private-csrf", "private-cookie"])
def test_credential_echo_never_enters_plan_or_receipt(tmp_path, secret):
    engine, context, network = setup(tmp_path)
    network.echo = secret
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "failed" and secret not in json.dumps(result.public_dict())
    assert not list(engine.storage.list("write_plans", scope=context.scope))


def test_provider_denial_and_cancel_do_not_replay_or_send(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context)
    network.deny = True
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert sum(m == "POST" for m, _, _ in network.calls) == 1
    network.deny = False
    approval = plan(engine, context)
    context.cancellation.set()
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "cancelled"
    assert sum(m == "POST" for m, _, _ in network.calls) == 1


@pytest.mark.parametrize("empty,timeout", [(False, False), (True, False), (False, True)])
def test_membership_add_exact_native_ids_and_restart_no_replay(tmp_path, empty, timeout):
    engine, context, network = setup(tmp_path)
    config = context.credentials["telvue"]
    config["permissions"] += ["playlist_membership:create"]
    config["medium_ids"] = ["143", "144"]
    if empty:
        network.items, network.count = [], 0
    change = dict(CHANGE, key="add", entity="playlist_membership", operation="create", fields={"medium_ids": [143, 144]})
    approval = plan(engine, context, change)
    network.fail_after_send = timeout
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == ("partial" if timeout else "completed"), result.public_dict()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(network))
    result = reopened.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    added = result.data["items"][0]["readback"]["playlist_items"][-2:]
    assert [r["playable"]["id"] for r in added] == [143, 144]
    assert [r["id"] for r in added] == [1143, 1144]
    assert sum(m == "POST" for m, _, _ in network.calls) == 1


@pytest.mark.parametrize("fault", ["unauthorized", "duplicate", "already_present", "wrong_type", "ignored", "wrong_readback"])
def test_membership_denials_and_unconfirmed_readback(tmp_path, fault):
    engine, context, network = setup(tmp_path)
    config = context.credentials["telvue"]
    config["permissions"] += ["playlist_membership:create"]
    config["medium_ids"] = ["141", "143"]
    ids = [143]
    if fault == "unauthorized":
        config["medium_ids"] = []
    elif fault == "duplicate":
        ids = [143, 143]
    elif fault == "already_present":
        ids = [141]
    elif fault == "wrong_type":
        network.items[0]["playable"]["type"] = "stream"
    change = dict(CHANGE, key="add", entity="playlist_membership", operation="create", fields={"medium_ids": ids})
    if fault not in {"ignored", "wrong_readback"}:
        result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
        assert result.status == "failed"
        assert not any(m == "POST" for m, _, _ in network.calls)
    else:
        approval = plan(engine, context, change)
        if fault == "ignored":
            network.ignore = True
        else:
            original = network.send
            def wrong(*args, **kwargs):
                result = original(*args, **kwargs)
                if kwargs["method"] == "POST":
                    network.items[0]["unknown"] = "unapproved change"
                return result
            network.send = wrong
        assert engine.execute("commit_write", approval, context=context).status == "partial"
        assert engine.execute("commit_write", approval, context=context).status == "partial"
        assert sum(m == "POST" for m, _, _ in network.calls) == 1


def test_membership_policy_revocation_prevents_commit(tmp_path):
    engine, context, network = setup(tmp_path)
    config = context.credentials["telvue"]
    config["permissions"] += ["playlist_membership:create"]
    config["medium_ids"] = ["143"]
    change = dict(CHANGE, key="add", entity="playlist_membership", operation="create", fields={"medium_ids": [143]})
    approval = plan(engine, context, change)
    config["medium_ids"] = []
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert not any(m == "POST" for m, _, _ in network.calls)


def test_cancellation_during_final_plan_read_does_not_persist_plan(tmp_path):
    engine, context, network = setup(tmp_path)
    original = network.send

    def cancelled(url, **kwargs):
        response = original(url, **kwargs)
        if url.endswith("/playlist_items.json"):
            context.cancellation.set()
        return response
    network.send = cancelled
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CHANGE]}, context=context)
    assert result.status == "cancelled", result.public_dict()
    assert not list(engine.storage.list("write_plans", scope=context.scope))
