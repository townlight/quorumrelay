import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.civicplus_search import search_rows

FIXTURE = Path(__file__).parent / "fixtures" / "civicplus-lacey-search-november.json"
SOURCE = {"provider": "civicplus-select", "url": "https://laceywa.portal.civicclerk.com/event/1077/files"}


class Transport:
    def __init__(self):
        self.calls = []
        self.changed = False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        assert urlsplit(url).netloc == "laceywa.api.civicclerk.com"
        query = parse_qs(urlsplit(url).query)
        assert query["startDate"] == ["2026-11-01T00:00:00.000Z"]
        assert "X-Bypass-Recaptcha-Secret" not in kwargs["headers"]
        if query.get("$skip") == ["14"] or query["search"] == ["quorumrelayneverpresentqzxjvk"]:
            raw = b'{"value":[]}'
        else:
            raw = FIXTURE.read_bytes() + (b" " if self.changed else b"")
        return Response(url, raw, "application/json")


def request(term="Council", **bounds):
    return {"source": SOURCE, "native": True, "query": {"terms": [term]}, "bounds": {
        "date_from": "2026-11-01", "date_to": "2026-11-30", "max_records": 100,
        "max_pages": 2, **bounds}}


def test_actual_groups_preserve_parent_native_ids_unknown_values_and_excerpts():
    from quorumrelay import Source
    rows = search_rows(Source.from_dict(SOURCE), FIXTURE.read_bytes())
    assert len([r for r in rows if r[2] == "meeting"]) == 14
    assert rows[0][0]["external_id"] == "1498"  # event.id=4319 is a file ID, not its parent.
    assert rows[0][1]["event"]["score"] == 0.016146826
    assert any(r[2] == "agenda_item" and r[0]["external_id"] == "20708" for r in rows)
    result = create_engine(provider_transport=Transport()).execute("search", request())
    assert result.status == "partial" and not result.errors
    assert result.coverage["query_window_exhausted"] is True
    assert result.coverage["catalog_complete"] is False
    assert result.data["hits"]
    records = [r for b in result.data["bundles"] for r in b["records"]]
    child = next(r for r in records if r["identity"]["record_type"] == "agenda_file")
    assert child["identity"]["parent"]["external_id"] == "1498"
    assert child["normalized"]["excerpt_completeness"] == "provider_returned_excerpts_not_full_text"
    assert "<mark" not in child["normalized"]["search_excerpts"][0]
    assert child["original"]["value"]["fileContent"]


def test_three_small_resumes_keep_absolute_page_position_and_distinct_ids():
    engine = create_engine(provider_transport=Transport())
    ids = []
    token = None
    for _ in range(3):
        result = engine.execute("search", request(max_records=1, **({"checkpoint": token} if token else {})))
        assert result.status == "partial" and not result.errors
        records = [r for b in result.data["bundles"] for r in b["records"]]
        ids.extend((r["identity"]["record_type"], r["identity"]["external_id"]) for r in records)
        token = result.coverage["checkpoint"]
    assert len(ids) == len(set(ids)) == 3


def test_capture_snapshot_namespace_revocation_and_caller_binding():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1))
    transport.changed = True
    count = len(transport.calls)
    changed = engine.execute("search", request(max_records=1, checkpoint=first.coverage["checkpoint"]))
    assert changed.status == "partial" and not changed.errors and len(transport.calls) == count
    assert first.data["bundles"][0]["capture"]["sha256"] == changed.data["bundles"][0]["capture"]["sha256"]
    foreign = engine.execute("search", request(max_records=1, checkpoint=first.coverage["checkpoint"]),
                             context=OperationContext(principal="other"))
    denied = engine.execute("search", request(), context=OperationContext(allowed_namespaces=frozenset({"unrelated"})))
    assert foreign.status == denied.status == "failed" and len(transport.calls) == count
    restarted = create_engine(provider_transport=transport).execute("search",
        request(max_records=1, checkpoint=first.coverage["checkpoint"]))
    assert restarted.status == "failed" and len(transport.calls) == count


def test_snapshot_expiry_and_capacity_never_evict_other_active_cursors():
    from civic_data_connectors.providers.civicplus_search import _sessions
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1))
    sessions = _sessions(engine)
    sessions.max_bytes = 1
    limited = engine.execute("search", request(max_records=2))
    assert any(e.code == "continuation_capacity" for e in limited.errors)
    token = first.coverage["checkpoint"]
    sessions.values[token]["expires"] = 0
    count = len(transport.calls)
    expired = engine.execute("search", request(max_records=1, checkpoint=token))
    assert expired.status == "failed" and len(transport.calls) == count


def test_empty_search_and_byte_ceiling_fail_honestly():
    result = create_engine(provider_transport=Transport()).execute("search", request("quorumrelayneverpresentqzxjvk"))
    assert result.status == "partial" and not result.errors and result.data["records"] == []
    limited = create_engine(provider_transport=Transport()).execute("search", request(parser_bytes=1024))
    assert limited.status == "failed" and limited.errors


def test_saved_search_parser_preserves_related_identity_and_raw_unknown_fields():
    result = create_engine().execute("normalize", {"source": {**SOURCE, "input_format": "civicplus-search-json"}},
                                    content=FIXTURE.read_bytes())
    assert result.status == "completed"
    assert any(r["identity"].get("parent") for r in result.data["records"])
    assert result.data["capture"]["original_values"] == json.loads(FIXTURE.read_bytes())
