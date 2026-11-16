"""Synthetic minutes contracts based on the saved public client."""
import json
import pytest
from urllib.parse import parse_qs, urlsplit
from civic_data_connectors.models import Bounds, OperationContext
from civic_data_connectors.providers.simbli_detail import fetch_detail
from test_simbli_detail import Transport, FORM
from quorumrelay.providers.contracts import Response
from quorumrelay import Source
from civic_data_connectors.providers.simbli_detail import parse_bundle, MEETING_MINUTES, SIMPLE_MINUTES

URL = "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36031063&MID=4942"
SOURCE = Source(provider="simbli", url=URL)

def test_meeting_minutes_preserve_nested_unjoined_items():
    payload = {"meeting_id": "4942", "response": {"MeetingMinutes": {"Minutes": "<p>Approved</p>"}, "AttendessHtml": "<p>Ada</p>", "RSSFeedLink": "https://example.com/feed", "LstItemMinutes": [{"Title": "Section", "ChildMinutesLst": [{"Title": "Item", "Minutes": "<p>Nested item decision</p>", "HyperLinks": [{"Url": "https://example.com", "Title": "Link"}]}]}]}}
    bundle = parse_bundle(SOURCE, "tenant", json.dumps(payload).encode(), MEETING_MINUTES)
    row = bundle["records"][0]
    assert row["identity"]["external_id"] == "4942"
    assert [t["text"] for t in row["text"]] == ["Approved", "Ada", "Nested item decision"]
    assert row["text"][2]["field"] == "LstItemMinutes[0].ChildMinutesLst[0].Minutes"
    assert row["normalized"]["minutes_item_hierarchy"] == payload["response"]["LstItemMinutes"]
    assert row["normalized"]["minutes_item_hierarchy"][0]["ChildMinutesLst"][0]["HyperLinks"][0] == {"Url": "https://example.com", "Title": "Link"}

@pytest.mark.parametrize("format", [MEETING_MINUTES, SIMPLE_MINUTES])
def test_null_response_has_no_fabricated_record(format):
    bundle = parse_bundle(SOURCE, "tenant", b'{"meeting_id":"4942","response":null}', format)
    assert not bundle["records"]

def test_mismatched_context_and_malformed_hierarchy_fail():
    for obj in [{"meeting_id": "wrong", "response": {}}, {"meeting_id": "4942", "response": {"LstItemMinutes": [{"ChildMinutesLst": {}}]}}]:
        with pytest.raises(ValueError):
            parse_bundle(SOURCE, "tenant", json.dumps(obj).encode(), MEETING_MINUTES)


class MinutesTransport(Transport):
    def __init__(self, *, fail=False, flag=True):
        super().__init__(FORM.replace(b"var enAjSFlag='';", b"var enAjSFlag='private-flag';" if flag else b""))
        self.fail_minutes = fail

    def request(self, url, **kwargs):
        path = urlsplit(url).path
        if path not in {"/Services/api/GetMinutes/", "/Services/api/GetMeetingMinutes/"}:
            return super().request(url, **kwargs)
        self.calls.append(url)
        q = parse_qs(urlsplit(url).query, keep_blank_values=True)
        assert q["enuid"] == [""] and q["searchText"] == [""] and q["matchType"] == [""]
        if path.endswith("/GetMinutes/"):
            assert q["enitemid"] == [""]
            body = {"Minutes": "<p>Simple minutes</p>"}
        else:
            assert q["enajs"] == ["private-flag"]
            body = {"MeetingMinutes": {"Minutes": "<p>Public minutes</p>"}, "AttendessHtml": "<p>Ada</p>", "LstItemMinutes": []}
        return Response(url, json.dumps(body).encode(), "application/json", 403 if self.fail_minutes else 200)

def test_fresh_minutes_preserve_meeting_and_private_controls():
    transport = MinutesTransport()
    result = fetch_detail(SOURCE, "tenant", Bounds(), OperationContext(), transport)
    supporting = next(url for url in transport.calls if urlsplit(url).path.endswith("/GetSupportingDocuments/"))
    assert parse_qs(urlsplit(supporting).query, keep_blank_values=True)["enitemid"] == [""]
    meetings = [r for r in result.data["records"] if r["identity"]["record_type"] == "meeting"]
    assert len(meetings) == 1
    from civic_data_connectors.engine import canonical_hash
    assert meetings[0]["normalized_sha256"] == canonical_hash(meetings[0]["normalized"])
    assert {t["text"] for t in meetings[0]["text"]} >= {"Simple minutes", "Public minutes", "Ada"}
    public = json.dumps(result.public_dict())
    assert "private-flag" not in public and "synthetic-private-control" not in public
    captures = [c["sha256"] for c in result.data["captures"]]
    assert all(t["provenance"]["capture_sha256"] in captures for t in meetings[0]["text"])

def test_missing_flag_preserves_independent_results():
    result = fetch_detail(SOURCE, "tenant", Bounds(), OperationContext(), MinutesTransport(flag=False))
    assert result.data["records"] and any(e.code == "simbli_meeting_minutes_unavailable" for e in result.errors)
    assert result.coverage["truncated"] is False

def test_minutes_failure_retains_other_data():
    result = fetch_detail(SOURCE, "tenant", Bounds(), OperationContext(), MinutesTransport(fail=True))
    assert result.data["records"]
    assert any(e.code in {"simbli_simple_minutes_unavailable", "simbli_meeting_minutes_unavailable"} for e in result.errors)
    assert result.coverage["truncated"] is False

def test_no_budget_for_minutes_keeps_previous_meeting():
    transport = MinutesTransport()
    result = fetch_detail(SOURCE, "tenant", Bounds(max_pages=3), OperationContext(), transport)
    assert result.data["records"]
    assert not any(urlsplit(u).path.endswith("/GetMeetingMinutes/") for u in transport.calls)
    assert any(e.code == "simbli_meeting_minutes_unavailable" for e in result.errors)
    assert result.coverage["truncated"] is True

def test_minutes_capture_survives_sqlite_and_zip(tmp_path):
    import base64
    from quorumrelay import create_engine
    from civic_data_connectors.interchange import read_bundle
    from civic_data_connectors.storage import SQLiteStorage
    result = fetch_detail(SOURCE, "tenant", Bounds(), OperationContext(), MinutesTransport())
    bundle = next(b for b in result.data["bundles"] if any(r["identity"]["record_type"] == "meeting" for r in b["records"]))
    assert len(bundle["captures"]) == 2
    database = tmp_path / "minutes.sqlite"
    engine = create_engine(storage=SQLiteStorage(database))
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    reopened = create_engine(storage=SQLiteStorage(database))
    import hashlib
    for text in bundle["records"][0]["text"]:
        digest = text["provenance"]["capture_sha256"]
        capture = reopened.storage.get("captures", digest, scope=OperationContext().scope)
        assert capture is not None
        assert hashlib.sha256(base64.b64decode(capture.value["content_base64"])).hexdigest() == digest
    found = reopened.execute("search", {"query": {"phrases": ["public minutes"]}})
    assert any(r["identity"]["external_id"] == "4942" for r in found.data["records"])
    exported = reopened.execute("export", {"bundle_key": imported.data["bundle_key"], "format": "zip"})
    zip_bytes = base64.b64decode(exported.data["content_base64"])
    assert read_bundle(zip_bytes, format="zip") == bundle
    destination = create_engine(storage=SQLiteStorage(tmp_path / "destination.sqlite"))
    restored = destination.execute("import_bundle", {"format": "zip", "persist": True}, content=zip_bytes)
    reopened_destination = create_engine(storage=SQLiteStorage(tmp_path / "destination.sqlite"))
    for capture in restored.data["bundle"]["captures"]:
        with reopened_destination.storage.open_capture(capture["storage_reference"], scope=OperationContext().scope) as stream:
            import hashlib
            assert hashlib.sha256(stream.read()).hexdigest() == capture["sha256"]

def test_transfer_bound_preserves_prior_captures():
    transport = MinutesTransport()
    result = fetch_detail(SOURCE, "tenant", Bounds(transfer_bytes=len(FORM) + 70), OperationContext(), transport)
    assert result.coverage["transfer_bytes"] <= len(FORM) + 70 or result.errors
    assert result.status in {"failed", "partial"}
    assert result.coverage["source_complete"] is False
    baseline = fetch_detail(SOURCE, "tenant", Bounds(), OperationContext(), MinutesTransport())
    exact = fetch_detail(SOURCE, "tenant", Bounds(transfer_bytes=baseline.coverage["transfer_bytes"]), OperationContext(), MinutesTransport())
    assert not exact.errors and not exact.coverage["truncated"]

def test_cancel_during_minutes_prevents_publishing_response():
    context = OperationContext()
    class Cancelling(MinutesTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if urlsplit(url).path == "/Services/api/GetMeetingMinutes/":
                context.cancellation.set()
            return response
    result = fetch_detail(SOURCE, "tenant", Bounds(), context, Cancelling())
    assert result.status == "cancelled"
    assert all("Public minutes" not in str(r.get("text")) for r in result.data["records"])

def test_simple_item_context_binds_only_supplied_native_id():
    data = {"meeting_id": "4942", "agenda_item_id": 17, "response": {"Minutes": "<p>Item minutes</p>", "unknown": 4}}
    bundle = parse_bundle(SOURCE, "tenant", json.dumps(data).encode(), SIMPLE_MINUTES)
    record = bundle["records"][0]
    assert record["identity"]["record_type"] == "agenda_item"
    assert record["identity"]["external_id"] == "17"
    assert record["identity"]["parent"]["external_id"] == "4942"
    assert record["text"][0]["text"] == "Item minutes"
    assert bundle["capture"]["original_values"]["response"]["unknown"] == 4

@pytest.mark.parametrize("format", [MEETING_MINUTES, SIMPLE_MINUTES])
def test_error_object_is_not_minutes(format):
    with pytest.raises(ValueError):
        parse_bundle(SOURCE, "tenant", b'{"meeting_id":"4942","response":{"error":"not available"}}', format)

@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hi", "https://user:pass@example.com/"])
def test_unsafe_rss_stays_raw(url):
    obj = {"meeting_id": "4942", "response": {"RSSFeedLink": url}}
    bundle = parse_bundle(SOURCE, "tenant", json.dumps(obj).encode(), MEETING_MINUTES)
    assert bundle["records"][0]["normalized"]["minutes_rss_url"] is None
    assert bundle["capture"]["original_values"]["response"]["RSSFeedLink"] == url

def test_deadline_during_minutes_prevents_publishing(monkeypatch):
    import civic_data_connectors.providers.simbli_detail as module
    now = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: now[0])
    class Late(MinutesTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if urlsplit(url).path == "/Services/api/GetMeetingMinutes/":
                now[0] = 10.0
            return response
    result = fetch_detail(SOURCE, "tenant", Bounds(deadline_seconds=2), OperationContext(), Late())
    assert result.coverage["deadline_exceeded"] and result.coverage["truncated"]
    assert all("Public minutes" not in str(r.get("text")) for r in result.data["records"])

@pytest.mark.parametrize("input_format", [MEETING_MINUTES, SIMPLE_MINUTES])
def test_registered_saved_minutes_format(input_format):
    from quorumrelay import create_engine
    content = json.dumps({"meeting_id": "4942", "response": {"Minutes": "<p>Item</p>"} if input_format == SIMPLE_MINUTES else {"MeetingMinutes": {"Minutes": "<p>Meeting</p>"}}}).encode()
    result = create_engine().execute("normalize", {"source": {"provider": "simbli", "url": URL, "input_format": input_format}}, content=content)
    assert result.status == "completed", result.public_dict()
    assert result.data["records"][0]["text"]

class SelectedMinutesTransport:
    def __init__(self, fail=False):
        from test_simbli_detail import ContentTransport
        self.base = ContentTransport()
        self.fail = fail
        self.calls = self.base.calls

    def request(self, url, **kwargs):
        path = urlsplit(url).path
        q = parse_qs(urlsplit(url).query, keep_blank_values=True)
        if path == "/Services/api/GetMinutes/" and q.get("enitemid") != [""]:
            self.calls.append(url)
            body = b'{"Minutes":"<p>Selected decision</p>"}'
            return Response(url, body, "application/json", 403 if self.fail else 200)
        return self.base.request(url, **kwargs)


def test_selected_item_minutes_bind_fresh_tree_and_capture():
    from test_simbli_detail import _selected_source, ROOT
    from quorumrelay import create_engine
    tree = json.loads((ROOT / "items.json").read_bytes())
    item = tree["Items"][0]
    transport = SelectedMinutesTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": _selected_source()})
    reads = [u for u in transport.calls if urlsplit(u).path == "/Services/api/GetMinutes/"]
    assert [parse_qs(urlsplit(u).query, keep_blank_values=True)["enitemid"][0] for u in reads] == ["", item["ID"]]
    records = [r for r in result.data["records"] if r["identity"]["record_type"] == "agenda_item" and r["identity"]["external_id"] == str(item["AgendaID"])]
    assert len(records) == 1 and records[0]["identity"]["parent"]["external_id"] == "4942"
    text = next(t for t in records[0]["text"] if t["text"] == "Selected decision")
    bundle = next(b for b in result.data["bundles"] if b["capture"]["input_format"] == "simbli-item-content-json")
    assert text["provenance"]["capture_sha256"] in [c["sha256"] for c in bundle["captures"]]
    assert "enitemid=" not in json.dumps(result.public_dict())


def test_selected_item_minutes_failure_retains_content_and_meeting_read():
    from test_simbli_detail import _selected_source
    from quorumrelay import create_engine
    transport = SelectedMinutesTransport(fail=True)
    result = create_engine(provider_transport=transport).execute("fetch", {"source": _selected_source()})
    assert any(e.code == "simbli_item_minutes_unavailable" for e in result.errors)
    assert any(b["capture"]["input_format"] == "simbli-item-content-json" and b["records"] for b in result.data["bundles"])
    assert any(urlsplit(u).path == "/Services/api/GetMeetingMinutes/" for u in transport.calls)


def test_selected_item_minutes_page_budget_preserves_item():
    from test_simbli_detail import _selected_source
    from quorumrelay import create_engine
    transport = SelectedMinutesTransport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": _selected_source(), "bounds": {"max_pages": 5}})
    assert result.coverage["truncated"]
    assert any(e.code == "simbli_item_minutes_unavailable" for e in result.errors)
    assert any(b["capture"]["input_format"] == "simbli-item-content-json" and b["records"] for b in result.data["bundles"])
    assert len([u for u in transport.calls if urlsplit(u).path == "/Services/api/GetMinutes/"]) == 1
