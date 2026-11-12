"""WebLink requests checked against independent Louisville/Boulder Chrome captures."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors import providers
from civic_data_connectors.models import Bounds, Source
from civic_data_connectors.providers import laserfiche

SAVED = Path(__file__).parent / "fixtures" / "brief-discovery" / "laserfiche"
LOUISVILLE = "https://laserfiche.louisvilleco.gov"
BOULDER = "https://documents.bouldercolorado.gov"


class Session:
    guarded = True

    def __init__(self, origin):
        self.origin = origin
        self.listings = {int(path.stem.split("-")[1]): json.loads(path.read_text())
                         for path in SAVED.glob("listing-*.json")}
        self.opened = []
        self.posted = []
        self.info = {"data": {"pageCount": 2}}
        self.texts = {1: {"data": {"text": "Council <b>agenda</b>"}},
                      2: {"data": {"text": "Call to order"}}}

    def open_and_catch(self, url, response_path, **kwargs):
        assert url.startswith(self.origin + "/")
        assert kwargs["byte_limit"] > 0 and kwargs["deadline_seconds"] > 0
        self.opened.append((url, response_path, kwargs))
        identity = int(parse_qs(urlsplit(url).query)["id"][0])
        if response_path.endswith(laserfiche.INFO):
            return self.info
        return self.listings[identity]

    def post_json(self, path, data, headers, **kwargs):
        assert path.startswith("/WebLink/")
        assert kwargs["byte_limit"] > 0 and kwargs["deadline_seconds"] > 0
        assert headers == {"X-Lf-Suppress-Login-Redirect": "1"}
        self.posted.append((path, data))
        if path.endswith(laserfiche.TEXT):
            return self.texts[data["pageNum"]]
        return self.listings[(data["folderId"], data["start"])]


def source(origin=LOUISVILLE, folder=8986, repo="Louisville"):
    return {"provider": "laserfiche-weblink", "url":
            f"{origin}/WebLink/Browse.aspx?id={folder}&dbid=0&repo={repo}",
            "body": "Planning Commission"}


def request(source_data=None, **bounds):
    return {"source": source_data or source(),
            "bounds": {"date_from": "2026-01-01", "date_to": "2026-11-11", **bounds}}


def engine(session):
    result = Engine()
    providers.register(result, browser=session)
    return result


def test_louisville_dated_document_fields_from_independent_capture():
    session = Session(LOUISVILLE)
    result = engine(session).execute("discover", request())
    # The independent capture set contains dated year listings but not the
    # sibling video/bylaws/resolution folders. Their failures stay visible.
    assert result.status == "partial", result.public_dict()
    assert {failure["folder"] for failure in result.coverage["failures"]} == {637006, 121033, 396315}
    identities = {r["identity"]["external_id"] for r in result.data["records"]}
    assert "1101058" in identities
    record = next(r for r in result.data["records"] if r["identity"]["external_id"] == "1101058")
    assert record["normalized"]["meeting_date"] == "2026-10-08"
    assert record["normalized"]["documents"][0]["url"] == (
        LOUISVILLE + "/WebLink/ElectronicFile.aspx?docid=1101058&dbid=0&repo=Louisville")
    assert record["original"]["name"] == "Planning Commission Agenda and Packet 2026 10 08"
    assert all("repo=Louisville" in call[0] for call in session.opened)
    assert 1010632 not in [int(parse_qs(urlsplit(call[0]).query)["id"][0])
                           for call in session.opened]


def test_boulder_year_month_meeting_nesting_respects_boundary_dates():
    session = Session(BOULDER)
    result = engine(session).execute("discover", request(source(BOULDER, 47549, "LF8PROD2"),
                                                       date_from="2026-10-01", date_to="2026-10-20"))
    assert result.status == "completed", result.public_dict()
    opened = [int(parse_qs(urlsplit(call[0]).query)["id"][0]) for call in session.opened]
    assert 206380 in opened and 206381 not in opened
    assert 198594 not in opened
    assert {r["normalized"]["meeting_date"] for r in result.data["records"]} == {"2026-10-06"}


def test_folder_pagination_and_resume_no_missing_midpage_entries():
    session = Session(LOUISVILLE)
    session.listings[8986] = {"data": {"name": "2026", "folderId": 8986, "totalEntries": 3,
                                     "results": [
        {"entryId": 1, "type": -2, "isEdoc": True, "name": "Agenda 2026 10 01"},
        {"entryId": 2, "type": -2, "isEdoc": True, "name": "Agenda 2026 10 02"}]}}
    session.listings[(8986, 2)] = {"data": {"folderId": 8986, "totalEntries": 3, "results": [
        {"entryId": 3, "type": -2, "isEdoc": False, "name": "Minutes 2026 10 03"}]}}
    owner = engine(session)
    req = request(max_records=1)
    one = owner.execute("discover", req)
    assert one.status == "partial"
    assert one.data["records"][0]["identity"]["external_id"] == "1"
    req["bounds"]["checkpoint"] = one.coverage["checkpoint"]
    two = owner.execute("discover", req)
    assert two.data["records"][0]["identity"]["external_id"] == "2", two.public_dict()
    req["bounds"]["checkpoint"] = two.coverage["checkpoint"]
    three = owner.execute("discover", req)
    assert three.data["records"][0]["identity"]["external_id"] == "3", three.public_dict()
    assert session.posted[0][1] == {
        "repoName": "Louisville", "folderId": 8986, "getNewListing": True, "start": 2,
        "end": 102, "sortColumn": "", "sortAscending": True}
    assert three.coverage["checkpoint"] is None


def test_session_origin_and_guard_requirements_fail_closed():
    wrong = Session(BOULDER)
    assert engine(wrong).execute("discover", request()).status == "failed"
    unguarded = Session(LOUISVILLE)
    unguarded.guarded = False
    assert engine(unguarded).execute("discover", request()).status == "failed"
    assert wrong.opened == unguarded.opened == []


def test_scanned_provider_text_preserves_pages_and_limit_coverage():
    session = Session(LOUISVILLE)
    session.info = json.loads((SAVED / "info-1066144.json").read_text())
    session.texts[1] = json.loads((SAVED / "text-1066144-1.json").read_text())
    src = Source(**source())
    url = LOUISVILLE + "/WebLink/DocView.aspx?id=1066144&dbid=0&repo=Louisville"
    result = laserfiche.scanned_text(src, url, Bounds(max_pages=2), OperationContext(), session)
    assert result["page_count"] == 31
    assert result["completeness"] == "partial"
    assert len(result["pages"]) == 1 and result["pages"][0]["page"] == 1
    assert "Louisville" in result["text"]
    assert session.posted[0][1] == {"repoName": "Louisville", "documentId": 1066144,
                                  "pageNum": 1, "showAnn": True, "searchUuid": ""}


def test_empty_scanned_text_never_claims_readable_or_cross_repo():
    import pytest
    session = Session(LOUISVILLE)
    session.texts = {1: {"data": {"text": " <br/> "}}, 2: {"data": {"text": ""}}}
    src = Source(**source())
    url = LOUISVILLE + "/WebLink/DocView.aspx?id=1066144&dbid=0&repo=Louisville"
    with pytest.raises(ValueError, match="no readable text"):
        laserfiche.scanned_text(src, url, Bounds(), OperationContext(), session)
    with pytest.raises(ValueError, match="different tenant repository"):
        laserfiche.scanned_text(src, url.replace("repo=Louisville", "repo=Other"),
                               Bounds(), OperationContext(), session)


def test_type_filter_and_cancellation_checkpoint():
    session = Session(LOUISVILLE)
    owner = engine(session)
    req = request()
    req["record_types"] = ["document"]
    result = owner.execute("discover", req)
    assert result.data["records"] == []
    context = OperationContext()
    context.progress = lambda p: context.cancellation.set()
    result = owner.execute("discover", request(), context=context)
    assert result.status == "cancelled" and result.coverage["checkpoint"]
