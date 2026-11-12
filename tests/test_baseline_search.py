"""All 34 baseline captures: normalize -> import -> exact metadata search.

Expectations come verbatim from the pinned original-implementation oracle
(search-expectations.json), never from the new parser. Coverage must stay
explicit: metadata and supplied text only, no whole-listing association.
"""

import hashlib
import json
from pathlib import Path

import pytest

from civic_data_connectors import Engine
from civic_data_connectors import imports, search, storage
from civic_data_connectors.storage import SQLiteStorage

MATRIX = Path(__file__).parent / "fixtures" / "baseline"
EXPECTATIONS = json.loads((MATRIX / "search-expectations.json").read_text(encoding="utf-8"))
CASES = EXPECTATIONS["cases"]


def normalize_case(engine, case):
    data = (MATRIX / case["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == case["sha256"]
    result = engine.execute(
        "normalize",
        {"source": {"provider": case["connector"], "url": case["source_url"]},
         "input_format": case["input_format"], "bounds": {"max_records": 10000}},
        content=data,
    )
    assert result.status in {"completed", "partial"}, result.public_dict()
    return result


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["connector"] + "/" + c["input_format"])
def test_baseline_capture_import_metadata_phrase_search(tmp_path, case):
    engine = Engine(storage=SQLiteStorage(tmp_path / "store.sqlite"))
    storage.register(engine)
    imports.register(engine)
    search.register(engine)
    normalized = normalize_case(engine, case)
    bundle = normalized.data
    assert bundle["capture"]["sha256"] == case["sha256"]
    assert len(bundle["records"]) >= 1

    imported = engine.execute("import_bundle", {"result": normalized.public_dict(), "persist": True})
    assert imported.status in {"completed", "partial"}, imported.public_dict()
    assert imported.data["bundle_key"]

    # Exact phrase from the pinned original output title must hit metadata.
    title = case["expected_title"]
    found = engine.execute("search", {"query": {"phrases": [title]}})
    assert found.status in {"completed", "partial"}, found.public_dict()
    hits = found.data["hits"]
    assert hits, f"Original title phrase not found in stored metadata: {title!r}"
    hit_ids = {hit["identity"]["external_id"] for hit in hits}
    assert hit_ids & set(case["expected_external_ids"])
    for hit in hits:
        assert hit["identity"]["namespace"] == case["expected_namespace"]
        assert hit["capture_sha256"] == case["sha256"]
        assert hit["citation_urls"]
        for match in hit["matches"]:
            assert match["field"].startswith(("normalized",)) or match.get("provenance")

    # Provider/namespace restriction selects exactly this capture's source.
    scoped = engine.execute("search", {
        "query": {"phrases": [title], "providers": [case["connector"]],
                  "namespaces": [case["expected_namespace"]]},
        "capture_sha256": [case["sha256"]]})
    assert scoped.data["hits"]
    assert scoped.coverage["searched_sources"]

    # Explicit text coverage: no capture claims full source text search.
    for availability in found.coverage["available_text"]:
        assert availability["full_source_searched"] is False
        assert availability["status"] in {"metadata_only", "supplied_text"}


def test_all_34_baseline_captures_share_one_store_and_provider_filter(tmp_path):
    engine = Engine(storage=SQLiteStorage(tmp_path / "all.sqlite"))
    storage.register(engine)
    imports.register(engine)
    search.register(engine)
    providers = set()
    for case in CASES:
        normalized = normalize_case(engine, case)
        imported = engine.execute("import_bundle", {"result": normalized.public_dict(), "persist": True})
        assert imported.status in {"completed", "partial"}, case["file"]
        providers.add(case["connector"])
    assert len(providers) == 31
    # Every case's first original title is retrievable from the shared store.
    missing = []
    for case in CASES:
        found = engine.execute("search", {"query": {"phrases": [case["expected_title"]],
                                                     "providers": [case["connector"]]}})
        if not found.data["hits"]:
            missing.append(case["connector"] + "/" + case["input_format"])
    assert not missing, f"baseline titles not searchable: {missing}"
    # A provider filter never leaks another provider's records.
    only_legistar = engine.execute("search", {"query": {"providers": ["legistar"], "limit": 1000}})
    assert {hit["identity"]["provider"] for hit in only_legistar.data["hits"]} == {"legistar"}
