"""Supplied page text follows the pinned SDK without requesting generation."""

import base64
import hashlib
import json

import pytest

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_repository_discovery import BASE, context, entry
from test_repository_fetch import ENTRY_URL

PAGES = ENTRY_URL + "/Document/Pages"


class PageTransport:
    def __init__(self):
        self.calls = []
        self.pages = {
            ENTRY_URL: entry(71),
            PAGES: {"value": [{"entryId": 71, "pageId": 901, "pageNumber": 1,
                                "hasText": True, "unknown": [False, None]}],
                    "@odata.nextLink": PAGES + "?$skiptoken=next"},
            PAGES + "?$skiptoken=next": {"value": [{"entryId": 71, "pageId": 902,
                                                     "pageNumber": 2, "hasText": True}]},
            PAGES + "/1/Text": {"text": "Approve the park funding.", "unknown": "preserved"},
            PAGES + "/2/Text": {"text": "Committee received the report."},
        }
        self.statuses = {}

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
        assert kwargs["allowed_origins"] == ("https://api.laserfiche.com",)
        assert kwargs["allow_redirects"] is False and kwargs.get("method", "GET") == "GET"
        return Response(url, json.dumps(self.pages[url]).encode(), "application/json", self.statuses.get(url, 200))


def run(transport, **kwargs):
    return create_engine(provider_transport=transport).fetch_record(
        Source("laserfiche-weblink", BASE), "71", include_text=True, context=kwargs.pop("context", context()), **kwargs)


def test_repository_page_text_captures_citations_search_reopen_and_interchange(tmp_path):
    transport = PageTransport()
    result = run(transport)
    assert result.status == "completed", result.public_dict()
    assert result.coverage["text_complete"] and not result.coverage["text_generation_requested"]
    record = result.data["records"][0]
    assert record["original"] == entry(71)
    assert [s["page"] for s in record["text"]] == [1, 2]
    assert record["text"][0]["provenance"]["page_id"] == 901
    captures = result.data["captures"]
    assert len(captures) == 4
    for capture in captures:
        raw = base64.b64decode(capture["content_base64"])
        assert hashlib.sha256(raw).hexdigest() == capture["sha256"]
        assert json.loads(raw) == capture["original_values"]
    assert "secret-read-token" not in json.dumps(result.public_dict())
    database = tmp_path / "records.sqlite"
    owner = create_engine(storage=SQLiteStorage(database))
    imported = owner.execute("import_bundle", {"result": result.public_dict(), "persist": True})
    assert imported.status == "completed", imported.public_dict()
    assert all(owner.storage.get("captures", capture["sha256"], scope=context().scope) is not None
               for capture in captures)
    repeated = owner.execute("import_bundle", {"result": result.public_dict(), "persist": True})
    assert all(change["outcome"] == "unchanged" for change in repeated.data["changes"])
    reopened = create_engine(storage=SQLiteStorage(database))
    found = reopened.execute("search", {"query": {"phrases": ["park funding"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    hit = found.data["hits"][0]
    assert any(match.get("page") == 1 and match["citation_url"] == PAGES + "/1/Text"
               for match in hit["matches"])
    exported = reopened.execute("export", {"bundle": result.data, "format": "zip"})
    assert exported.status == "completed", exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / "destination.sqlite"))
    restored = destination.execute("import_bundle", {"format": "zip", "persist": True},
                                   content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    for restored_capture, original in zip(restored.data["bundle"]["captures"], captures, strict=True):
        assert {k: v for k, v in restored_capture.items() if k != "storage_reference"} == {
            k: v for k, v in original.items() if k != "content_base64"}
        with destination.storage.open_capture(restored_capture["storage_reference"], scope=context().scope) as stream:
            assert stream.read() == base64.b64decode(original["content_base64"])
    again = destination.execute("search", {"query": {"phrases": ["park funding"]}})
    assert again.data["hits"][0]["identity"] == hit["identity"]
    assert again.data["hits"][0]["matches"] == hit["matches"]
    transport.pages[PAGES + "/1/Text"]["text"] = "Reject the park funding."
    changed = run(transport)
    assert changed.data["records"][0]["identity"] == record["identity"]
    assert changed.data["records"][0]["normalized_sha256"] != record["normalized_sha256"]
    imported_change = owner.execute("import_bundle", {"result": changed.public_dict(), "persist": True})
    assert imported_change.data["changes"][0]["outcome"] == "changed_source"


@pytest.mark.parametrize("failure", ["missing_text", "text_404", "wrong_entry", "bad_page_id", "cycle", "foreign_next", "echo", "bad_text"])
def test_repository_page_text_partial_retains_document_and_coverage(failure):
    transport = PageTransport()
    first = transport.pages[PAGES]["value"][0]
    if failure == "missing_text":
        first["hasText"] = False
    elif failure == "text_404":
        transport.statuses[PAGES + "/1/Text"] = 404
    elif failure == "wrong_entry":
        first["entryId"] = 72
    elif failure == "bad_page_id":
        first["pageId"] = True
    elif failure == "cycle":
        transport.pages[PAGES]["@odata.nextLink"] = PAGES
    elif failure == "foreign_next":
        transport.pages[PAGES]["@odata.nextLink"] = "https://evil.example.org/page"
    elif failure == "echo":
        transport.pages[PAGES + "/1/Text"]["text"] = "secret-read-token"
    elif failure == "bad_text":
        transport.pages[PAGES + "/1/Text"]["text"] = {"not": "text"}
    result = run(transport)
    assert result.status == "partial", result.public_dict()
    assert result.data["records"][0]["identity"]["external_id"] == "71"
    assert not result.coverage["text_complete"] and result.coverage["failures"]
    assert "secret-read-token" not in json.dumps(result.public_dict())
    searched = create_engine().execute("search", {"result": result.public_dict(), "query": {"terms": ["report"]}})
    assert searched.status == "partial" and searched.coverage["incomplete_text"]


def test_repository_page_text_bounds_cancellation_and_opt_in():
    transport = PageTransport()
    limited = run(transport, bounds=Bounds(max_pages=1))
    assert limited.status == "partial" and limited.coverage["truncated"]
    assert limited.coverage["pages"] == 1
    assert not any(url.endswith("/2/Text") for url, _ in transport.calls)
    cancelled = context()
    cancelled.cancellation.set()
    transport = PageTransport()
    assert run(transport, context=cancelled).status == "cancelled"
    assert not transport.calls
    ordinary = create_engine(provider_transport=transport).fetch_record(Source("laserfiche-weblink", BASE), "71")
    # Caller token is still required for metadata reads.
    assert ordinary.status == "failed" and not transport.calls
    ordinary = create_engine(provider_transport=transport).fetch_record(Source("laserfiche-weblink", BASE), "71", context=context())
    assert ordinary.status == "completed" and len(transport.calls) == 1
    assert "page_text_sha256" not in ordinary.data["records"][0]["normalized"]


@pytest.mark.parametrize("value", ["true", 1, None])
def test_repository_page_text_flag_requires_boolean(value):
    transport = PageTransport()
    result = create_engine(provider_transport=transport).fetch(
        Source("laserfiche-weblink", BASE), {"external_id": "71", "include_text": value}, context=context())
    assert result.status == "failed" and not transport.calls


def test_repository_page_text_cumulative_byte_bound_retains_obtained_page():
    transport = PageTransport()
    first_bytes = sum(len(json.dumps(transport.pages[url]).encode()) for url in [PAGES, PAGES + "/1/Text"])
    result = run(transport, bounds=Bounds(transfer_bytes=first_bytes + 1))
    assert result.status == "partial" and not result.coverage["text_complete"]
    assert result.data["records"][0]["text"][0]["page"] == 1
    assert result.coverage["content_fetched"]


@pytest.mark.parametrize("source", [Source("cablecast", "https://reflect.example.org/CablecastPublicSite/"),
                                    Source("legistar", "https://mock-city.legistar.com/Calendar.aspx")])
def test_page_text_option_cannot_be_silently_ignored_by_another_provider(source):
    transport = PageTransport()
    result = create_engine(provider_transport=transport).fetch_record(source, "71", include_text=True)
    assert result.status == "unsupported" and not transport.calls


def test_repository_page_text_http_request_preserves_flag_and_trusted_credentials():
    from starlette.testclient import TestClient
    from civic_data_connectors.transports.http import create_app
    from civic_data_connectors.transports.runtime import Principal, ServiceConfig

    transport = PageTransport()
    token = "synthetic-service-token-for-page-text"
    principal = Principal(credentials={"laserfiche_token": "secret-read-token"})
    config = ServiceConfig(tokens={token: principal})
    with TestClient(create_app(create_engine(provider_transport=transport), config),
                    base_url="http://127.0.0.1") as client:
        response = client.post("/v1/operations/fetch", headers={"Authorization": "Bearer " + token},
            json={"source": Source("laserfiche-weblink", BASE).public_dict(),
                  "external_id": "71", "include_text": True})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed" and result["coverage"]["text_complete"], result
    assert "secret-read-token" not in response.text
