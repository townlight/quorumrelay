"""CivicWeb byte bounds cover every request in the same operation."""
from quorumrelay import Bounds, OperationContext, create_engine

from test_civicweb_listing import DOCS, MEETINGS, SOURCE, TYPES, Transport, discover, ids


def test_meeting_types_and_listing_share_transfer_budget():
    limit = len(TYPES) + len(MEETINGS) - 1
    result, transport = discover(transfer_bytes=limit)
    assert result.status == "failed"
    assert not result.data["records"]
    assert result.coverage["checkpoint"]
    assert transport.calls[-1][1]["byte_limit"] == len(MEETINGS) - 1


def test_document_exhaustion_keeps_meeting_and_resumable_document_task():
    limit = len(TYPES) + len(MEETINGS) + len(DOCS[18421]) - 1
    result, transport = discover(request={"record_types": ["meeting", "document"]},
        date_from="2026-11-04", date_to="2026-11-04", transfer_bytes=limit)
    assert result.status == "partial" and result.errors
    assert ids(result) == ["18421"]
    assert ids(result, "document") == []
    assert transport.calls[-1][1]["byte_limit"] == len(DOCS[18421]) - 1
    resumed, _ = discover(request={"record_types": ["meeting", "document"]},
        date_from="2026-11-04", date_to="2026-11-04", checkpoint=result.coverage["checkpoint"])
    assert ids(resumed) == []
    assert set(ids(resumed, "document")) == {"522441", "522399"}
    assert resumed.coverage["checkpoint"] is None


def test_related_document_list_honors_smaller_transfer_limit():
    transport = Transport()
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, "18421", "document", bounds=Bounds(transfer_bytes=len(DOCS[18421]) - 1))
    assert result.status == "failed"
    assert transport.calls[0][1]["byte_limit"] == len(DOCS[18421]) - 1


def test_related_document_cancellation_during_request_does_not_publish_records():
    transport = Transport()
    context = OperationContext()
    request = transport.request

    def cancelling(url, **kwargs):
        response = request(url, **kwargs)
        context.cancellation.set()
        return response

    transport.request = cancelling
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, "18421", "document", context=context)
    assert result.status == "cancelled"
    assert not result.data
    assert result.coverage["transfer_bytes"] == len(DOCS[18421])
