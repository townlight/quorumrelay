"""Observed public rows and synthetic private controls; no account session."""
import base64
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.simbli import HOST, LIST, PAGER, _cache, _listing

ROOT = Path(__file__).parent / "fixtures" / "simbli-discovery"
FIRST, SECOND = (ROOT / "listing.html").read_bytes(), (ROOT / "page-2.json").read_bytes()
SOURCE = Source("simbli", HOST + "/index.aspx?S=36031063")


class Transport:
    def __init__(self):
        self.calls, self.fail, self.cross, self.auth, self.repeat = [], False, False, False, False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allowed_origins"] == (HOST,)
        assert kwargs["allow_redirects"] is False
        path = urlsplit(url).path
        if path == "/index.aspx":
            raw = b"var currUserId = ''; var sToken = 'synthetic-menu-token'; var encrSiteId = 'synthetic-site'; var sessionId = 'synthetic-session';"
        elif path == "/CoreServices/api/Menu/GetMenu":
            assert parse_qs(urlsplit(url).query)["sct"] == ["synthetic-menu-token"]
            assert kwargs["headers"]["Cookie"] == "public=synthetic-cookie"
            raw = json.dumps({"MenuList": [{"Url": LIST + "?S=36031063"}]}).encode()
        elif path == LIST:
            raw = FIRST
        else:
            assert path == PAGER and kwargs["method"] == "POST"
            body = json.loads(kwargs["body"])
            assert body["RecordCount"] == 50 and body["SchoolID"] == "36031063"
            assert body["IsUserLoggedIn"] is False and body["UserID"] == ""
            assert body["SortColName"] == "DateTime" and body["IsSortDesc"] is True
            assert body["SecurityToken"] == "synthetic-public-control"
            assert kwargs["headers"]["Authorization"] == "Bearer "
            raw = SECOND if body["RecordStart"] == 51 else b"[]"
            if self.repeat:
                raw = json.dumps(_listing(FIRST, "36031063")[0]).encode()
            if self.cross:
                rows = json.loads(raw)
                rows[0]["MM_DistrictID"] = 999
                raw = json.dumps(rows).encode()
        return Response(url, raw, "application/json", 503 if self.fail and path == PAGER else 200,
            set_cookie_headers=(("auth_Token=synthetic-auth; Path=/; Secure",) if self.auth else
                                ("public=synthetic-cookie; Path=/; Secure",)))


def test_actual_two_page_rows_exact_bytes_native_ids_and_anonymous_menu():
    transport = Transport()
    result = create_engine(provider_transport=transport).discover(SOURCE, bounds=Bounds(max_pages=2))
    assert result.status == "partial" and not result.errors, result.public_dict()
    rows = result.data["records"]
    assert len(rows) == len({r["identity"]["external_id"] for r in rows}) == 100
    assert rows[0]["identity"]["external_id"] == "4942"
    assert result.coverage["catalog_complete"] is False and result.coverage["checkpoint"]
    assert result.coverage["requests"] == 4
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == FIRST
    assert base64.b64decode(result.data["captures"][1]["content_base64"]) == SECOND
    assert rows[50]["original"] == json.loads(SECOND)[0]
    assert "synthetic-cookie" not in json.dumps(result.public_dict())
    assert "synthetic-menu-token" not in json.dumps(result.public_dict())


def test_small_record_cursors_retry_scope_expiry_and_current_bounds():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    token, ids = None, []
    for _ in range(100):
        result = engine.discover(SOURCE, bounds=Bounds(max_records=1, checkpoint=token))
        assert not result.errors, result.public_dict()
        ids.extend(r["identity"]["external_id"] for r in result.data["records"])
        token = result.coverage["checkpoint"]
    assert len(ids) == len(set(ids)) == 100 and len(transport.calls) == 4
    resumed = engine.discover(SOURCE, bounds=Bounds(checkpoint=token))
    assert resumed.coverage["listing_exhausted"] and not resumed.data["records"]
    calls = len(transport.calls)
    replay = engine.discover(SOURCE, bounds=Bounds(checkpoint=token))
    assert replay.coverage["listing_exhausted"] and len(transport.calls) == calls + 1
    for context in [OperationContext(principal="other"), OperationContext(allowed_namespaces=())]:
        denied = engine.discover(SOURCE, bounds=Bounds(checkpoint=token), context=context)
        assert denied.status == "failed" and len(transport.calls) == calls + 1
    denied = engine.discover(SOURCE, bounds=Bounds(checkpoint=token, date_from="2026-01-01"))
    assert denied.status == "failed"
    denied = engine.discover(SOURCE, bounds=Bounds(checkpoint=token, parser_bytes=100))
    assert denied.status == "failed"
    _cache(engine).values[token]["expires"] = 0
    assert engine.discover(SOURCE, bounds=Bounds(checkpoint=token)).status == "failed"


def test_failed_page_retries_and_cross_district_repeat_auth_bounds_fail_closed():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.discover(SOURCE, bounds=Bounds(max_pages=1))
    token = first.coverage["checkpoint"]
    transport.fail = True
    failed = engine.discover(SOURCE, bounds=Bounds(checkpoint=token))
    assert failed.status == "failed" and failed.errors[0].details == {"http_status": 503}
    transport.fail = False
    assert len(engine.discover(SOURCE, bounds=Bounds(checkpoint=token, max_pages=1)).data["records"]) == 50
    for key in ["cross", "repeat"]:
        setattr(transport, key, True)
        failed = engine.discover(SOURCE, bounds=Bounds(checkpoint=token))
        assert failed.status == "failed" and not failed.data["records"]
        setattr(transport, key, False)
    transport.auth = True
    denied = create_engine(provider_transport=transport).discover(SOURCE)
    assert denied.status == "failed" and len(denied.data["records"]) == 0
    transport.auth = False
    small = create_engine(provider_transport=transport).discover(SOURCE, bounds=Bounds(parser_bytes=100))
    assert small.status == "failed"
    before = len(transport.calls)
    context = OperationContext()
    context.cancellation.set()
    cancelled = engine.discover(SOURCE, context=context)
    assert cancelled.status == "cancelled" and len(transport.calls) == before


def test_local_date_filter_and_legacy_capture_unchanged():
    source = Source("simbli", HOST + LIST + "?S=36031063")
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(source, bounds=Bounds(max_pages=2, date_from="2026-11-01", date_to="2026-11-30"))
    assert not result.errors and result.coverage["filtered_records"] > 0
    assert all("2026-11-01" <= r["normalized"]["meeting_date"] <= "2026-11-30" for r in result.data["records"])
    calls = len(transport.calls)
    saved = engine.execute("discover", {"source": source.public_dict()}, content=FIRST)
    assert len(transport.calls) == calls and len(saved.data["records"]) == 50
    changed = deepcopy(source.public_dict())
    changed["body"] = "Unverified body"
    assert engine.execute("discover", {"source": changed}).status == "failed" and len(transport.calls) == calls
