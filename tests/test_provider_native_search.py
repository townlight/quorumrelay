"""Wistia native search maps the official response, not synthetic provider semantics."""

import base64
import json
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage


class SearchTransport:
    def __init__(self, status=200, payload=None):
        self.calls = []
        self.status = status
        self.payload = payload if payload is not None else {"data": {"medias": [
            {"hashed_id": "recording1", "name": "Council recording", "description": "Supplied metadata",
             "created": "2026-11-11T01:00:00Z", "updated": "2026-11-11T02:00:00Z",
             "folder_hashed_id": "folder1", "transcript_matches": [
                 {"text": "The water budget was approved", "start_time_seconds": 12.5,
                  "start_time_formatted": "0:12", "thumbnail_url": None}], "unknown": [False, None]},
            {"hashed_id": "recording2", "name": "Broad provider candidate", "description": "Watershed budgets",
             "transcript_matches": []}], "folders": [], "subfolders": [], "channels": [],
             "channel_episodes": [], "webinars": []}}

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(url, json.dumps(self.payload).encode(), "application/json", self.status)


def request():
    return {"native": True, "source": {"provider": "wistia", "url": "https://api.wistia.com/modern/medias"},
            "query": {"terms": ["water"], "phrases": ["budget was approved"]}}


def test_native_search_requests_real_route_and_preserves_excerpt_timestamps_and_original(tmp_path):
    transport = SearchTransport()
    engine = create_engine(provider_transport=transport, storage=SQLiteStorage(tmp_path / "search.sqlite"))
    context = OperationContext(credentials={"wistia_token": "secret-read-token"}, operation_id="search1")
    result = engine.execute("search", request(), context=context)
    assert result.status == "partial", result.public_dict()
    assert len(transport.calls) == 1
    url, kwargs = transport.calls[0]
    assert urlsplit(url).path == "/modern/search"
    assert parse_qs(urlsplit(url).query) == {"q": ["water budget was approved"], "resource_type[]": ["media"]}
    assert kwargs["headers"]["X-Wistia-API-Version"] == "2026-09"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
    assert kwargs["allowed_origins"] == ("https://api.wistia.com",)
    assert len(result.data["hits"]) == 1
    hit = result.data["hits"][0]
    assert hit["identity"]["external_id"] == "recording1"
    assert hit["matches"][0]["timestamp_seconds"] == 12.5
    assert hit["matches"][0]["completeness"] == "partial"
    assert result.coverage["native_search"] is True
    assert result.coverage["provider_caps"]["pagination"] is False
    assert result.coverage["catalog_complete"] is False
    capture = result.data["bundle"]["capture"]
    assert json.loads(base64.b64decode(capture["content_base64"])) == transport.payload
    assert "secret-read-token" not in json.dumps(result.public_dict())
    status = engine.execute("status", {"operation_id": "search1"}, context=context)
    assert status.data["result"]["coverage"]["native_search"] is True
    imported = engine.execute("import_preview", {"bundle": result.data["bundle"]}, context=replace(context, operation_id=None))
    assert imported.status == "completed"
    assert imported.data["bundle"]["records"][0]["original"]["unknown"] == [False, None]


def test_native_search_denials_failures_and_invalid_response_do_not_become_empty_success():
    for transport, context in [
        (SearchTransport(), OperationContext()),
        (SearchTransport(status=403), OperationContext(credentials={"wistia_token": "token"})),
        (SearchTransport(payload={"not_data": []}), OperationContext(credentials={"wistia_token": "token"})),
        (SearchTransport(), OperationContext(credentials={"wistia_token": "token"},
                                              allowed_namespaces=frozenset())),
    ]:
        result = create_engine(provider_transport=transport).execute("search", request(), context=context)
        assert result.status == "failed", result.public_dict()
        assert result.data is None


def test_native_search_upload_date_does_not_become_meeting_date():
    transport = SearchTransport()
    engine = create_engine(provider_transport=transport)
    wanted = request()
    wanted["query"]["date_from"] = "2026-11-01"
    result = engine.execute("search", wanted, context=OperationContext(credentials={"wistia_token": "token"}))
    assert result.status == "partial"
    assert any(f["reason"] == "unknown_date" for f in result.coverage["failures"])
    assert "created_after" not in parse_qs(urlsplit(transport.calls[0][0]).query)


def test_legistar_native_body_metadata_search_scopes_fields_and_preserves_keyset_checkpoint():
    class LegistarTransport:
        def __init__(self):
            self.calls = []
        def request(self, url, **kwargs):
            self.calls.append((url, kwargs))
            query = parse_qs(urlsplit(url).query)
            assert "substringof('council',tolower(EventBodyName))" in query["$filter"][0]
            return Response(url, json.dumps([{"EventId": 7, "EventBodyName": "Council", "EventDate": "2026-11-11",
                                             "EventLocation": "Supplied room", "EventComment": "comment"}]).encode())
    transport = LegistarTransport()
    engine = create_engine(provider_transport=transport)
    wanted = {"native": True, "source": {"provider": "legistar", "url": "https://webapi.legistar.com/v1/city",
                                          "options": {"page_size": 1}},
              "query": {"terms": ["Council"], "date_from": "2026-11-01", "date_to": "2026-11-11"},
              "bounds": {"max_pages": 1}}
    result = engine.execute("search", wanted)
    assert result.status == "partial", result.public_dict()
    assert result.data["hits"][0]["record"]["normalized"]["location"] == "Supplied room"
    assert result.data["hits"][0]["matches"][0]["field"] == "normalized.body"
    assert result.coverage["native_fields"] == ["EventBodyName"]
    assert result.coverage["agenda_document_text_searched"] is False
    assert result.coverage["checkpoint"]
    changed = {**wanted, "query": {**wanted["query"], "terms": ["Other"]},
               "bounds": {"max_pages": 1, "checkpoint": result.coverage["checkpoint"]}}
    assert engine.execute("search", changed).status == "failed"
    assert len(transport.calls) == 1
    escaped = {**wanted, "query": {**wanted["query"], "terms": ["O'Council"]}}
    transport.request = lambda url, **kw: Response(url, b"[]")
    empty = engine.execute("search", escaped)
    assert empty.status == "partial"
