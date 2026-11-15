"""Cancellation at durable intent persistence must precede adapter execution."""

import pytest

from civic_data_connectors.storage import update_operation
from test_writes import plan, setup


@pytest.mark.parametrize("explicit_operation_id", [False, True])
def test_persisted_cancel_during_intent_save_prevents_send_and_replay(
    tmp_path, monkeypatch, explicit_operation_id,
):
    engine, context, network = setup(tmp_path)
    if explicit_operation_id:
        context.operation_id = "cancel-during-intent"
    approval = plan(engine, context)
    operation_id = context.operation_id or approval["plan_id"]
    original_put = engine.storage.put
    triggered = False

    def cancel_after_intent(collection, key, value, **kwargs):
        nonlocal triggered
        version = original_put(collection, key, value, **kwargs)
        if collection == "receipts" and not triggered and value["items"][0]["state"] == "sending":
            triggered = True
            update_operation(engine.storage, operation_id, {"cancel_requested": True}, scope=context.scope)
        return version

    monkeypatch.setattr(engine.storage, "put", cancel_after_intent)
    result = engine.execute("commit_write", approval, context=context)
    assert triggered
    assert result.status == "cancelled", result.public_dict()
    assert result.data["items"][0]["state"] == "cancelled"
    assert not network.calls
    stored = engine.execute("receipt", {"plan_id": approval["plan_id"]}, context=context)
    assert stored.status == "cancelled"
    update_operation(engine.storage, operation_id, {"cancel_requested": False}, scope=context.scope)
    assert engine.execute("commit_write", approval, context=context).status == "cancelled"
    assert not network.calls
