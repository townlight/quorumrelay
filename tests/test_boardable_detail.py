import base64
import json
from dataclasses import replace
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.native import parse_native


ROOT = "https://site.boardable.com/ventura-county-community-college-district/meetings"
SOURCE = Source("boardable", ROOT)
NAMESPACE = "//site.boardable.com/ventura-county-community-college-district"
PAGE = (Path(__file__).parent / "fixtures/boardable-discovery/page-1.json").read_bytes()
ROW = json.loads(PAGE)["data"][0]
ID = str(ROW["id"])
DETAIL = ROOT + "/" + ROW["slug"]


def detail(identity=ROW["id"]):
    # Same reference-table contract as the captured Boardable public detail.
    table = [{"agendaListFormat": 6, "meeting": 1},
             {"slug": 2, "title": 3, "id": 4, "date": 5}, ROW["slug"], ROW["title"],
             identity, "Nov 12, 2026", "numbered"]
    return ('<script id="__NUXT_DATA__">' + json.dumps(table) + '</script>').encode()


class Transport:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or Response(DETAIL, detail(), "text/html")

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url == DETAIL
        assert kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == ("https://site.boardable.com",)
        return self.response


def setup(tmp_path, response=None):
    storage = SQLiteStorage(tmp_path / "scope.db")
    transport = Transport(response)
    engine = create_engine(storage=storage, provider_transport=transport)
    context = OperationContext(principal="reader", client_id="client-a", tenant="tenant-a")
    bundle = parse_native(SOURCE, NAMESPACE, PAGE, "boardable-public-meetings-json")
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=context)
    assert imported.status == "completed", imported.public_dict()
    return engine, storage, transport, context, bundle


def test_known_listing_detail_survives_restart_and_preserves_both_captures_without_new_grants(tmp_path):
    engine, storage, transport, context, bundle = setup(tmp_path)
    engine = create_engine(storage=SQLiteStorage(storage.path), provider_transport=transport)
    context = replace(context, allowed_operations=frozenset({"fetch"}),
                      allowed_namespaces=frozenset({NAMESPACE}))
    result = engine.fetch_record(SOURCE, ID, context=context)
    assert result.status == "partial", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == ID
    assert record["source_url"] == DETAIL
    assert result.data["captures"] == [bundle["capture"]]
    assert base64.b64decode(result.data["capture"]["content_base64"]) == detail()
    assert result.coverage["listing_capture_sha256"] == bundle["capture"]["sha256"]
    assert not result.coverage["document_bytes_verified"]
    denied = engine.execute("normalize", {"source": {**SOURCE.public_dict(),
        "url": DETAIL, "input_format": "boardable-public-meeting-html"}}, content=detail(), context=context)
    assert denied.status == "failed" and len(transport.calls) == 1


@pytest.mark.parametrize("change", ["caller", "namespace", "operation", "missing-capture", "digest", "url"])
def test_known_detail_requires_current_scope_grants_and_exact_capture_binding(tmp_path, change):
    engine, storage, transport, context, bundle = setup(tmp_path)
    source = SOURCE
    if change == "caller":
        context = replace(context, principal="other-reader")
    elif change == "namespace":
        context = replace(context, allowed_namespaces=frozenset({"other"}))
    elif change == "operation":
        context = replace(context, allowed_operations=frozenset({"discover"}))
    elif change == "url":
        source = replace(SOURCE, url=ROOT.removesuffix("/meetings"))
    else:
        capture = dict(bundle["capture"])
        if change == "digest":
            damaged = PAGE[:-1] + (b" " if PAGE[-1:] != b" " else b"\n")
            capture["content_base64"] = base64.b64encode(damaged).decode()
            storage.put("captures", capture["sha256"], capture, scope=context.scope)
        else:
            record = dict(bundle["records"][0], capture_sha256="0" * 64)
            storage.put("records", source_identity_key(record["identity"]), record, scope=context.scope)
    result = engine.fetch_record(source, ID, context=context)
    assert result.status == "failed", result.public_dict()
    assert transport.calls == []


@pytest.mark.parametrize("response", [
    Response(DETAIL, detail(999999), "text/html"),
    Response(DETAIL + "/other", detail(), "text/html"),
    Response(DETAIL, detail(), "application/json"),
    Response(DETAIL, detail(), "text/html", 302),
])
def test_detail_rejects_wrong_native_identity_or_response_contract(tmp_path, response):
    engine, _, transport, context, _ = setup(tmp_path, response)
    result = engine.fetch_record(SOURCE, ID, context=context)
    assert result.status == "failed" and len(transport.calls) == 1
    assert result.errors[0].code == "provider_detail_unavailable"


def test_known_detail_honors_cancellation_and_response_byte_bound(tmp_path):
    engine, _, transport, context, _ = setup(tmp_path)
    context.cancellation.set()
    assert engine.fetch_record(SOURCE, ID, context=context).status == "cancelled"
    assert not transport.calls
    context.cancellation.clear()
    result = engine.fetch_record(SOURCE, ID, context=context, bounds=Bounds(transfer_bytes=1))
    assert result.status == "failed" and transport.calls[0][1]["byte_limit"] == 1
