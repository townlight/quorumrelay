import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.discovery import _checkpoint, _resume
from civic_data_connectors.providers.clerkbase_listing import controls
from civic_data_connectors.models import Source

FIXTURES = Path(__file__).parent / "fixtures" / "clerkbase"
HOME = (FIXTURES / "home.html").read_bytes()
TREE = (FIXTURES / "agenda-tree.html").read_bytes()
RESULT = (FIXTURES / "search-council-page1.html").read_bytes()
URL = "https://clerkshq.com/SouthKingstown-ri"
SOURCE = {"provider": "clerkbase", "url": URL}


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if kwargs.get("method", "GET") == "POST":
            assert urlsplit(url).path == "/search"
            return Response(url, RESULT, "text/html")
        if url == URL:
            return Response(url, HOME, "text/html")
        assert url == controls(Source(**SOURCE), HOME)[0]["url"]
        assert kwargs.get("allow_redirects") is False
        return Response(url, TREE, "text/html")


def test_supplied_root_tree_and_scoped_resume_preserve_url_identity():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("discover", {"source": SOURCE, "bounds": {"max_pages": 2, "max_records": 2}})
    assert first.status == "partial" and not first.errors, first.public_dict()
    row = first.data["records"][1]
    assert row["identity"]["derivation"] == "supplied_url"
    assert row["identity"]["external_id"] == row["normalized"]["url"]
    assert row["normalized"]["meeting_date"] == "2026-01-12"
    token = first.coverage["checkpoint"]
    second = engine.execute("discover", {"source": SOURCE, "bounds": {"checkpoint": token, "max_records": 1}})
    assert second.status == "partial" and not second.errors
    assert second.data["records"][0]["identity"] != row["identity"]
    assert not second.coverage["catalog_complete"]
    # A caller-modified URL cannot turn a public tree control into arbitrary GET.
    state = _resume(token, json.loads(base64.urlsafe_b64decode(token))["binding"])
    queue, seen = state
    queue[0]["fields"]["url"] = "https://clerkshq.com/private/staff"
    binding = json.loads(base64.urlsafe_b64decode(token))["binding"]
    bad = _checkpoint(binding, queue[:1], seen)
    before = len(transport.calls)
    failed = engine.execute("discover", {"source": SOURCE, "bounds": {"checkpoint": bad}})
    assert failed.errors and all("/private/" not in u for u, _ in transport.calls[before:])


def test_native_search_and_saved_parsers_are_registered():
    native = create_engine(provider_transport=Transport()).execute("search", {
        "native": True, "source": SOURCE, "query": {"terms": ["Council"]},
        "bounds": {"max_pages": 1}})
    assert native.status == "partial" and not native.errors, native.public_dict()
    assert len(native.data["bundle"]["records"]) == 20
    for content, fmt, count in ((TREE, "clerkbase-public-tree-html", 5),
                                (RESULT, "clerkbase-search-html", 20)):
        saved = create_engine().execute("normalize", {
            "source": {**SOURCE, "input_format": fmt}}, content=content)
        assert saved.status == "completed", saved.public_dict()
        assert len(saved.data["records"]) == count
        assert all(r["identity"]["derivation"] == "supplied_url" for r in saved.data["records"])
    assert parse_qs(urlsplit(controls(Source(**SOURCE), HOME)[0]["url"]).query)["path"] == ["SouthKingstown_Docket,"]


def test_tree_error_and_parser_bound_remain_failed_not_empty():
    class Broken(Transport):
        def request(self, url, **kwargs):
            if url != URL:
                return Response(url, b'<html>Application error</html>', 'text/html')
            return super().request(url, **kwargs)
    result = create_engine(provider_transport=Broken()).execute('discover', {
        'source': SOURCE, 'bounds': {'max_pages': 2}})
    assert result.status == 'partial' and result.errors
    assert result.coverage['failed_pages'] and result.coverage['checkpoint']
    limited = create_engine(provider_transport=Transport()).execute('discover', {
        'source': SOURCE, 'bounds': {'parser_bytes': 100}})
    assert limited.status == 'failed' and limited.errors
