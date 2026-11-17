"""Observed client range POST through public fetch; no live account or writes."""
import base64
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import gworks_calendar as calendar
from civic_data_connectors.providers.contracts import Response
from test_gworks_secure_calendar import SOURCE, URL, NS, ROW, content

BOUNDS = Bounds(date_from="2026-11-01", date_to="2026-11-30")


def context():
    return OperationContext(tenant="library-client", allowed_namespaces=frozenset({NS}), credentials={
        "gworks": {"token": "private-calendar-test", "tenant": "library-client", "city_id": "1311",
            "origin": "https://api.gworks.cloud", "allowed_namespaces": [NS]}})


class Server:
    def __init__(self):
        self.content = content()
        self.calls = []
        self.after = lambda: None
        self.status, self.url, self.mime = 200, URL, "application/json"

    def request(self, url, **options):
        assert url == URL and options["method"] == "POST" and not options["allow_redirects"]
        assert options["headers"] == {"Content-Type": "application/json", "Authorization": "Bearer private-calendar-test"}
        assert options["allowed_origins"] == ("https://api.gworks.cloud",)
        self.calls.append(options)
        self.after()
        return Response(self.url, self.content, self.mime, self.status)


def test_exact_native_range_and_response_captures_reopen_search_exports(tmp_path):
    vendor = Server()
    caller = context()
    owner = create_engine(storage=SQLiteStorage(tmp_path / "calendar.sqlite"), provider_transport=vendor)
    result = owner.fetch(SOURCE, bounds=BOUNDS, context=caller)
    assert result.status == "partial" and not result.errors, result.public_dict()
    payload = json.loads(vendor.calls[0]["body"])
    assert payload == {"range": {"cms_meeting.meeting_ts": {
        "f": "2026-11-1 00:00:00", "t": "2026-11-30 23:59:59"}},
        "columns": [{"data": "cms_meeting.id"}, {"data": "cms_meeting.meeting_ts", "orderable": "true"},
            {"data": "cms_meeting.title"}, {"data": "cms_meeting.agenda_published_fl"}],
        "order": [{"column": 1, "dir": "asc"}], "start": 0}
    assert result.data["records"][0]["original"] == ROW
    assert base64.b64decode(result.data["capture"]["content_base64"]) == vendor.content
    assert not result.coverage["catalog_complete"] and result.coverage["pagination"] == "not_established"
    assert "private-calendar-test" not in json.dumps(result.public_dict())
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}, context=caller).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "calendar.sqlite"))
    assert len(reopened.execute("search", {"query": {"terms": ["safety"]}}, context=caller).data["hits"]) == 1
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format}, context=caller)
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("field,value", [("token", ""), ("tenant", "other"), ("city_id", "1117"),
    ("origin", "https://elsewhere.example"), ("allowed_namespaces", []), ("allowed_namespaces", NS)])
def test_trusted_credential_binding_is_required_before_read(field, value):
    vendor, caller = Server(), context()
    caller.credentials["gworks"][field] = value
    result = create_engine(provider_transport=vendor).fetch(SOURCE, bounds=BOUNDS, context=caller)
    assert result.status == "failed" and not vendor.calls


@pytest.mark.parametrize("case", ["http", "mime", "origin", "bytes", "records", "shape", "cancel", "deadline"])
def test_bounded_read_failures_cannot_become_complete_empty_success(case, monkeypatch):
    vendor, caller, bounds = Server(), context(), BOUNDS
    if case == "http":
        vendor.status = 401
    elif case == "mime":
        vendor.mime = "text/html"
    elif case == "origin":
        vendor.url = "https://example.org/"
    elif case == "bytes":
        vendor.content += b" " * 4096
        bounds = replace(bounds, transfer_bytes=4096)
    elif case == "records":
        other = {**ROW, "cms_meeting.id": 5018}
        vendor.content = content([ROW, other])
        bounds = replace(bounds, max_records=1)
    elif case == "shape":
        vendor.content = b'{"data":{}}'
    elif case == "cancel":
        vendor.after = caller.cancellation.set
    else:
        now = [100.0]
        monkeypatch.setattr(calendar, "monotonic", lambda: now[0])
        vendor.after = lambda: now.__setitem__(0, 1000.0)
    result = create_engine(provider_transport=vendor).fetch(SOURCE, bounds=bounds, context=caller)
    assert result.status == ("cancelled" if case == "cancel" else "failed"), result.public_dict()
    assert result.data is None
    if case == "http":
        assert result.errors[0].code == "permission_denied" and result.errors[0].details["http_status"] == 401


def test_local_date_checks_unknown_numeric_time_and_empty_calendar_stay_partial():
    vendor, caller = Server(), context()
    prior, unknown = deepcopy(ROW), deepcopy(ROW)
    prior.update({"cms_meeting.id": 11, "cms_meeting.meeting_ts": "2026-10-31"})
    unknown.update({"cms_meeting.id": 12, "cms_meeting.meeting_ts": 1794268800000})
    vendor.content = content([prior, ROW, unknown])
    owner = create_engine(provider_transport=vendor)
    result = owner.fetch(SOURCE, bounds=BOUNDS, context=caller)
    assert result.status == "partial" and len(result.data["records"]) == 2
    assert result.coverage["filtered_records"] == 1 and result.coverage["unknown_date_records"] == ["12"]
    vendor.content = content([])
    result = owner.fetch(SOURCE, bounds=BOUNDS, context=caller)
    assert result.status == "partial" and not result.data["records"] and not result.coverage["source_complete"]


@pytest.mark.parametrize("case", ["range", "checkpoint", "detail", "related", "namespace"])
def test_unmapped_selectors_denied_without_network(case):
    vendor, caller, request, bounds = Server(), context(), {}, BOUNDS
    if case == "range":
        bounds = Bounds()
    elif case == "checkpoint":
        bounds = replace(bounds, checkpoint="unverified")
    elif case == "detail":
        request["external_id"] = "5017"
    elif case == "related":
        request["related"] = "documents"
    else:
        caller.allowed_namespaces = frozenset()
    result = create_engine(provider_transport=vendor).fetch(SOURCE, request, bounds=bounds, context=caller)
    assert result.status == "failed" and not vendor.calls
