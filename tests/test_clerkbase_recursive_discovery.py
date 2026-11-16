"""Nested ClerkBase traversal uses only current, parent-declared controls."""
import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.discovery import _checkpoint
from test_clerkbase_listing import SOURCE, TREE, URL

CHILD = (Path(__file__).parent / "fixtures/clerkbase/docket-agenda-child.html").read_bytes()
HOME = b'''<a class="js-doc-view" data-toc-url="/toc/SouthKingstown-ri?path=SouthKingstown_Docket," data-path="SouthKingstown_Docket,"></a>'''
PARENT_PATH = "SouthKingstown_Docket,"
CHILD_PATH = "SouthKingstown_Docket,AGENDA,"


class Network:
    def __init__(self):
        self.calls = []
        self.home, self.parent, self.child = HOME, TREE, CHILD

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == URL:
            content = self.home
        else:
            path = parse_qs(urlsplit(url).query).get("path", [""])[0]
            content = self.parent if path == PARENT_PATH else self.child if path == CHILD_PATH else b"bad"
        return Response(url, content, "text/html")


def discover(engine, bounds):
    return engine.execute("discover", {"source": SOURCE, "bounds": bounds})


def test_nested_captured_nodes_resume_parent_revalidation_and_bounds():
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    assert first.status == "partial" and not first.errors, first.public_dict()
    token = first.coverage["checkpoint"]
    assert token
    before = len(network.calls)
    resumed = discover(engine, {"checkpoint": token, "max_pages": 1})
    assert resumed.status == "partial" and not resumed.errors, resumed.public_dict()
    assert len(network.calls) - before == 3  # root, parent, child
    assert resumed.coverage["network_requests"] == 3
    nodes = resumed.data["records"]
    assert len(nodes) == 17 and all(r["identity"]["record_type"] == "agenda_item" for r in nodes)
    assert all(r["identity"]["derivation"] == "supplied_url" for r in nodes)
    assert nodes[0]["identity"]["external_id"].endswith("#_CPA1")
    assert nodes[0]["identity"].get("parent") is None
    assert base64.b64decode(resumed.data["captures"][0]["content_base64"]) == CHILD


def test_changed_parent_blocks_checkpoint_child_before_child_request():
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    network.parent = TREE.replace(b"SouthKingstown_Docket,AGENDA,", b"SouthKingstown_Docket,REPLACED,")
    before = len(network.calls)
    result = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1})
    assert result.errors
    assert all(CHILD_PATH not in url for url, _ in network.calls[before:])


def test_tampered_checkpoint_cannot_forge_child():
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    state = json.loads(base64.urlsafe_b64decode(first.coverage["checkpoint"]))
    state["queue"][0]["fields"]["url"] = "https://clerkshq.com/toc/SouthKingstown-ri?path=SouthKingstown_Docket,SECRET,"
    token = _checkpoint(state["binding"], state["queue"][:1], set(state["seen"]))
    before = len(network.calls)
    result = discover(engine, {"checkpoint": token, "max_pages": 1})
    assert result.errors and all("SECRET" not in url for url, _ in network.calls[before:])


@pytest.mark.parametrize("replacement", [b"#unknown\" title", b"/council/2025/other.htm#_CPA1\" title"])
def test_node_mismatch_fails_without_false_records(replacement):
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    if replacement.startswith(b"#"):
        network.child = CHILD.replace(b"#_CPA1\" title", replacement, 1)
    else:
        network.child = CHILD.replace(b"/council/2026/jan12_26ag.htm#_CPA1\" title", replacement, 1)
    result = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1})
    assert result.errors and not result.data["records"]


def test_partial_node_page_resume_revalidates_and_preserves_seen():
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    limited = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1, "max_records": 3})
    assert len(limited.data["records"]) == 3 and limited.coverage["checkpoint"]
    resumed = discover(engine, {"checkpoint": limited.coverage["checkpoint"], "max_pages": 1, "max_records": 20})
    assert len(resumed.data["records"]) == 14
    assert not {r["identity"]["external_id"] for r in limited.data["records"]} & {
        r["identity"]["external_id"] for r in resumed.data["records"]}


def test_revalidation_counts_against_transfer_budget():
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    result = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1,
                               "transfer_bytes": len(HOME) + len(TREE)})
    assert result.errors and not result.data["records"]
    assert len(network.calls) == 4  # initial root/parent, then revalidated root/parent only
    assert result.coverage["network_requests"] == 2
    assert result.coverage["transfer_bytes"] == len(HOME) + len(TREE)


def test_cyclic_declared_child_is_not_followed():
    network = Network()
    network.parent += b'<a class="js-doc-view" data-toc-url="/toc/SouthKingstown-ri?path=SouthKingstown_Docket," data-path="SouthKingstown_Docket,"></a>'
    engine = create_engine(provider_transport=network)
    result = discover(engine, {"max_pages": 3})
    assert not result.errors, result.public_dict()
    assert sum(PARENT_PATH == parse_qs(urlsplit(url).query).get("path", [""])[0] for url, _ in network.calls) == 1


def test_cancelled_discovery_makes_no_network_requests():
    from civic_data_connectors.models import OperationContext
    network = Network()
    context = OperationContext()
    context.cancellation.set()
    result = create_engine(provider_transport=network).execute("discover", {"source": SOURCE}, context=context)
    assert result.status == "cancelled" and not network.calls


def test_nested_provenance_survives_storage_reopen_and_zip(tmp_path):
    from civic_data_connectors.interchange import read_bundle
    from civic_data_connectors.storage import SQLiteStorage

    network = Network()
    database = tmp_path / "clerkbase.sqlite"
    engine = create_engine(storage=SQLiteStorage(database), provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    page = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1})
    bundle = page.data["bundles"][0]
    chain = bundle["extensions"]["tree_validation"]["parent_responses"]
    assert [base64.b64decode(x["content_base64"]) for x in chain] == [HOME, TREE]
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert imported.status == "completed", imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(database))
    exported = reopened.execute("export", {"bundle_key": imported.data["bundle_key"], "format": "zip"})
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == bundle


def test_deadline_after_child_response_does_not_publish_nodes(monkeypatch):
    from civic_data_connectors.providers import discovery
    clock = [0.0]
    network = Network()
    engine = create_engine(provider_transport=network)
    first = discover(engine, {"max_pages": 2})
    original = network.request
    def delayed(url, **kwargs):
        response = original(url, **kwargs)
        if CHILD_PATH in url:
            clock[0] = 2.0
        return response
    network.request = delayed
    monkeypatch.setattr(discovery, "monotonic", lambda: clock[0])
    result = discover(engine, {"checkpoint": first.coverage["checkpoint"], "max_pages": 1, "deadline_seconds": 1})
    assert not result.data["records"] and result.coverage["deadline_exceeded"]


def test_failed_sibling_retains_independent_nested_nodes_and_retry():
    network = Network()
    sibling = b'<a class="js-doc-view" data-toc-url="/toc/SouthKingstown-ri?path=SouthKingstown_Docket,FAIL," data-path="SouthKingstown_Docket,FAIL,"></a>'
    network.parent = sibling + TREE
    result = discover(create_engine(provider_transport=network), {"max_pages": 4})
    assert result.status == "partial" and result.errors and result.coverage["checkpoint"]
    assert len([r for r in result.data["records"] if r["identity"]["record_type"] == "agenda_item"]) == 17
    assert len(result.data["captures"]) == 3
