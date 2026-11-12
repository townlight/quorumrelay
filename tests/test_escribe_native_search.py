import base64
from dataclasses import replace
import json
from pathlib import Path
from urllib.parse import parse_qs

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures" / "escribe-native-search"
SOURCE = {"provider": "escribe", "url": "https://pub-oakville.escribemeetings.com/meetingscalendarview.aspx?Expanded=Council"}
LANGUAGES = b'<input class="chkLanguage" value="0,9"><input class="chkLanguage" value="0,12">'


class Transport:
    def __init__(self):
        self.calls, self.changed, self.failure, self.repeat = [], False, False, False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == ("https://pub-oakville.escribemeetings.com",)
        if url == SOURCE["url"]:
            return Response(url, LANGUAGES, "text/html")
        assert url == "https://pub-oakville.escribemeetings.com/GetSearchData.asmx/GetSearchMeetingData?Expanded=Council"
        fields = parse_qs(kwargs["body"].decode(), keep_blank_values=True)
        assert fields["filterByLanguage"] == ["0,9,0,12,"]
        assert fields["filterByDate"] == [""] and fields["includeConflicts"] == ["false"]
        assert fields["includeComments"] == ["false"] and fields["iDisplayLength"] == ["10"]
        start = int(fields["iDisplayStart"][0])
        name = "empty" if fields["searchText"] == ["quorumrelayneverpresentqzxjvk"] else "page-1" if start == 0 else "page-2"
        if self.repeat:
            name = "page-1"
        content = (ROOT / (name + ".json")).read_bytes()
        if self.changed:
            content = content.replace(b"8058", b"8059")
        return Response(url, content, "", 503 if self.failure else 200)


def request(**bounds):
    return {"native": True, "source": SOURCE, "query": {"terms": ["Council"], "limit": 100}, "bounds": bounds}


def test_grouped_source_pages_document_ids_url_derived_items_raw_bytes_and_partial_matching():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("search", request(max_pages=2, max_records=20))
    assert result.status == "partial" and not result.errors, result.public_dict()
    bundles = result.data["bundles"]
    assert len(bundles) == 2 and sum(len(b["records"]) for b in bundles) == 16
    assert result.coverage["duplicate_records_skipped"] == 4
    assert bundles[0]["records"][0]["identity"]["external_id"] == "103599"
    assert base64.b64decode(bundles[0]["capture"]["content_base64"]) == (ROOT / "page-1.json").read_bytes()
    items = [row for bundle in bundles for row in bundle["records"] if row["identity"]["record_type"] == "agenda_item"]
    assert items and all(row["identity"]["derivation"] == "supplied_url" for row in items)
    assert all(row["identity"]["parent"]["external_id"] == row["original"]["parent_meeting_id"] for row in items)
    assert all(row["original"]["group_html"] in json.loads((ROOT / "page-1.json").read_bytes())["aaData"]
               for row in bundles[0]["records"])
    assert result.data["hits"] and result.coverage["full_document_text_searched"] is False
    assert result.coverage["catalog_complete"] is False and result.coverage["checkpoint"]
    assert [parse_qs(kwargs["body"].decode())["iDisplayStart"] for _, kwargs in transport.calls if "body" in kwargs] == [["0"], ["10"]]


def test_midpage_resume_scope_current_grants_query_and_source_changes_fail_closed():
    transport = Transport()
    engine, context = create_engine(provider_transport=transport), OperationContext(principal="alice")
    first = engine.execute("search", request(max_records=1), context=context)
    token = first.coverage["checkpoint"]
    second = engine.execute("search", request(max_records=1, checkpoint=token), context=context)
    assert first.data["bundles"][0]["records"][0]["identity"] != second.data["bundles"][0]["records"][0]["identity"]
    count = len(transport.calls)
    for ctx in [replace(context, principal="bob"), replace(context, allowed_namespaces=frozenset())]:
        assert engine.execute("search", request(checkpoint=token), context=ctx).status == "failed"
        assert len(transport.calls) == count
    changed = request(checkpoint=token)
    changed["query"]["terms"] = ["Budget"]
    assert engine.execute("search", changed, context=context).status == "failed"
    transport.changed = True
    assert engine.execute("search", request(checkpoint=token), context=context).status == "failed"


def test_empty_cancellation_byte_limits_and_failed_page_retry():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    empty = request()
    empty["query"]["terms"] = ["quorumrelayneverpresentqzxjvk"]
    result = engine.execute("search", empty)
    assert result.status == "partial" and result.data["hits"] == [] and not result.coverage["checkpoint"]
    context = OperationContext()
    context.cancellation.set()
    count = len(transport.calls)
    assert engine.execute("search", request(), context=context).status == "cancelled" and len(transport.calls) == count
    assert engine.execute("search", request(parser_bytes=1)).status == "failed"
    transport.failure = True
    failed = engine.execute("search", request())
    assert failed.status == "failed" and failed.coverage["checkpoint"]
    transport.failure = False
    retried = engine.execute("search", request(max_records=1, checkpoint=failed.coverage["checkpoint"]))
    assert retried.status == "partial" and retried.data["bundles"][0]["records"]
    transport.repeat = True
    repeated = engine.execute("search", request(max_pages=2))
    assert repeated.status == "partial" and repeated.errors[0].code == "provider_search_failed"
    assert len(repeated.data["bundles"]) == 1


def test_explicit_local_dates_and_unknown_body_rejected():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    dated = request(max_pages=1)
    dated["query"].update(date_from="2026-11-10", date_to="2026-11-11")
    result = engine.execute("search", dated)
    assert result.status == "partial" and not result.errors
    assert all("2026-11-10" <= hit["record"]["normalized"]["meeting_date"] <= "2026-11-11" for hit in result.data["hits"])
    dated["query"]["body"] = "Unverified body"
    count = len(transport.calls)
    assert engine.execute("search", dated).status == "failed" and len(transport.calls) == count
