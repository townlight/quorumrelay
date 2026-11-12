import base64
import json
from pathlib import Path
from urllib.parse import parse_qs

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = {"provider": "civicplus-agenda-center", "url": "https://www.effinghamcounty.org/AgendaCenter"}
ROOT = b'<a href class="breadCrumb">Agenda Center Archive</a><input id="searchField" value=""><input id="StartDatePicker" value=""><input id="EndDatePicker" value=""><a href="javascript:changeYear(2025, 3, \'a0\')">2025</a>'


class Transport:
    def __init__(self):
        self.calls = []
        self.changed = False
        self.noise = False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        if url == SOURCE["url"]:
            return Response(url, ROOT, "text/html")
        assert url == "https://www.effinghamcounty.org/AgendaCenter/UpdateCategoryList"
        fields = parse_qs(kwargs["body"].decode(), keep_blank_values=True)
        assert fields["year"] == ["2025"] and fields["catID"] == ["3"]
        assert fields["startDate"] == fields["endDate"] == [""]
        name = "agendacenter-search-error.html" if fields["term"] == ["quorumrelayneverpresentqzxjvk"] else "agendacenter-search-commission.html"
        raw = (FIXTURES / name).read_bytes()
        if self.changed:
            raw = raw.replace(b"Commission Meeting", b"Changed Meeting")
        return Response(url, raw + (b"<!--generated DOM state changed-->" if self.noise else b""), "text/html")


def request(term="Commission", **bounds):
    return {"source": SOURCE, "native": True, "query": {"terms": [term]}, "bounds": {
        "date_from": "2025-01-01", "date_to": "2025-12-31", "max_records": 20, **bounds}}


def test_actual_keyword_fragment_has_metadata_hits_and_unknown_body_is_retained():
    req = request()
    req["query"]["body"] = "Commissioners"
    result = create_engine(provider_transport=Transport()).execute("search", req)
    assert result.status == "partial" and not result.errors
    assert result.coverage["body_filter"] == {"requested": "Commissioners", "applied": False, "status": "unknown_retained"}
    assert len(result.data["records"]) == 9
    assert result.coverage["full_document_text_searched"] is False


def test_three_small_resumes_do_not_reject_absolute_offset():
    engine = create_engine(provider_transport=Transport())
    token, ids = None, []
    for _ in range(3):
        result = engine.execute("search", request(max_records=1, **({"checkpoint": token} if token else {})))
        assert result.status == "partial" and not result.errors
        ids.extend(r["identity"]["external_id"] for b in result.data["bundles"] for r in b["records"])
        token = result.coverage["checkpoint"]
    assert len(ids) == len(set(ids)) == 3


def test_observed_200_application_error_is_failed_not_zero_results():
    result = create_engine(provider_transport=Transport()).execute("search", request("quorumrelayneverpresentqzxjvk"))
    assert result.status == "failed" and result.errors
    assert result.data["bundles"][0]["capture"]["content_base64"]
    assert result.coverage["checkpoint"]


def test_forged_public_control_and_other_scope_fail_before_post():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1))
    state = json.loads(base64.urlsafe_b64decode(first.coverage["checkpoint"]))
    state["queue"][0]["fields"]["catID"] = "9999"
    token = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    count = len(transport.calls)
    forged = engine.execute("search", request(max_records=1, checkpoint=token))
    assert forged.status == "failed" and len(transport.calls) == count+1
    count = len(transport.calls)
    foreign = engine.execute("search", request(max_records=1, checkpoint=first.coverage["checkpoint"]),
                             context=OperationContext(principal="other"))
    denied = engine.execute("search", request(), context=OperationContext(allowed_namespaces=frozenset({"unrelated"})))
    assert foreign.status == denied.status == "failed" and len(transport.calls) == count


def test_changed_capture_fails_with_no_silent_row_skip():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1))
    transport.changed = True
    result = engine.execute("search", request(max_records=1, checkpoint=first.coverage["checkpoint"]))
    assert result.status == "failed" and result.errors


def test_unmapped_dom_noise_preserves_rows_and_exact_original_captures():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1))
    transport.noise = True
    resumed = engine.execute("search", request(max_records=1, checkpoint=first.coverage["checkpoint"]))
    assert resumed.status == "partial" and not resumed.errors
    assert first.data["bundles"][0]["capture"]["sha256"] != resumed.data["bundles"][0]["capture"]["sha256"]
