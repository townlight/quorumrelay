"""Stored cancellation during adapter preflight must stop the civic mutation."""

import io

import pytest

from civic_data_connectors.storage import update_operation
from civic_data_connectors.write_files import stage_write_file
import test_account_apis as essential
import test_granicus_write as granicus
from test_client_write_response_bounds import wistia_update


def granicus_case(tmp_path, kind):
    if kind == "granicus_publication":
        return granicus.publication_setup(tmp_path)
    vendor = granicus.MediaNetwork() if kind == "granicus_media" else granicus.DocumentNetwork("clip")
    engine, _, caller, change = granicus.setup(tmp_path, vendor)
    if kind == "granicus_media":
        caller.credentials["granicus"].update(permissions=["recording:upload"], folder_ids=["11"],
            meeting_ids=["7"], media_origin="https://synthetic-media.granicus.com")
        handle = stage_write_file(engine, io.BytesIO(b"synthetic-video"), context=caller,
                                 filename="approved.mp4", content_type="video/mp4")
        change.update(entity="recording", operation="upload", resource_id=None, parent_id="11", meeting_id="7",
            fields={"FolderID": 11, "NewFileName": "approved.mp4"},
            files=[{"part": "bytes", "filename": "approved.mp4", "content_type": "video/mp4", "file_handle": handle}])
    else:
        caller.credentials["granicus"].update(permissions=["document:update"], meeting_ids=["11"])
        change.update(entity="document", meeting_id="11", fields={"ParentType": "clip", "Kind": "minutes",
            "URL": "https://synthetic-city.granicus.com/supplied.pdf"})
    return engine, vendor, caller, change


@pytest.mark.parametrize("provider", ["wistia", "essential", "granicus", "granicus_document",
                                      "granicus_media", "granicus_publication"])
@pytest.mark.parametrize("explicit_operation_id", [False, True])
def test_durable_preflight_cancellation_prevents_mutation(tmp_path, monkeypatch, provider, explicit_operation_id):
    if provider == "essential":
        engine, vendor, source, change, caller = essential.write_setup(tmp_path)
    elif provider == "granicus":
        engine, vendor, caller, change = granicus.setup(tmp_path)
        source = granicus.SOURCE
    elif provider.startswith("granicus_"):
        engine, vendor, caller, change = granicus_case(tmp_path, provider)
        source = granicus.SOURCE
    else:
        engine, caller, vendor, source, change = wistia_update(tmp_path)
    if explicit_operation_id:
        caller.operation_id = "cancel-preflight"
    result = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    assert result.status == "completed", result.public_dict()
    approval = {key: result.data[key] for key in ("plan_id", "plan_hash")}
    operation_id = caller.operation_id or approval["plan_id"]
    original = vendor.send
    interrupted = False

    def cancel_during_preflight(*args, **kwargs):
        nonlocal interrupted
        response = original(*args, **kwargs)
        if not interrupted:
            interrupted = True
            update_operation(engine.storage, operation_id, {"cancel_requested": True}, scope=caller.scope)
        return response

    monkeypatch.setattr(vendor, "send", cancel_during_preflight)
    result = engine.execute("commit_write", approval, context=caller)
    assert interrupted
    assert result.status == "cancelled", result.public_dict()
    if provider.startswith("granicus"):
        assert vendor.mutations == 0
    elif provider == "essential":
        assert not any(call[1]["method"] == "POST" for call in vendor.calls)
    else:
        assert all(method == "GET" for method, _ in vendor.calls)
    update_operation(engine.storage, operation_id, {"cancel_requested": False}, scope=caller.scope)
    assert engine.execute("commit_write", approval, context=caller).status == "cancelled"


@pytest.mark.parametrize("explicit_operation_id", [False, True])
def test_stored_cancellation_after_first_chunk_keeps_uncertainty_and_never_finishes(
    tmp_path, monkeypatch, explicit_operation_id,
):
    vendor = granicus.DocumentNetwork("clip")
    engine, _, caller, change = granicus.setup(tmp_path, vendor)
    if explicit_operation_id:
        caller.operation_id = "cancel-after-chunk"
    caller.credentials["granicus"].update(permissions=["document:upload"], meeting_ids=["11"])
    data = b"%PDF-1.7\n" + b"x" * 7_000_031
    handle = stage_write_file(engine, io.BytesIO(data), context=caller, filename="large.pdf", content_type="application/pdf")
    change.update(entity="document", operation="upload", meeting_id="11", fields={"ParentType": "clip",
        "Kind": "minutes", "Description": "Full document", "Name": "Large Minutes"},
        files=[{"part": "Document", "filename": "large.pdf", "content_type": "application/pdf", "file_handle": handle}])
    approval = granicus.plan(engine, caller, change)
    operation_id = caller.operation_id or approval["plan_id"]
    original = vendor.send

    def cancel_after_chunk(url, **kwargs):
        response = original(url, **kwargs)
        if b'"add"' in (kwargs.get("body") or b""):
            update_operation(engine.storage, operation_id, {"cancel_requested": True}, scope=caller.scope)
        return response

    monkeypatch.setattr(vendor, "send", cancel_after_chunk)
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "partial", result.public_dict()
    item = result.data["items"][0]
    assert item["state"] == "uncertain" and item["completed_chunks"] == 1 and item["upload_id"]
    assert vendor.mutations == 1 and [len(chunk) for chunk in vendor.chunks] == [7_000_000]
    assert engine.execute("commit_write", approval, context=caller).status == "partial"
    update_operation(engine.storage, operation_id, {"cancel_requested": False}, scope=caller.scope)
    assert engine.execute("commit_write", approval, context=caller).status == "partial"
    assert vendor.mutations == 1 and len(vendor.chunks) == 1
