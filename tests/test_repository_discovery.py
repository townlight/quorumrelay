"""Repository v2 contract tests do not impersonate authenticated live acceptance."""

import base64
import json

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response

BASE = "https://api.laserfiche.com/repository/v2/Repositories/r-city/Entries/54/Folder/Children"
NAMESPACE = "//api.laserfiche.com/repository/v2/Repositories/r-city"


def entry(identity, kind="Document", parent=54):
    return {"@odata.type": "#Laserfiche.Repository." + kind, "id": identity, "name": "Budget " + str(identity),
            "parentId": parent, "entryType": kind, "isContainer": kind == "Folder", "isLeaf": kind != "Folder",
            "creationTime": "2026-11-11T00:00:00Z", "lastModifiedTime": "2026-11-11T01:00:00Z",
            "fields": [{"name": "Date", "values": ["not a meeting date"], "hasMoreValues": True}],
            "unknown": {"keep": [False, None]}}


class RepositoryTransport:
    def __init__(self):
        self.calls = []
        self.pages = {BASE: {"value": [entry(71)], "@odata.count": 2,
                             "@odata.nextLink": BASE + "?$skiptoken=opaque"},
                      BASE + "?$skiptoken=opaque": {"value": [entry(72, "Folder")]}}
        self.status = 200

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(url, json.dumps(self.pages[url]).encode(), "application/json", self.status)


def context(**kwargs):
    return OperationContext(credentials={"laserfiche_token": "secret-read-token"}, **kwargs)


def test_repository_children_paging_checkpoint_raw_identity_and_saved_replay():
    transport = RepositoryTransport()
    engine = create_engine(provider_transport=transport)
    source = Source("laserfiche-weblink", BASE)
    first = engine.discover(source, bounds=Bounds(max_records=1), context=context())
    assert first.status == "partial", first.public_dict()
    assert first.coverage["checkpoint"]
    row = first.data["records"][0]
    assert row["identity"]["namespace"] == NAMESPACE
    assert row["identity"]["parent"] is None  # Stable across moves.
    assert row["relationships"][0]["identity"]["external_id"] == "54"
    assert row["original"] == transport.pages[BASE]["value"][0]
    assert "meeting_date" not in row["normalized"]
    assert row["source_revision"]["value"]["lastModifiedTime"] == "2026-11-11T01:00:00Z"
    assert "secret-read-token" not in json.dumps(first.public_dict())
    url, kwargs = transport.calls[0]
    assert url == BASE
    assert kwargs["headers"]["Prefer"] == "odata.maxpagesize=1"
    assert kwargs["allowed_origins"] == ("https://api.laserfiche.com",)
    second = engine.discover(source, bounds=Bounds(checkpoint=first.coverage["checkpoint"]), context=context())
    assert second.status == "completed", second.public_dict()
    assert second.coverage["collection_complete"] is True
    assert second.coverage["catalog_complete"] is False
    assert second.data["records"][0]["identity"]["record_type"] == "folder"
    raw = base64.b64decode(first.data["bundles"][0]["capture"]["content_base64"])
    replay = engine.normalize(source, raw, input_format="laserfiche-repository-entries-json")
    assert replay.status == "completed"
    assert replay.data["records"][0] == {**row, "captured_at": replay.data["records"][0]["captured_at"]}
    assert engine.discover(source, bounds=Bounds(checkpoint=first.coverage["checkpoint"]),
                           context=context(principal="other")).status == "failed"
    moved = Source("laserfiche-weblink", BASE.replace("/54/", "/55/"))
    value = json.dumps({"value": [entry(71, parent=55)]}).encode()
    assert engine.normalize(moved, value, input_format="laserfiche-repository-entries-json").data["records"][0]["identity"] == row["identity"]


@pytest.mark.parametrize("link", ["https://evil.example/steal", BASE.replace("r-city", "r-other"),
                                BASE.replace("/54/", "/55/"), BASE + "?token=secret", BASE])
def test_repository_untrusted_nextlinks_are_rejected_before_another_request(link):
    transport = RepositoryTransport()
    transport.pages[BASE]["@odata.nextLink"] = link
    result = create_engine(provider_transport=transport).discover(Source("laserfiche-weblink", BASE), context=context())
    assert result.status == "failed", result.public_dict()
    assert len(transport.calls) == 1


def test_repository_access_bounds_malformed_parent_and_saved_no_network():
    transport = RepositoryTransport()
    engine = create_engine(provider_transport=transport)
    source = Source("laserfiche-weblink", BASE)
    assert engine.discover(source).status == "failed"
    assert engine.discover(source, context=context(allowed_namespaces=frozenset())).status == "failed"
    assert engine.discover(Source("laserfiche-weblink", BASE, namespace="r-other"), context=context()).status == "failed"
    assert not transport.calls
    assert engine.discover(source, bounds=Bounds(date_from="2026-11-01"), context=context()).status == "failed"
    assert engine.discover(source, bounds=Bounds(parser_bytes=1), context=context()).status == "failed"
    transport.pages[BASE]["value"][0]["parentId"] = 55
    assert engine.discover(source, context=context()).status == "failed"
    transport.pages[BASE]["value"][0]["parentId"] = 54
    transport.status = 403
    denied = engine.discover(source, context=context())
    assert denied.status == "failed"
    assert denied.errors[0].details["http_status"] == 403
    calls = len(transport.calls)
    saved = engine.fetch(source, {"content_base64": base64.b64encode(json.dumps(transport.pages[BASE]).encode()).decode()})
    assert saved.status == "partial", saved.public_dict()
    assert len(transport.calls) == calls
    cancelled = context()
    cancelled.cancellation.set()
    assert engine.discover(source, context=cancelled).status == "cancelled"


def test_repository_canonical_and_legacy_write_routing_remain_explicit():
    from civic_data_connectors.write_adapters import _laserfiche_repository
    assert _laserfiche_repository(Source("laserfiche-weblink", BASE, namespace=NAMESPACE)) == "r-city"
    assert _laserfiche_repository(Source("laserfiche-weblink", BASE, namespace="r-city")) == "r-city"
    with pytest.raises(ValueError):
        _laserfiche_repository(Source("laserfiche-weblink", BASE, namespace="r-other"))
