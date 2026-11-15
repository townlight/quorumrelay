"""Cancellation and deadline apply through account response mapping."""

import pytest

from quorumrelay import Bounds, Source, create_engine
from civic_data_connectors.providers import account_reads
from test_account_apis import ESSENTIAL, MEETING, TELVUE, Network, context, structure


@pytest.mark.parametrize("provider", ["telvue", "municode-meetings"])
@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_mapping_cannot_finish_after_cancellation_or_deadline(monkeypatch, provider, boundary):
    telvue = provider == "telvue"
    network = Network({"media": [{"id": 8, "title": "Council"}]} if telvue
                      else {"meetingStructure": structure()})
    caller = context(provider)
    clock = [0.0]
    mapper_name = "telvue_bundle" if telvue else "essential_bundle"
    original = getattr(account_reads, mapper_name)

    def map_then_interrupt(*args, **kwargs):
        bundle = original(*args, **kwargs)
        if boundary == "cancel":
            caller.cancellation.set()
        else:
            clock[0] = 2.0
        return bundle

    monkeypatch.setattr(account_reads, mapper_name, map_then_interrupt)
    monkeypatch.setattr(account_reads, "monotonic", lambda: clock[0])
    source = Source(provider, TELVUE if telvue else ESSENTIAL, namespace="account-a")
    request = {"api_resource": "media"} if telvue else {
        "api_resource": "multimedia", "external_id": MEETING}
    result = create_engine(provider_transport=network).fetch(
        source, request, bounds=Bounds(deadline_seconds=1), context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "failed"), result.public_dict()
    assert result.data is None
    assert len(network.calls) == 1
    if boundary == "deadline":
        assert result.errors[0].code == "account_read_failed"
