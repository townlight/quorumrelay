"""Actual native BoardBook Minutes remain source text, not inferred decisions."""

import base64
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

SOURCE = Source("boardbook", "https://meetings.boardbook.org/Public/Minutes/3307?meeting=755664",
                input_format="boardbook-public-minutes-html")
CONTENT = (Path(__file__).parent / "fixtures/boardbook-minutes-755664.html").read_bytes()
PDF = b"%PDF-1.7\nsynthetic transfer only"


class Network:
    def __init__(self, response_url=SOURCE.url):
        self.calls, self.response_url = [], response_url

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allowed_origins"] == ("https://meetings.boardbook.org",)
        if url == SOURCE.url:
            assert options["allow_redirects"] is False
            return Response(self.response_url, CONTENT, "text/html")
        assert url == "https://meetings.boardbook.org/Public/DownloadMinutes/3307?meeting=755664"
        return Response(url, PDF, "application/pdf")


def test_actual_native_hierarchy_action_source_fields_and_raw_capture():
    assert hashlib.sha256(CONTENT).hexdigest() == "97973d79ec8860d5eed416ba04ebceff191ec312ba94d955a2a22ae7fc8ba3f1"
    result = create_engine().normalize(SOURCE, CONTENT, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"]) == 27
    meeting, *items = result.data["records"]
    assert meeting["identity"]["external_id"] == "755664"
    assert meeting["normalized"]["source_document_type"] == "Minutes"
    assert meeting["normalized"]["scheduled_start"] == "2026-08-10T17:30:00"
    assert meeting["normalized"]["documents"][0]["kind"] == "minutes"
    row = next(r for r in items if r["identity"]["external_id"] == "18486089")
    assert row["identity"]["parent"]["external_id"] == "18486087"
    assert row["identity"]["parent"]["parent"] == meeting["identity"]
    action, = row["normalized"]["source_fields"]["Actions"]
    assert "Benson: Yea" in action and "No Action(s)" not in action
    assert row["text"][-1]["field"] == "source_fields.Actions" and row["text"][-1]["text"] == action
    assert not {"votes", "motions", "attendance"} & row["normalized"].keys()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CONTENT


def test_default_fetch_attachment_search_persistence_reopen_retry_and_zip(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    caller = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.fetch(replace(SOURCE, input_format=None), context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    attachment = engine.fetch_attachment(SOURCE, result.data["records"][0], index=0, capture=CONTENT, context=caller)
    assert attachment.status == "completed", attachment.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    found = reopened.execute("search", {"query": {"phrases": ["Benson: Yea"]}}, context=caller)
    assert found.data["hits"], found.public_dict()
    identities = [h["identity"] for h in found.data["hits"]]
    assert len({str(v) for v in identities}) == len(identities)
    exported = reopened.execute("export", {"format": "zip", "bundle": result.data}, context=caller)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data


@pytest.mark.parametrize("before,after", [
    (b'/Public/DownloadMinutes/3307?meeting=755664', b'/Public/DownloadMinutes/3307?meeting=755665'),
    (b'/Public/DownloadMinutes/3307?', b'/Public/DownloadMinutes/3308?'),
    (b'data-agendaitemid="18486089"', b'data-agendaitemid="18486087"'),
    (b'agenda-item-children-of-18486087', b'agenda-item-children-of-18486089'),
])
def test_changed_native_download_item_or_parent_rejected(before, after):
    assert before in CONTENT
    result = create_engine().normalize(SOURCE, CONTENT.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("url", [SOURCE.url + "&meeting=2", SOURCE.url + "#fragment",
    SOURCE.url.replace("https:", "http:"), SOURCE.url.replace("755664", "0")])
def test_bad_source_context_fails_before_network(url):
    network = Network()
    result = create_engine(provider_transport=network).discover(replace(SOURCE, url=url))
    assert result.status == "failed", result.public_dict()
    assert not network.calls


def test_wrong_response_and_transfer_bound_fail_without_complete_empty_result():
    result = create_engine(provider_transport=Network(SOURCE.url + "&other=1")).discover(SOURCE)
    assert result.errors and not result.data["records"], result.public_dict()
    network = Network()
    result = create_engine(provider_transport=network).discover(SOURCE, bounds=Bounds(transfer_bytes=16))
    assert result.errors and not result.data["records"], result.public_dict()
    assert network.calls[0][1]["byte_limit"] == 16
