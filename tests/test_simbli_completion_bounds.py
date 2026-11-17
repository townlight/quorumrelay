"""Simbli public requests and response mapping share one operation budget."""

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from civic_data_connectors.providers import simbli, simbli_detail
from test_simbli_discovery import FIRST, SECOND, SOURCE, Transport
from test_simbli_detail import SOURCE as DETAIL_SOURCE, Transport as DetailTransport


def test_listing_aggregate_transfer_limit_is_not_reset_per_page():
    network = Transport()
    source = Source("simbli", simbli.HOST + simbli.LIST + "?S=36031063")
    limit = len(FIRST) + len(SECOND) - 1
    engine = create_engine(provider_transport=network)
    result = engine.discover(
        source, bounds=Bounds(max_pages=2, transfer_bytes=limit))
    assert result.errors, result.public_dict()
    assert len(result.data["records"]) == 50
    assert result.coverage["transfer_bytes"] == len(FIRST) + len(SECOND)
    assert network.calls[1][1]["byte_limit"] == limit - len(FIRST)
    assert result.coverage["checkpoint"]
    resumed = engine.discover(source, bounds=Bounds(
        max_pages=1, checkpoint=result.coverage["checkpoint"]))
    assert not resumed.errors and len(resumed.data["records"]) == 50
    assert resumed.coverage["transfer_bytes"] == len(SECOND)
    assert not ({r["identity"]["external_id"] for r in result.data["records"]}
                & {r["identity"]["external_id"] for r in resumed.data["records"]})


def test_listing_exact_transfer_exhaustion_stops_before_another_request():
    network = Transport()
    source = Source("simbli", simbli.HOST + simbli.LIST + "?S=36031063")
    result = create_engine(provider_transport=network).discover(
        source, bounds=Bounds(max_pages=2, transfer_bytes=len(FIRST)))
    assert result.errors and len(network.calls) == 1
    assert len(result.data["records"]) == 50
    assert result.coverage["transfer_bytes"] == len(FIRST)


def test_listing_cancelled_transport_cannot_seed_a_continuation():
    caller = OperationContext()

    class Interrupted(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            caller.cancellation.set()
            return response

    network = Interrupted()
    result = create_engine(provider_transport=network).discover(SOURCE, context=caller)
    assert result.status == "cancelled" and result.errors
    assert len(network.calls) == 1 and result.coverage["checkpoint"] is None
    assert not result.data["records"] and not result.data["bundles"]


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_listing_mapping_cannot_publish_after_interruption(monkeypatch, boundary):
    caller, clock = OperationContext(), [0.0]
    original = simbli._rows_bundle

    def interrupted(*args, **kwargs):
        bundle = original(*args, **kwargs)
        caller.cancellation.set() if boundary == "cancel" else clock.__setitem__(0, 2.0)
        return bundle

    monkeypatch.setattr(simbli, "_rows_bundle", interrupted)
    monkeypatch.setattr(simbli, "monotonic", lambda: clock[0])
    result = create_engine(provider_transport=Transport()).discover(
        SOURCE, bounds=Bounds(deadline_seconds=1), context=caller)
    assert not result.data["records"] and not result.data["bundles"]
    assert result.errors
    assert result.status == ("cancelled" if boundary == "cancel" else "failed")


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_detail_mapping_cannot_publish_after_interruption(monkeypatch, boundary):
    caller, clock = OperationContext(), [0.0]
    original = simbli_detail.parse_bundle

    def interrupted(*args, **kwargs):
        bundle = original(*args, **kwargs)
        caller.cancellation.set() if boundary == "cancel" else clock.__setitem__(0, 2.0)
        return bundle

    monkeypatch.setattr(simbli_detail, "parse_bundle", interrupted)
    monkeypatch.setattr(simbli_detail, "monotonic", lambda: clock[0])
    network = DetailTransport()
    result = create_engine(provider_transport=network).execute(
        "fetch", {"source": DETAIL_SOURCE, "bounds": {"deadline_seconds": 1}}, context=caller)
    assert not result.data["records"] and not result.data["bundles"]
    assert result.errors and len(network.calls) == 2
    assert result.status == ("cancelled" if boundary == "cancel" else "failed")


def test_detail_cancellation_on_page_response_stops_before_any_service_read():
    caller = OperationContext()

    class Interrupted(DetailTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            caller.cancellation.set()
            return response

    network = Interrupted()
    result = create_engine(provider_transport=network).execute(
        "fetch", {"source": DETAIL_SOURCE}, context=caller)
    assert result.status == "cancelled" and result.errors
    assert len(network.calls) == 1 and not result.data["records"]
