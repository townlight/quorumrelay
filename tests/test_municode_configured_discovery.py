"""Configured static listing discovery using a saved fixture and offline transport."""
import base64
import hashlib
from pathlib import Path

from quorumrelay import create_engine
from quorumrelay.providers.contracts import Response

RAW = (Path(__file__).parent / "fixtures/baseline/municode.response").read_bytes()
URL = "https://fixture.municodemeetings.com/meetings3"


class FixtureTransport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        assert url == URL
        assert kwargs["method"] == "GET"
        assert kwargs["allowed_origins"] == ("https://fixture.municodemeetings.com",)
        self.calls.append(url)
        return Response(url, RAW, "text/html", 200)


def discover(**bounds):
    transport = FixtureTransport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": {"provider": "municode-meetings", "url": URL},
        "bounds": {"date_from": "2026-11-01", "date_to": "2026-11-30", **bounds},
    })
    return result, transport


def test_configured_static_listing_is_partial_and_preserves_capture():
    result, transport = discover()
    assert result.status == "partial" and not result.errors
    assert transport.calls == [URL] and result.coverage["pages"] == 1
    assert result.coverage["filtered_records"] == 21
    assert result.coverage["actual_dates"] == ["2026-11-10", "2026-11-17"]
    assert len(result.data["records"]) == 4
    record = result.data["records"][0]
    assert record["identity"]["namespace"] == "//fixture.municodemeetings.com"
    assert record["identity"]["derivation"] == "url_path"
    assert record["identity"]["external_id"] == "/bc-citycouncil/page/city-council-meeting-4"
    assert record["normalized"]["title"] == "City Council Meeting"
    assert record["normalized"]["source_start"] == "2026-11-17T18:30:00-07:00"
    capture = result.data["captures"][0]
    assert base64.b64decode(capture["content_base64"]) == RAW
    assert capture["sha256"] == hashlib.sha256(RAW).hexdigest() == record["capture_sha256"]
    assert result.coverage["checkpoint"] is None
    assert "upstream catalog completeness is unverified" in result.coverage["scope"]


def test_local_record_limit_checkpoint_continues_same_capture():
    first, transport = discover(max_records=2)
    assert first.status == "partial" and len(first.data["records"]) == 2
    assert len(transport.calls) == 1 and first.coverage["checkpoint"]
    second, transport = discover(max_records=2, checkpoint=first.coverage["checkpoint"])
    assert second.status == "partial" and len(second.data["records"]) == 2
    assert len(transport.calls) == 1 and second.coverage["checkpoint"]
    third, transport = discover(max_records=2, checkpoint=second.coverage["checkpoint"])
    assert third.status == "partial" and third.data["records"] == []
    assert len(transport.calls) == 1 and third.coverage["checkpoint"] is None
    assert len({r["identity"]["external_id"] for r in first.data["records"] + second.data["records"]}) == 4


def test_configured_listing_rejects_transfer_over_limit():
    result, transport = discover(parser_bytes=len(RAW) + 1, transfer_bytes=len(RAW) - 1)
    assert result.status == "failed" and not result.data["records"]
    assert result.coverage["checkpoint"] and len(transport.calls) == 1


def test_multi_request_transfer_budget_preserves_first_page():
    from test_suiteone_discovery import OLDER, ROOT, SOURCE, Transport

    transport = Transport()
    budget = len(ROOT) + len(OLDER) - 1
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": SOURCE.public_dict(), "bounds": {"transfer_bytes": budget}})
    assert result.status == "partial" and result.errors and result.coverage["checkpoint"]
    assert [r["identity"]["external_id"] for r in result.data["records"]] == ["1412"]
    assert len(transport.calls) == 2
    assert transport.calls[0][1]["byte_limit"] == budget
    assert transport.calls[1][1]["byte_limit"] == budget - len(ROOT)


def test_resume_root_control_fetch_is_charged_to_budget():
    from test_suiteone_discovery import ROOT, SOURCE, Transport

    first = create_engine(provider_transport=Transport()).execute("discover", {
        "source": SOURCE.public_dict(), "bounds": {"max_pages": 1}})
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": SOURCE.public_dict(), "bounds": {"checkpoint": first.coverage["checkpoint"],
                                                     "transfer_bytes": len(ROOT)}})
    assert result.status == "failed" and result.coverage["checkpoint"]
    assert len(transport.calls) == 1 and transport.calls[0][1]["byte_limit"] == len(ROOT)
