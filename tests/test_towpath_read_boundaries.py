"""Explicit Towpath detail reads retain their bounds through normalization."""
import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from civic_data_connectors.providers import retrieval
from civic_data_connectors.providers.contracts import Response
from test_towpath_detail import CAPTURE, SOURCE


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_towpath_mapper_cannot_outlive_read_bounds(monkeypatch, boundary):
    clock = [0.0]
    caller = OperationContext()
    original = retrieval.parse_page

    class Transport:
        def request(self, url, **options):
            return Response(url, CAPTURE, "text/html")

    def map_then_interrupt(*args, **kwargs):
        result = original(*args, **kwargs)
        if boundary == "cancel":
            caller.cancellation.set()
        else:
            clock[0] = 2.0
        return result

    monkeypatch.setattr(retrieval, "parse_page", map_then_interrupt)
    monkeypatch.setattr(retrieval, "monotonic", lambda: clock[0])
    result = create_engine(provider_transport=Transport()).fetch(SOURCE, {"external_id": "64"},
        bounds=Bounds(deadline_seconds=1), context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "failed"), result.public_dict()
    assert result.data is None


def test_towpath_explicit_detail_applies_transfer_bound_before_mapping():
    limits = []

    class Transport:
        def request(self, url, **options):
            limits.append(options["byte_limit"])
            return Response(url, CAPTURE, "text/html")

    result = create_engine(provider_transport=Transport()).fetch(SOURCE, {"external_id": "64"},
        bounds=Bounds(transfer_bytes=16))
    assert limits == [16]
    assert result.status == "failed" and result.errors, result.public_dict()
    assert result.data is None
