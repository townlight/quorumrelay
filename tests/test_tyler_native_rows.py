"""Configured native Tyler reads retain only visible rows and their literal statuses."""

import base64
import json

from civic_data_connectors import Source, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.storage import SQLiteStorage


ORIGIN = "https://libertycountytxapp.meetingmanager.tylerapp.com"
SOURCE_URL = ORIGIN + "/392259prod/tylermm/calendar/"
API_BASE = ORIGIN + "/tylermmcalendar392259prod/"


def _row(identity, title, *, canceled=False, adjourned=False, visibility=1):
    return {
        "id": identity,
        "meetingId": 3007,
        "recurringId": 3027,
        "meetingTitle": title,
        "meetingTypeId": 4,
        "meetingTypeName": "Commissioners Court",
        "startDateTime": "2026-11-11T06:00:00Z",
        "startTime": "07:00 PM",
        "endDateTime": "2026-11-11T06:00:00Z",
        "endTime": "08:00 PM",
        "newMeetingDate": "2026-11-12T06:00:00Z",
        "newMeetingTime": "08:00 PM",
        "isPublicVisibility": visibility,
        "canceled": canceled,
        "adjourned": adjourned,
        "agendaStatus": 5,
        "minutesStatus": 1,
        "videoStatus": "linked",
        "agendaItemTitles": ["1. Budget review", "2. Public comment"],
        "unknownVendorValue": {"kept": True},
    }


ROWS = [
    _row("native-title-cancelled", "Cancelled Shade Tree Commission", canceled=False),
    _row("native-cancel-flag", "Budget Workshop", canceled=True),
    _row("native-adjourned-flag", "Council Meeting", adjourned=True),
    {"isPublicVisibility": 0},  # Private rows are excluded before their other fields are examined.
]


class Transport:
    def __init__(self, calendar=None, search=None, detail=None, *, changed_url=False):
        self.calendar = ROWS if calendar is None else calendar
        self.search = search
        self.detail = detail
        self.changed_url = changed_url
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs.get("allow_redirects") is False
        if url.endswith("/meetingInformation/getMeetingInformationByDate"):
            content = json.dumps(self.calendar).encode()
        elif url.endswith("/meetingCalendarSearch/search"):
            content = json.dumps(self.search or {"searchResults": [], "totalElements": 0}).encode()
        elif url.endswith("/meetingInformation/getMeeting"):
            content = json.dumps(self.detail or {}).encode()
        else:
            raise AssertionError(f"Unexpected Tyler request URL: {url}")
        response_url = url + "/redirected" if self.changed_url else url
        return Response(response_url, content, "application/json")


def _source():
    return Source("tyler-meeting-manager", SOURCE_URL,
                  options={"calendar_api_base": API_BASE, "meeting_type_ids": []})


def _discovery_request():
    return {"source": _source().public_dict(), "bounds": {
        "date_from": "2026-11-01", "date_to": "2026-11-30", "max_pages": 1,
        "max_records": 20}}


def test_native_calendar_keeps_status_title_source_time_and_raw_row():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("discover", _discovery_request())
    assert result.status == "partial", result.public_dict()
    rows = {row["identity"]["external_id"]: row for row in result.data["records"]}
    assert set(rows) == {"native-title-cancelled", "native-cancel-flag", "native-adjourned-flag"}

    title_cancelled = rows["native-title-cancelled"]
    assert title_cancelled["normalized"]["title"] == "Cancelled Shade Tree Commission"
    assert title_cancelled["normalized"]["source_status"]["canceled"] is False
    canceled = rows["native-cancel-flag"]
    assert canceled["normalized"]["source_status"]["canceled"] is True
    adjourned = rows["native-adjourned-flag"]
    assert adjourned["normalized"]["source_status"]["adjourned"] is True
    assert canceled["normalized"]["source_status"]["agendaStatus"] == 5
    assert canceled["normalized"]["source_status"]["minutesStatus"] == 1
    assert canceled["normalized"]["source_status"]["videoStatus"] == "linked"
    assert canceled["normalized"]["meeting_date"] == "2026-11-11"
    assert canceled["normalized"]["source_start"] == "2026-11-11T06:00:00Z"
    assert canceled["normalized"]["source_time"] == "07:00 PM"
    assert canceled["normalized"]["source_new_meeting_date"] == "2026-11-12T06:00:00Z"
    assert canceled["normalized"]["time_zone_status"] == "source_literal_unverified"
    assert canceled["normalized"]["agenda_item_titles"] == ["1. Budget review", "2. Public comment"]
    assert canceled["normalized"]["agenda_items_availability"] == "titles_supplied_without_native_item_ids"
    assert canceled["normalized"]["source_fields"]["isPublicVisibility"] == 1
    assert canceled["original"] == ROWS[1]
    assert canceled["original"]["unknownVendorValue"] == {"kept": True}
    assert len(transport.calls) == 1


def test_visible_malformed_identity_or_date_fails_instead_of_empty_success():
    malformed = [
        [{**_row("", "Meeting"), "id": ""}],
        [{**_row("native-id", "Meeting"), "startDateTime": "not-a-date"}],
    ]
    for rows in malformed:
        result = create_engine(provider_transport=Transport(calendar=rows)).execute(
            "discover", _discovery_request())
        assert result.status == "failed", result.public_dict()
        assert result.errors
        assert result.data["records"] == []


def test_native_calendar_rejects_changed_response_url():
    transport = Transport(changed_url=True)
    result = create_engine(provider_transport=transport).execute("discover", _discovery_request())
    assert result.status == "failed", result.public_dict()
    assert result.errors
    assert result.data["records"] == []
    assert len(transport.calls) == 1


def test_native_search_uses_richer_mapping_and_excludes_private_rows():
    search_rows = [ROWS[0], ROWS[1], ROWS[3]]
    transport = Transport(search={"searchResults": search_rows, "totalElements": len(search_rows)})
    result = create_engine(provider_transport=transport).execute("search", {
        "native": True, "source": _source().public_dict(),
        "query": {"terms": ["Cancelled"], "date_from": "2026-11-01", "date_to": "2026-11-30"},
        "bounds": {"max_pages": 1, "max_records": 10},
    })
    assert result.status == "partial", result.public_dict()
    assert [record["identity"]["external_id"] for record in result.data["bundle"]["records"]] == [
        "native-title-cancelled", "native-cancel-flag"]
    assert len(result.data["hits"]) == 1
    assert result.data["hits"][0]["identity"]["external_id"] == "native-title-cancelled"


def test_native_detail_status_survives_storage_search_and_zip(tmp_path):
    canceled_detail = _row("native-cancel-flag", "Cancelled Budget Workshop", canceled=True)
    transport = Transport(detail=canceled_detail)
    engine = create_engine(storage=SQLiteStorage(tmp_path / "source.sqlite"), provider_transport=transport)
    discovered = engine.execute("discover", _discovery_request())
    canceled_record = next(row for row in discovered.data["records"]
                           if row["identity"]["external_id"] == "native-cancel-flag")
    imported = engine.execute("import_bundle", {"bundle": discovered.data["bundles"][0], "persist": True})
    assert imported.status == "completed", imported.public_dict()
    detail = engine.fetch_record(_source(), canceled_record["identity"]["external_id"])
    assert detail.status == "partial", detail.public_dict()
    record = detail.data["records"][0]
    assert record["normalized"]["title"] == "Cancelled Budget Workshop"
    assert record["normalized"]["source_status"]["canceled"] is True
    assert record["original"] == canceled_detail
    persisted = engine.execute("import_bundle", {"result": detail.public_dict(), "persist": True})
    assert persisted.status == "partial"

    reopened = create_engine(storage=SQLiteStorage(tmp_path / "source.sqlite"))
    matches = reopened.execute("search", {"query": {"phrases": ["Cancelled Budget Workshop"]}})
    assert {hit["identity"]["external_id"] for hit in matches.data["hits"]} == {"native-cancel-flag"}
    assert matches.data["hits"][0]["record"]["normalized"]["source_status"]["canceled"] is True

    exported = reopened.execute("export", {"bundle": detail.data, "format": "zip"})
    restored_engine = create_engine(storage=SQLiteStorage(tmp_path / "restored.sqlite"))
    restored = restored_engine.execute("import_bundle", {"format": "zip", "persist": True},
                                       content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    restored_hit = restored_engine.execute("search", {"query": {"phrases": ["Cancelled Budget Workshop"]}})
    assert restored_hit.data["hits"][0]["identity"]["external_id"] == "native-cancel-flag"
    assert restored_hit.data["hits"][0]["record"]["normalized"]["source_status"]["canceled"] is True


def test_legacy_saved_normalizer_keeps_historical_filter_behavior():
    legacy_rows = [
        {"id": "legacy-1", "meetingTitle": "Council", "startDateTime": "2026-11-11",
         "startTime": "07:00 PM", "isPublicVisibility": 1, "canceled": False, "adjourned": False},
        {"id": "legacy-2", "meetingTitle": "Cancelled Council", "startDateTime": "2026-11-11",
         "startTime": "07:00 PM", "isPublicVisibility": 1, "canceled": True, "adjourned": False},
        {"id": "legacy-3", "meetingTitle": "Adjourned", "startDateTime": "2026-11-11",
         "startTime": "07:00 PM", "isPublicVisibility": 1, "canceled": False, "adjourned": True},
    ]
    result = create_engine().normalize(Source("tyler-meeting-manager", SOURCE_URL),
        json.dumps(legacy_rows).encode(), input_format="tyler-public-calendar-json")
    assert result.status == "completed"
    assert [row["external_id"] for row in result.data["compatibility"]["meetings"]] == ["legacy-1"]
    assert len(result.data["records"]) == 3


def test_native_discovery_resumes_new_rows_and_rejects_legacy_offset_semantics():
    from civic_data_connectors import OperationContext
    from civic_data_connectors.engine import canonical_hash

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    request = _discovery_request()
    request['bounds']['max_records'] = 1
    first = engine.execute('discover', request)
    state = json.loads(base64.urlsafe_b64decode(first.coverage['checkpoint']))
    legacy_binding = canonical_hash({
        'source': _source().public_dict(), 'dates': ['2026-11-01', '2026-11-30'],
        'scope': OperationContext().scope, 'input_format': 'tyler-public-calendar-json',
        'semantics': 'inclusive-source-calendar-date/v1'})
    assert state['binding'] != legacy_binding
    state['binding'] = legacy_binding
    request['bounds']['checkpoint'] = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    calls = len(transport.calls)
    assert engine.execute('discover', request).status == 'failed'
    assert len(transport.calls) == calls
    identities = [first.data['records'][0]['identity']['external_id']]
    result = first
    for _ in range(2):
        request['bounds']['checkpoint'] = result.coverage['checkpoint']
        result = engine.execute('discover', request)
        identities.extend(row['identity']['external_id'] for row in result.data['records'])
    assert set(identities) == {row['id'] for row in ROWS if row['isPublicVisibility'] == 1}
    assert len(identities) == len(set(identities)) == 3
    assert result.coverage['checkpoint'] is None


def test_native_search_rejects_legacy_row_filter_checkpoint_before_request():
    from dataclasses import asdict
    from civic_data_connectors import OperationContext
    from civic_data_connectors.engine import canonical_hash
    from civic_data_connectors.providers.discovery import _checkpoint
    from civic_data_connectors.search import _query

    source = _source()
    query = {'terms': ['Council'], 'date_from': '2026-11-01', 'date_to': '2026-11-30'}
    legacy_binding = canonical_hash({'source': source.public_dict(), 'query': asdict(_query(query)),
        'scope': OperationContext().scope, 'page_size': 1, 'contract': 'tyler-public-search/v1'})
    transport = Transport()
    result = create_engine(provider_transport=transport).execute('search', {
        'native': True, 'source': source.public_dict(), 'query': query,
        'bounds': {'max_records': 1, 'checkpoint': _checkpoint(legacy_binding, [{'page': 2}], set())}})
    assert result.status == 'failed'
    assert not transport.calls
