"""Captured anonymous JSON stays distinct from privileged/opaque page controls."""

import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.simbli_detail import DETAIL, ITEMS

ROOT = Path(__file__).parent / "fixtures" / "simbli-detail"
SOURCE = {"provider": "simbli", "url": "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36031063&MID=4942"}
FORM = b"""var isUserLoggedIn='False';var did='36031063';var meetingID='4942';var enCuUID='';
var enDID='synthetic-district';var enMeetingID='synthetic-meeting';
var encrTZ='synthetic-timezone';var sToken='synthetic-private-control';"""


class Transport:
    def __init__(self, page=FORM, fail=None):
        self.calls, self.page, self.fail = [], page, fail

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == ("https://simbli.eboardsolutions.com",)
        path = urlsplit(url).path
        if path == "/SB_Meetings/ViewMeeting.aspx":
            return Response(url, self.page, "text/html", set_cookie_headers=("anon=synthetic; Path=/; Secure",))
        assert "anon=synthetic" in kwargs["headers"]["Cookie"]
        query = parse_qs(urlsplit(url).query)
        assert query["endid"] == ["synthetic-district"]
        file = {"/Services/api/GetMeeting/": "meeting.json",
                "/Services/api/MeetingView/GetItemsTreeDTO/": "items.json",
                "/Services/api/GetSupportingDocuments/": "supporting.json"}.get(path)
        content = (ROOT / file).read_bytes() if file else b"null"
        return Response(url, content, "application/json", 403 if path == self.fail else 200)


def test_registered_detail_and_agenda_raw_parent_identity_and_private_controls():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and not result.errors, result.public_dict()
    records = result.data["records"]
    assert len(records) > 12
    assert records[0]["identity"]["external_id"] == "4942"
    assert records[0]["normalized"]["meeting_date"] == "2026-11-10"
    assert records[0]["normalized"]["time_zone_status"] == "unknown"
    items = [r for r in records if r["identity"]["record_type"] == "agenda_item"]
    assert all(r["identity"]["parent"]["external_id"] == "4942" for r in items)
    assert any(any(rel["relation"] == "parent_agenda_item" for rel in r["relationships"]) for r in items)
    assert all(not r["normalized"]["documents"] for r in items)
    assert base64.b64decode(result.data["bundles"][1]["capture"]["content_base64"]) == (ROOT / "items.json").read_bytes()
    assert "synthetic-private-control" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("format,file", [(DETAIL, "meeting.json"), (ITEMS, "items.json")])
def test_additive_saved_formats_preserve_originals(format, file):
    result = create_engine().execute("normalize", {"source": {**SOURCE, "input_format": format}},
                                     content=(ROOT / file).read_bytes())
    assert result.status == "completed", result.public_dict()
    assert result.data["capture"]["original_values"] == json.loads((ROOT / file).read_bytes())


@pytest.mark.parametrize("page", [FORM.replace(b"'False'", b"'True'"),
                                  FORM.replace(b"'4942'", b"'4943'"),
                                  FORM.replace(b"enCuUID=''", b"enCuUID='user'")])
def test_non_anonymous_or_changed_identity_fails_before_service_reads(page):
    transport = Transport(page)
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "failed" and len(transport.calls) == 1
    assert "synthetic-private-control" not in json.dumps(result.public_dict())


def test_partial_child_failure_limits_scope_and_revocation():
    transport = Transport(fail="/Services/api/MeetingView/GetItemsTreeDTO/")
    result = create_engine(provider_transport=transport).execute("fetch", {"source": SOURCE})
    assert result.status == "partial" and result.errors
    assert len(result.data["records"]) == 1
    limited = create_engine(provider_transport=Transport()).execute("fetch", {
        "source": SOURCE, "bounds": {"max_records": 2, "max_pages": 2}})
    assert len(limited.data["records"]) == 2 and limited.coverage["truncated"]
    assert create_engine(provider_transport=Transport()).execute("fetch", {"source": SOURCE},
        context=OperationContext(allowed_operations=frozenset())).status == "failed"
