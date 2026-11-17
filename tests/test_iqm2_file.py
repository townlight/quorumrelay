import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures"
EVIDENCE = json.loads((FIXTURES / "iqm2-legifile-7478.capture.json").read_bytes())
CONTENT = base64.b64decode(EVIDENCE["content_base64"], validate=True)
URL = EVIDENCE["url"]
SOURCE = Source("iqm2", URL, input_format="iqm2-legislative-file-html")
PARENT_EVIDENCE = json.loads((FIXTURES / "iqm2-detail-1496.capture.json").read_bytes())
PARENT_CONTENT = base64.b64decode(PARENT_EVIDENCE["content_base64"], validate=True)
PARENT = Source("iqm2", PARENT_EVIDENCE["source_url"], input_format="iqm2-meeting-detail-html")


class Network:
    def __init__(self, response=None):
        self.calls, self.after_request = [], None
        self.response = response or Response(URL, CONTENT, "text/html")

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.after_request:
            self.after_request()
        if "FileOpen.aspx" in url:
            return Response(url, b"%PDF-1.7\nsynthetic file printout", "application/pdf")
        assert url == URL
        assert kwargs["allow_redirects"] is False
        return self.response


def setup(tmp_path, response=None):
    network = Network(response)
    owner = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    context = OperationContext(principal="reader", client_id="client", tenant="city")
    parent = owner.normalize(PARENT, PARENT_CONTENT, input_format=PARENT.input_format, context=context)
    assert parent.status == "completed", parent.public_dict()
    assert owner.execute("import_bundle", {"bundle": parent.data, "persist": True}, context=context).status == "completed"
    return owner, network, context, parent.data


def test_actual_file_text_and_three_native_downloads_keep_other_meeting_references_separate():
    assert len(CONTENT) == EVIDENCE["bytes"] == 91857
    assert hashlib.sha256(CONTENT).hexdigest() == EVIDENCE["sha256"]
    result = create_engine().normalize(SOURCE, CONTENT, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    normalized = record["normalized"]
    assert record["identity"]["external_id"] == "7478" and record["identity"]["parent"] is None
    assert normalized["source_meeting_context"] == "1496"
    assert normalized["meeting_membership"] == "not_verified_by_file_page_alone"
    assert normalized["source_file_type"] == "Staff Report"
    assert len(normalized["documents"]) == 3 and len(normalized["related_references"]) == 5
    assert [d["external_id"] for d in normalized["documents"]] == ["60688", "21288", "21287"]
    assert "Future year funding is contingent on Council budget approval" in record["text"][1]["text"]
    assert "R ecommended" not in record["text"][0]["text"]
    assert "motion" not in normalized and "vote" not in normalized
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CONTENT


def test_related_detail_replays_parent_and_preserves_identity_text_files_and_captures_after_reopen(tmp_path):
    owner, network, context, parent = setup(tmp_path)
    owner = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    result = owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=context)
    assert result.status == "partial", result.public_dict()
    assert len(network.calls) == 1 and network.calls[0][0] == URL
    assert network.calls[0][1]["allowed_origins"] == ("https://santamonicacityca.iqm2.com",)
    record = result.data["records"][0]
    previous = next(r for r in parent["records"] if r["identity"]["external_id"] == "7478")
    assert record["identity"] == previous["identity"]
    assert all(relation in record["relationships"] for relation in previous["relationships"])
    assert len([r for r in record["relationships"] if r["relation"] == "document"]) == 3
    assert record["normalized_sha256"] == canonical_hash(record["normalized"])
    assert record["normalized"]["meeting_membership"] == "verified_by_retained_meeting_capture"
    assert result.data["captures"][0]["sha256"] == parent["capture"]["sha256"]
    assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}, context=context).status == "completed"
    owner = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    found = owner.execute("search", {"query": {"phrases": ["Future year funding is contingent"]}}, context=context)
    assert any(h["record"]["identity"]["external_id"] == "7478" for h in found.data["hits"]), found.public_dict()
    exported = owner.execute("export", {"format": "zip", "bundle": result.data}, context=context)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data
    attachment = owner.fetch_attachment(PARENT, record, index=0, context=context)
    assert attachment.status == "completed", attachment.public_dict()
    assert network.calls[-1][0].endswith("FileOpen.aspx?Type=30&ID=60688")


@pytest.mark.parametrize("kind", ["missing_parent", "other_scope", "unlisted_item", "changed_source", "tampered_capture"])
def test_related_read_rejects_unverified_membership_scope_source_and_capture_before_network(tmp_path, kind):
    owner, network, context, bundle = setup(tmp_path)
    parent, item, source = "1496", "7478", PARENT
    if kind == "missing_parent":
        parent = "1497"
    elif kind == "other_scope":
        context = replace(context, client_id="another")
    elif kind == "unlisted_item":
        item = "99999"
    elif kind == "changed_source":
        source = replace(PARENT, url=PARENT.url.replace("1496", "1497"))
    else:
        capture = deepcopy(bundle["capture"])
        capture["content_base64"] = base64.b64encode(PARENT_CONTENT + b" ").decode()
        owner.storage.put("captures", capture["sha256"], capture, scope=context.scope)
    result = owner.fetch_related(source, parent, "legislative_file", external_id=item, context=context)
    assert result.status == "failed", result.public_dict()
    assert not network.calls


@pytest.mark.parametrize("response", [
    Response(URL, CONTENT.replace(b'id="ContentPlaceholder1_txtLegiFileID" value="7478"',
        b'id="ContentPlaceholder1_txtLegiFileID" value="7479"'), "text/html"),
    Response(URL, CONTENT.replace(b'action="../Agency/LegiFile.aspx?Frame=&amp;MeetingID=1496',
        b'action="../Agency/LegiFile.aspx?Frame=&amp;MeetingID=1497'), "text/html"),
    Response(URL + "&other=1", CONTENT, "text/html"),
    Response(URL, CONTENT, "application/json"),
    Response(URL, CONTENT, "text/html", 403),
])
def test_related_detail_rejects_changed_native_binding_mime_redirect_and_denial(tmp_path, response):
    if response.url == URL and response.content_type == "text/html" and response.status == 200:
        assert response.content != CONTENT
    owner, network, context, _ = setup(tmp_path, response)
    result = owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=context)
    assert result.status == "failed", result.public_dict()
    assert len(network.calls) == 1


def test_related_detail_honors_cancellation_and_current_transfer_bound(tmp_path):
    owner, network, context, _ = setup(tmp_path)
    context.cancellation.set()
    assert owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=context).status == "cancelled"
    assert not network.calls
    context.cancellation.clear()
    network.after_request = context.cancellation.set
    assert owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=context).status == "cancelled"
    assert len(network.calls) == 1
    context.cancellation.clear()
    network.after_request = None
    result = owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=context,
                                 bounds=Bounds(transfer_bytes=90000))
    assert result.status == "failed" and network.calls[-1][1]["byte_limit"] == 90000


def test_related_detail_stops_after_its_deadline_and_fetch_only_caller_needs_no_parse_grant(tmp_path, monkeypatch):
    owner, network, context, _ = setup(tmp_path)
    only_fetch = replace(context, allowed_operations=frozenset({"fetch"}))
    result = owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=only_fetch)
    assert result.status == "partial", result.public_dict()
    from civic_data_connectors.providers import iqm2_file
    clock = [0.0]
    monkeypatch.setattr(iqm2_file, "monotonic", lambda: clock[0])
    network.after_request = lambda: clock.__setitem__(0, 2.0)
    result = owner.fetch_related(PARENT, "1496", "legislative_file", external_id="7478", context=only_fetch,
                                 bounds=Bounds(deadline_seconds=1))
    assert result.status == "failed" and len(network.calls) == 2
