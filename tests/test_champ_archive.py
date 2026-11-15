"""Offline calendar discovery against captured public CHAMP responses."""
import json
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures/champ-archive"
ARCHIVE = (FIXTURES / "archive.json").read_bytes()
GROUP = (FIXTURES / "group.json").read_bytes()
SOURCE = Source("champ", "https://play.champds.com/lakezurichil/archive/1", options={"archive_group_id": 1})
DATES = {"date_from": "2026-11-01", "date_to": "2026-11-30"}


class Transport:
    def __init__(self, archive=ARCHIVE, group=GROUP):
        self.archive, self.group, self.calls = archive, group, []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allowed_origins"] == ("https://playapi.champds.com",)
        assert kwargs["allow_redirects"] is False
        return Response(url, self.archive if url.endswith("/archive/1") else self.group, "text/html", 200)


def discover(transport=None, source=SOURCE, **bounds):
    transport = transport or Transport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": source.public_dict(), "bounds": {**DATES, **bounds}})
    return result, transport


def test_calendar_capture_metadata_and_native_records():
    result, transport = discover()
    assert result.status == "partial", result.public_dict()
    assert [r["identity"]["external_id"] for r in result.data["records"]] == ["211", "210"]
    record = result.data["records"][0]
    assert record["identity"]["namespace"] == "//champds.com/lakezurichil"
    assert record["normalized"]["meeting_date"] == "2026-11-16"
    assert record["normalized"]["scheduled_start"] == "2026-11-17T01:00:00Z"
    assert record["original"]["EventDescription"] is not None
    assert record["source_revision"]["kind"] == "provider_supplied"
    assert result.coverage["external_eci_enabled"] is True
    assert result.coverage["external_eci_included"] is False
    assert transport.calls == ["https://playapi.champds.com/lakezurichil/archive/1",
        "https://playapi.champds.com/lakezurichil/archiveGroupDate/1/LOCAL/2026-11-01T00:00:00/2026-11-30T23:59:59"]


def test_local_continuation_reopens_engine_and_detects_changed_bytes():
    first, _ = discover(max_records=1)
    checkpoint = first.coverage["checkpoint"]
    assert checkpoint and len(first.data["records"]) == 1
    second, _ = discover(checkpoint=checkpoint, max_records=1)
    assert [r["identity"]["external_id"] for r in second.data["records"]] == ["210"]
    assert second.coverage["checkpoint"] is None
    changed, _ = discover(Transport(group=GROUP + b" "), checkpoint=checkpoint, max_records=1)
    assert changed.status == "failed" and not changed.data["records"]


def test_page_budget_continues_metadata_then_group():
    first, _ = discover(max_pages=1)
    assert first.coverage["checkpoint"] and first.data["records"] == []
    second, transport = discover(checkpoint=first.coverage["checkpoint"], max_pages=1)
    assert len(second.data["records"]) == 2 and len(transport.calls) == 1


@pytest.mark.parametrize("problem", ["customer", "archive", "group", "type", "malformed"])
def test_invalid_metadata_or_group_fails_closed(problem):
    metadata = json.loads(ARCHIVE)
    group = GROUP
    if problem == "customer":
        metadata["Customer"]["CustomerAccessID"] = "other"
    elif problem == "archive":
        metadata["Archive"]["CustomerArchiveID"] = 9
    elif problem == "group":
        metadata["ArchiveGroups"][0]["CustomerArchiveGroupID"] = 9
    elif problem == "type":
        metadata["ArchiveGroups"][0]["DisplayTypeID"] = 3
    else:
        group = b'{}'
    result, _ = discover(Transport(archive=json.dumps(metadata).encode(), group=group))
    assert result.status == "failed" and not result.data["records"]


def test_malformed_row_and_local_date_filter_disclosed():
    data = json.loads(GROUP)
    data.append({"CustomerEventID": "invalid"})
    result, _ = discover(Transport(group=json.dumps(data).encode()), date_from="2026-11-16")
    assert [r["identity"]["external_id"] for r in result.data["records"]] == ["211"]
    assert result.coverage["malformed_rows_omitted"] == 1
    assert result.coverage["filtered_records"] == 1


def test_month_and_group_required():
    result, _ = discover(date_to="2026-12-01")
    assert result.status == "failed"
    source = Source("champ", SOURCE.url)
    result, _ = discover(source=source)
    assert result.status == "failed"


def test_cancelled_before_requests():
    from quorumrelay import OperationContext

    context = OperationContext()
    context.cancellation.set()
    transport = Transport()
    result = create_engine(provider_transport=transport).execute(
        "discover", {"source": SOURCE.public_dict(), "bounds": DATES}, context=context)
    assert result.status == "cancelled" and transport.calls == []


def test_cancelled_during_request_retains_checkpoint():
    from quorumrelay import OperationContext

    context = OperationContext()

    class CancellingTransport(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            context.cancellation.set()
            return response

    transport = CancellingTransport()
    result = create_engine(provider_transport=transport).execute(
        "discover", {"source": SOURCE.public_dict(), "bounds": DATES}, context=context)
    assert result.status == "cancelled" and result.coverage["checkpoint"]
    assert len(transport.calls) == 1 and result.data["records"] == []


def test_persist_reopen_and_neutral_zip_preserve_native_row(tmp_path):
    import io

    from civic_data_connectors.interchange import read_bundle, write_bundle
    from civic_data_connectors.storage import SQLiteStorage

    path = tmp_path / "catalog.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=Transport())
    first = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": {**DATES, "max_records": 1}})
    found = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": {
        **DATES, "max_records": 1, "checkpoint": first.coverage["checkpoint"]}})
    bundle = found.data["bundles"][0]
    original = bundle["records"][0]["original"]
    saved = engine.execute("import_bundle", {"bundle": bundle, "persist": True, "coverage": found.coverage})
    assert saved.status in {"completed", "partial"}, saved.public_dict()
    reopened = create_engine(storage=SQLiteStorage(path))
    searched = reopened.execute("search", {"query": {"terms": ["Meeting"]}})
    assert len(searched.data["hits"]) == 1
    from civic_data_connectors.models import OperationContext

    stored_bundles = reopened.storage.list("bundles", scope=OperationContext().scope)
    assert len(stored_bundles) == 1
    assert stored_bundles[0].value["extensions"]["champ_archive_context"] == bundle["extensions"]["champ_archive_context"]
    for fmt in ("json", "jsonl", "zip"):
        output = io.BytesIO()
        write_bundle(bundle, output, format=fmt)
        restored = read_bundle(output.getvalue(), format=fmt)
        assert restored["records"][0]["original"] == original
        assert restored["extensions"]["champ_archive_context"] == bundle["extensions"]["champ_archive_context"]


def test_resumed_bundle_retains_both_captures_and_exact_request_context():
    import base64
    import hashlib

    first, _ = discover(max_records=1)
    second, _ = discover(checkpoint=first.coverage["checkpoint"], max_records=1)
    bundle = second.data["bundles"][0]
    context = bundle["extensions"]["champ_archive_context"]
    metadata = context["archive_metadata_capture"]
    assert metadata == first.data["captures"][0]
    assert metadata["captured_at"] == first.data["captures"][0]["captured_at"]
    assert base64.b64decode(metadata["content_base64"]) == ARCHIVE
    assert metadata["sha256"] == hashlib.sha256(ARCHIVE).hexdigest()
    assert base64.b64decode(bundle["capture"]["content_base64"]) == GROUP
    assert metadata["retrieval_url"] == "https://playapi.champds.com/lakezurichil/archive/1"
    assert context["group_retrieval_url"] == bundle["capture"]["retrieval_url"]
    assert context["archive_id"] == context["archive_group_id"] == 1
    assert (context["date_from"], context["date_to"]) == ("2026-11-01", "2026-11-30")
    assert context["external_eci_enabled"] is True and context["external_eci_included"] is False


def test_tampered_continuation_metadata_rejected():
    import base64

    first, _ = discover(max_records=1)
    token = first.coverage["checkpoint"]
    state = json.loads(base64.urlsafe_b64decode(token))
    state["queue"][0]["metadata_capture"]["content_base64"] = base64.b64encode(b"{}").decode()
    modified = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    result, _ = discover(checkpoint=modified)
    assert result.status == "failed" and result.data["records"] == []


def test_deadline_expires_during_metadata_response(monkeypatch):
    import civic_data_connectors.providers.champ_archive as archive_module

    now = [100.0]
    monkeypatch.setattr(archive_module, "monotonic", lambda: now[0])

    class SlowTransport(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            now[0] += 2
            return response

    result, transport = discover(SlowTransport(), deadline_seconds=1)
    assert result.status == "failed" and result.errors
    assert result.data["records"] == [] and result.coverage["checkpoint"]
    assert len(transport.calls) == 1


def test_group_response_over_parser_limit_keeps_metadata():
    oversized = GROUP + b" " * len(ARCHIVE)
    result, transport = discover(Transport(group=oversized), parser_bytes=len(ARCHIVE) + 1)
    assert result.status == "failed" and result.errors and not result.data["records"]
    assert len(transport.calls) == 2 and len(result.data["captures"]) == 1
    assert result.data["captures"][0]["retrieval_url"].endswith("/archive/1")
    assert result.coverage["checkpoint"] and not result.coverage["catalog_complete"]


def test_aggregate_transfer_limit_keeps_metadata():
    result, transport = discover(transfer_bytes=len(ARCHIVE) + len(GROUP) - 1)
    assert result.status == "failed" and result.errors and not result.data["records"]
    assert len(transport.calls) == 2 and len(result.data["captures"]) == 1
    assert result.data["captures"][0]["retrieval_url"].endswith("/archive/1")
    assert result.coverage["checkpoint"] and not result.coverage["catalog_complete"]
