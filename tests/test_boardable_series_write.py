"""Synthetic Boardable weekly series through the shared WriteCoordinator."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import time
from zoneinfo import ZoneInfo

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import AmbiguousWrite, WriteChange, WriteFailure, default_adapters
from civic_data_connectors.providers.boardable_series_write import BoardableSeriesWriteAdapter
from civic_data_connectors.models import Source
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

ORG = "https://app.boardable.com/quorumrelay-evaluation/"
NS = "boardable:46098"
SERIES_ID = 12616
ORIGINAL_ID = 526618
FIRST_DATE = "11/30/2026"
SECOND_DATE = "12/07/2026"
ORIGINAL_URL = ORG + "meetings/c8ab1a-quorumrelay-recurrence-api-fixture"

SOURCE = {"provider": "boardable", "url": ORG, "namespace": NS}
CREATE = {
    "key": "new-series", "entity": "meeting", "operation": "create",
    "fields": {
        "title": "QuorumRelay Recurrence API Fixture",
        "description": "<p>Synthetic private recurrence contract fixture.</p>",
        "location": "QuorumRelay integration evaluation",
        "timezone": "America/New_York",
        "dates": [{"date": FIRST_DATE, "from": "9:00 am", "to": "10:00 am"}],
        "recurrence": {"repeat_period": "week", "weekly_interval": 1, "end_date": SECOND_DATE},
    },
}
UPDATE = {
    "key": "edit-series", "entity": "meeting", "operation": "update", "resource_id": str(ORIGINAL_ID),
    "fields": {"title": "QuorumRelay Recurrence API Fixture Revised"},
}
UPDATE_PUNCT = {
    "key": "edit-series-punct", "entity": "meeting", "operation": "update", "resource_id": str(ORIGINAL_ID),
    "fields": {"title": "QuorumRelay Recurrence API Fixture!"},
}
BOUNDS = SimpleNamespace(max_records=52, parser_bytes=2_000_000, transfer_bytes=2_000_000)


def _repo_root():
    override = os.environ.get("QUORUMRELAY_REPO_ROOT")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs").is_dir():
            return parent
    raise RuntimeError("Repository root containing docs/ is required for pinned Boardable captures.")


def _capture(name):
    path = _repo_root() / "docs" / "capabilities" / "evidence" / "boardable-series-form" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _clock(value):
    match = re.fullmatch(r"([1-9]|1[0-2]):([0-5][0-9]) ([ap]m)", value, re.I)
    assert match
    hour, minute = int(match.group(1)), int(match.group(2))
    if match.group(3).lower() == "pm" and hour != 12:
        hour += 12
    if match.group(3).lower() == "am" and hour == 12:
        hour = 0
    return hour, minute


def _utc(date_text, start_text, end_text, timezone_name):
    day = datetime.strptime(date_text, "%m/%d/%Y")
    fh, fm = _clock(start_text)
    th, tm = _clock(end_text)
    tz = ZoneInfo(timezone_name)
    start = datetime(day.year, day.month, day.day, fh, fm, tzinfo=tz).astimezone(timezone.utc)
    end = datetime(day.year, day.month, day.day, th, tm, tzinfo=tz).astimezone(timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%M:%S.000000Z"), end.strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def _week_dates(initial, ending):
    day = datetime.strptime(initial, "%m/%d/%Y")
    end = datetime.strptime(ending, "%m/%d/%Y")
    result = []
    while day <= end:
        result.append(day.strftime("%m/%d/%Y"))
        day += timedelta(days=7)
    return result


def _slug(identity, title):
    clean = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "meeting"
    return f"{identity:x}-{clean}"


def _recurrence(start_text):
    return datetime.fromisoformat(start_text.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")


def _summary(occurrence, series_id):
    return {
        "id": occurrence["id"],
        "url": occurrence["url"],
        "start": occurrence["start"],
        "end": occurrence["end"],
        "series_id": series_id,
        "slug": occurrence["url"].rsplit("/", 1)[-1],
    }


class Vendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.fault = None
        self.series_id = SERIES_ID
        self.original_id = ORIGINAL_ID
        self.title = CREATE["fields"]["title"]
        self.description = CREATE["fields"]["description"]
        self.location = CREATE["fields"]["location"]
        self.timezone = CREATE["fields"]["timezone"]
        self.series_from = CREATE["fields"]["dates"][0]["from"]
        self.series_to = CREATE["fields"]["dates"][0]["to"]
        self.series_date = FIRST_DATE
        self.series_ends = SECOND_DATE
        self.occurrences = {}
        self._install_occurrences([FIRST_DATE, SECOND_DATE])

    def _install_occurrences(self, dates):
        self.occurrences = {}
        base = self.original_id
        for index, date_text in enumerate(dates):
            identity = base + index
            start, end = _utc(date_text, self.series_from, self.series_to, self.timezone)
            self.occurrences[identity] = {
                "id": identity,
                "date": date_text,
                "start": start,
                "end": end,
                "url": ORG + "meetings/" + _slug(identity, self.title),
            }
        self.original_id = base

    def _refresh_urls(self):
        for occurrence in self.occurrences.values():
            occurrence["url"] = ORG + "meetings/" + _slug(occurrence["id"], self.title)

    def _series_data(self):
        return {
            "dates": [{"date": self.series_date, "from": self.series_from, "to": self.series_to}],
            "description": self.description,
            "disable_remote_rsvp": False,
            "enable_ai_summary": False,
            "enable_recording": False,
            "enable_transcription": False,
            "group_ids": [],
            "guests": [],
            "invitee_ids": [403839],
            "location": self.location,
            "meeting_type": "series",
            "minutes_type": "free_form",
            "monthly_interval": "1",
            "monthly_repeat_type": "numbered-day",
            "notify": False,
            "owner_id": 403839,
            "public_member_dashboard": False,
            "public_page": False,
            "remote_option": "no_remote",
            "remote_url": None,
            "remote_url_description": None,
            "repeat_period": "week",
            "series_date": self.series_date,
            "series_ends": self.series_ends,
            "series_from": self.series_from,
            "series_to": self.series_to,
            "timezone": self.timezone,
            "title": self.title,
            "weekly_interval": "1",
        }

    def _meeting(self, identity):
        occurrence = self.occurrences[identity]
        occ_title = occurrence.get("title", self.title)
        leader = 999 if self.fault == "bad_leader" else self.original_id
        series = {
            "create_in_progress": self.fault == "async_generation",
            "publish_in_progress": False,
            "id": self.series_id,
            "organization_id": 46098,
            "original_meeting_id": self.original_id,
            "meeting_invite_leader_id": leader,
            "title": self.title,
            "description": self.description,
            "data": self._series_data(),
            "organization": {"id": 46098, "name": "QuorumRelay Evaluation"},
            "uuid": {"uuid": "server-computed"},
        }
        org = 46099 if self.fault == "wrong_org" and identity != self.original_id else 46098
        ordered = sorted(self.occurrences.values(), key=lambda item: item["start"])
        position = next(i for i, item in enumerate(ordered) if item["id"] == identity)
        previous = None
        if position:
            prior = ordered[position - 1]
            previous = {
                "id": prior["id"], "organization_id": 46098, "series_id": self.series_id,
                "title": self.title, "url": prior["url"],
            }
        members = [{
            "id": 403839,
            "pivot": {
                "meeting_id": identity, "user_id": 403839, "rsvp": "",
                "attendance": "", "collaborator": 0, "is_voter": 1,
                "token": "secret-token",
            },
            "email": "secret@example.test",
            "profile": {"email": "secret@example.test", "account_setup_link": "https://secret"},
        }]
        if self.fault == "extra_member" and identity != self.original_id:
            members.append({"id": 999, "pivot": {"meeting_id": identity, "user_id": 999}})
        return {
            "id": identity,
            "organization_id": org,
            "owner_id": 403839,
            "title": occ_title,
            "description": self.description,
            "location": self.location,
            "start": occurrence["start"],
            "end": occurrence["end"],
            "timezone": self.timezone,
            "datesTimezone": [{
                "date": occurrence["date"], "from": self.series_from, "to": self.series_to,
                "id": identity, "timezone": self.timezone,
            }],
            "slug": occurrence["url"].rsplit("/", 1)[-1],
            "url": occurrence["url"],
            "series_id": self.series_id,
            "series": series,
            "previous_meeting": previous,
            "recurrence_id": _recurrence(occurrence["start"]),
            "remote_option": "no_remote",
            "remote_url": None,
            "remote_url_description": None,
            "disable_remote_rsvp": 0,
            "minutes_type": "free_form",
            "public_member_dashboard": 0,
            "public_page": 0,
            "published": False,
            "published_level": 0,
            "published_at": None,
            "minutes_published": 0,
            "materials_published_status": None,
            "published_materials_status": None,
            "agenda_live_version": None,
            "agenda_draft_version": None,
            "agenda_last_published_at": None,
            "enable_recording": 0,
            "enable_transcription": 0,
            "enable_ai_summary": 0,
            "alternative_dates": None,
            "additional_dates": [],
            "video_conference_enabled": False,
            "starred_public_page": 0,
            "notify": [403839],
            "group_id": None,
            "group": None,
            "groups": [],
            "guests": [],
            "guest_members": [],
            "members": members,
            "custom_business": {"state": "keep", "meeting_id": identity},
            "created_at": "2026-11-16T22:44:08.000000Z",
            "updated_at": "2026-11-16T22:44:08.000000Z",
            "formattedMeetingTime": {"datetime": "display only"},
            "timeUntilStart": "display only",
            "meetingHasStarted": False,
            "name": occ_title,
            "blurb": self.description,
        }

    def _collection(self):
        rows = [_summary(self.occurrences[key], self.series_id) for key in sorted(self.occurrences)]
        if self.fault == "duplicate_bucket":
            rows = [rows[0], deepcopy(rows[0]), rows[1]]
        if self.fault == "conflict_bucket":
            rows = deepcopy(rows)
            rows[0]["url"] = ORG + "meetings/conflicting-copy"
        if self.fault == "missing_occurrence":
            rows = rows[:1]
        if self.fault == "extra_occurrence":
            extra = {
                "id": 526620, "date": "12/14/2026",
                "start": "2026-12-14T14:00:00.000000Z", "end": "2026-12-14T15:00:00.000000Z",
                "url": ORG + "meetings/" + _slug(526620, self.title),
            }
            self.occurrences[526620] = extra
            rows.append(_summary(extra, self.series_id))
        if self.fault == "foreign_series" and len(rows) > 1:
            rows[1]["series_id"] = 9999
        return {
            "can": {"view-unpublished": True},
            "meeting": _summary(self.occurrences[self.original_id], self.series_id),
            "past": [], "today": [], "future": rows,
            "unpublished": deepcopy(rows),
        }

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert headers["Cookie"] == "boardable_session=secret-session"
        assert headers["X-XSRF-TOKEN"] == "secret-csrf"
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert "Authorization" not in headers
        self.calls.append((method, url, body))
        if method == "GET":
            exact = url[:-len("?format=json")] if url.endswith("?format=json") else None
            for identity, occurrence in self.occurrences.items():
                if exact == occurrence["url"]:
                    return WriteResponse(200, json.dumps({"meeting": self._meeting(identity)}).encode())
            return WriteResponse(404, b'{"error":"not found"}')
        if url == ORG + "meetings":
            data = json.loads(body)
            self.series_id = 12620
            self.original_id = 526700
            self.title = data["title"]
            self.description = data["description"]
            self.location = data["location"]
            self.timezone = data["timezone"]
            self.series_date = data["series_date"]
            self.series_ends = data["series_ends"]
            self.series_from = data["series_from"]
            self.series_to = data["series_to"]
            self._install_occurrences(_week_dates(self.series_date, self.series_ends))
            return WriteResponse(201, json.dumps(self._meeting(self.original_id)).encode())
        if url.startswith(ORG + "meeting-series/"):
            assert body == b"{}"
            return WriteResponse(200, json.dumps(self._collection()).encode())
        assert url == ORG + "meetings_v2/" + str(self.original_id)
        data = json.loads(body)
        if self.fault != "ignore_update":
            self.title = data["title"]
            self.description = data["description"]
            self.location = data["location"]
            if self.fault != "preserve_urls":
                self._refresh_urls()
            if self.fault == "corrupt_child_after_update" and 526619 in self.occurrences:
                self.occurrences[526619]["title"] = "Corrupted Child"
        if self.fault == "timeout_after_update":
            raise TimeoutError()
        return WriteResponse(200, json.dumps(self._meeting(self.original_id)).encode())


class PinnedVendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.mode = "before"
        self.create = _capture("boardable-recurrence-api-create.json")
        self.before = _capture("boardable-recurrence-api-readback.json")
        self.update = _capture("boardable-recurrence-api-update.json")
        self.after = _capture("boardable-recurrence-api-updated-readback.json")

    def _source(self):
        return self.after if self.mode == "after_update" else self.before

    def _meeting_by_url(self, url):
        for row in self._source()["occurrences"]:
            if row["url"] == url:
                return row["data"]["meeting"]
        return None

    def _collection(self):
        return self._source()["collection"]["data"]

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert headers["Cookie"] == "boardable_session=secret-session"
        assert headers["X-XSRF-TOKEN"] == "secret-csrf"
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert "Authorization" not in headers
        self.calls.append((method, url, body))
        if method == "GET":
            exact = url[:-len("?format=json")] if url.endswith("?format=json") else None
            meeting = self._meeting_by_url(exact)
            if meeting is None:
                return WriteResponse(404, b'{"error":"not found"}')
            return WriteResponse(200, json.dumps({"meeting": meeting}).encode())
        if url == ORG + "meetings":
            assert json.loads(body) == self.create["request"]["body"]
            return WriteResponse(201, json.dumps(self.create["response"]["data"]).encode())
        if url.startswith(ORG + "meeting-series/"):
            assert body == b"{}"
            return WriteResponse(200, json.dumps(self._collection()).encode())
        if url == ORG + "meetings_v2/" + str(ORIGINAL_ID):
            data = json.loads(body)
            assert data["series_choice"] == "subsequent"
            assert data["assignable_class"] == "App\\Boardable\\Meetings\\Meeting"
            self.mode = "after_update"
            return WriteResponse(200, json.dumps(self.update["response"]["data"]).encode())
        return WriteResponse(404, b'{"error":"not found"}')


def setup_pinned(tmp_path):
    vendor = PinnedVendor()
    context = OperationContext(
        principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({NS}),
        credentials={"boardable": {
            "current_meeting_form": True,
            "current_meeting_series": True,
            "tenant": "city",
            "org_url": ORG,
            "organization_id": 46098,
            "allowed_namespaces": [NS],
            "session_cookie": "boardable_session=secret-session",
            "xsrf_token": "secret-csrf",
            "owner_id": 403839,
            "permissions": ["meeting:create", "meeting:update"],
            "meeting_ids": [str(ORIGINAL_ID)],
            "meeting_urls": {str(ORIGINAL_ID): ORIGINAL_URL},
            "series_ids": [SERIES_ID],
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(
        principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({NS}),
        credentials={"boardable": {
            "current_meeting_form": True,
            "current_meeting_series": True,
            "tenant": "city",
            "org_url": ORG,
            "organization_id": 46098,
            "allowed_namespaces": [NS],
            "session_cookie": "boardable_session=secret-session",
            "xsrf_token": "secret-csrf",
            "owner_id": 403839,
            "permissions": ["meeting:create", "meeting:update"],
            "meeting_ids": [str(ORIGINAL_ID)],
            "meeting_urls": {str(ORIGINAL_ID): vendor.occurrences[ORIGINAL_ID]["url"]},
            "series_ids": [SERIES_ID],
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def plan(engine, context, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


def test_create_weekly_series_minimal_body_and_complete_readback(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    assert vendor.calls == []
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == "526700"
    assert item["series_id"] == "12620"
    assert item["occurrence_ids"] == [526700, 526701]
    assert len(item["occurrence_urls"]) == 2
    post = next(call for call in vendor.calls if call[0] == "POST" and call[1] == ORG + "meetings")
    body = json.loads(post[2])
    assert set(body) == {
        "title", "description", "owner_id", "timezone", "dates", "meeting_type", "minutes_type",
        "location", "remote_option", "remote_url", "remote_url_description", "disable_remote_rsvp",
        "invitee_ids", "group_ids", "guests", "notify", "public_member_dashboard", "public_page",
        "enable_recording", "enable_transcription", "enable_ai_summary", "repeat_period",
        "weekly_interval", "monthly_interval", "monthly_repeat_type", "series_date", "series_ends",
        "series_from", "series_to",
    }
    assert body["meeting_type"] == "series"
    assert body["weekly_interval"] == "1"
    assert body["series_date"] == FIRST_DATE and body["series_ends"] == SECOND_DATE
    assert body["dates"] == [{"date": FIRST_DATE, "from": "9:00 am", "to": "10:00 am"}]
    collection = next(call for call in vendor.calls if call[1] == ORG + "meeting-series/12620/data")
    assert collection[0] == "POST" and collection[2] == b"{}"
    public = json.dumps(result.public_dict())
    assert "secret-session" not in public
    assert "secret-token" not in public
    assert "secret@example.test" not in public


def test_update_whole_series_metadata_changes_both_urls_and_preserves_state(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute("commit_write", plan(engine, context, UPDATE), context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == str(ORIGINAL_ID)
    assert item["series_id"] == str(SERIES_ID)
    assert item["occurrence_ids"] == [526618, 526619]
    assert all("revised" in url for url in item["occurrence_urls"])
    occurrences = item["readback"]["occurrences"]
    assert [row["title"] for row in occurrences] == [UPDATE["fields"]["title"], UPDATE["fields"]["title"]]
    assert [row["datesTimezone"][0]["date"] for row in occurrences] == [FIRST_DATE, SECOND_DATE]
    assert [row["start"] for row in occurrences] == [
        "2026-11-30T14:00:00Z", "2026-12-07T14:00:00Z",
    ]
    post = next(call for call in vendor.calls if call[0] == "POST" and call[1] == ORG + "meetings_v2/526618")
    body = json.loads(post[2])
    assert "meeting_type" not in body
    assert body["series_choice"] == "subsequent"
    assert body["assignable_class"] == "App\\Boardable\\Meetings\\Meeting"
    assert body["assignable_id"] == ORIGINAL_ID
    assert body["dates"][0]["id"] == ORIGINAL_ID
    assert body["title"] == UPDATE["fields"]["title"]


def test_child_change_after_plan_is_conflict_without_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    vendor.occurrences[526619]["url"] = ORG + "meetings/changed-child"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


def test_expected_version_and_foreign_series_are_rejected_before_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [{**UPDATE, "expected_version": "wrong"}]}, context=context,
    )
    assert result.status == "failed"
    vendor.fault = "foreign_series"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
    assert result.status == "failed"
    assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


@pytest.mark.parametrize("fault", ["duplicate_bucket", "conflict_bucket", "missing_occurrence", "extra_occurrence"])
def test_collection_bucket_and_occurrence_integrity_fail_closed(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = fault
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
    assert result.status == "failed"
    assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


def test_bad_original_leader_and_wrong_org_are_rejected(tmp_path):
    for fault in ("bad_leader", "wrong_org"):
        engine, context, vendor = setup(tmp_path / fault)
        vendor.fault = fault
        result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
        assert result.status == "failed"
        assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


def test_async_generation_create_is_uncertain_and_not_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    vendor.fault = "async_generation"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "succeeded"
    assert sum(call[1] == ORG + "meetings" for call in vendor.calls) == 1


@pytest.mark.parametrize("publication", ["materials_published_at", "series_data_published"])
def test_create_with_unexpected_publication_evidence_is_uncertain_and_not_replayed(tmp_path, publication):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    original_meeting = vendor._meeting

    def meeting_with_publication(identity):
        meeting = original_meeting(identity)
        if publication == "materials_published_at":
            meeting["materials_published_at"] = "2026-11-16T22:44:08.000000Z"
        else:
            meeting["series"]["data"]["published"] = True
        return meeting

    vendor._meeting = meeting_with_publication
    result = engine.execute("commit_write", approval, context=context)
    item = result.data["items"][0]
    assert item["state"] == "uncertain"
    assert sum(call[1] == ORG + "meetings" for call in vendor.calls) == 1
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[1] == ORG + "meetings" for call in vendor.calls) == 1


def test_update_lost_slug_is_uncertain_and_never_reposted(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    vendor.fault = "timeout_after_update"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == str(ORIGINAL_ID)
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls) == 1


@pytest.mark.parametrize("dates,recurrence", [
    ([{"date": "03/01/2026", "from": "2:30 am", "to": "3:30 am"}],
     {"repeat_period": "week", "weekly_interval": 1, "end_date": "03/08/2026"}),
    ([{"date": "10/25/2026", "from": "1:30 am", "to": "2:30 am"}],
     {"repeat_period": "week", "weekly_interval": 1, "end_date": "11/01/2026"}),
    ([{"date": "01/04/2026", "from": "9:00 am", "to": "10:00 am"}],
     {"repeat_period": "week", "weekly_interval": 1, "end_date": "01/10/2027"}),
])
def test_dst_span_and_count_bounds_are_rejected(tmp_path, dates, recurrence):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CREATE)
    change["fields"]["dates"] = dates
    change["fields"]["recurrence"] = recurrence
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("series_ids", [[True], [12616.0], ["not-a-series"], []])
def test_unsafe_series_grants_are_denied(tmp_path, series_ids):
    engine, context, vendor = setup(tmp_path)
    context.credentials["boardable"]["series_ids"] = series_ids
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
    assert result.status == "failed"
    assert not vendor.calls


def test_series_flag_without_meeting_form_is_denied(tmp_path):
    engine, context, vendor = setup(tmp_path)
    context.credentials["boardable"].pop("current_meeting_form")
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CREATE]}, context=context)
    assert result.status == "failed"
    assert not vendor.calls


def test_year_boundary_occurrences_sort_by_utc_start_not_text_date(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CREATE)
    change["key"] = "year-boundary-series"
    change["fields"]["dates"] = [{"date": "12/28/2026", "from": "9:00 am", "to": "10:00 am"}]
    change["fields"]["recurrence"] = {"repeat_period": "week", "weekly_interval": 1, "end_date": "01/04/2027"}
    result = engine.execute("commit_write", plan(engine, context, change), context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["occurrence_ids"] == [526700, 526701]
    occurrences = item["readback"]["occurrences"]
    assert [row["datesTimezone"][0]["date"] for row in occurrences] == ["12/28/2026", "01/04/2027"]
    assert [row["start"] for row in occurrences] == ["2026-12-28T14:00:00Z", "2027-01-04T14:00:00Z"]


def test_narrowed_series_grant_before_commit_denies_without_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    context.credentials["boardable"]["series_ids"] = [999]
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "failed"
    assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


def test_punctuation_only_title_update_does_not_require_url_changes(tmp_path):
    engine, context, vendor = setup(tmp_path)
    before_urls = [vendor.occurrences[526618]["url"], vendor.occurrences[526619]["url"]]
    approval = plan(engine, context, UPDATE_PUNCT)
    vendor.fault = "preserve_urls"
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["state"] == "succeeded"
    assert item["occurrence_urls"] == before_urls
    assert [row["title"] for row in item["readback"]["occurrences"]] == [UPDATE_PUNCT["fields"]["title"], UPDATE_PUNCT["fields"]["title"]]


def test_unexpected_child_member_prevents_update(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = "extra_member"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
    assert result.status == "failed"
    assert not any(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls)


def test_corrupt_child_after_update_is_uncertain_and_not_reposted(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    vendor.fault = "corrupt_child_after_update"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == str(ORIGINAL_ID)
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[1] == ORG + "meetings_v2/526618" for call in vendor.calls) == 1


def test_previous_meeting_relationship_is_normalized_to_native_identity(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    occurrences = result.data["items"][0]["readback"]["occurrences"]
    assert occurrences[0]["previous_meeting"] is None
    assert occurrences[1]["previous_meeting"] == {
        "id": 526618, "organization_id": 46098, "series_id": SERIES_ID,
    }


def test_pinned_capture_replay_create_through_engine_sqlite(tmp_path):
    engine, context, vendor = setup_pinned(tmp_path)
    approval = plan(engine, context, CREATE)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["state"] == "succeeded"
    assert item["resource_id"] == "526618"
    assert item["series_id"] == "12616"
    assert item["occurrence_ids"] == [526618, 526619]


def test_pinned_capture_replay_update_through_engine_sqlite(tmp_path):
    engine, context, vendor = setup_pinned(tmp_path)
    approval = plan(engine, context, UPDATE)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["state"] == "succeeded"
    assert item["occurrence_ids"] == [526618, 526619]
    assert all("revised" in url for url in item["occurrence_urls"])
    assert [row["title"] for row in item["readback"]["occurrences"]] == [UPDATE["fields"]["title"], UPDATE["fields"]["title"]]


def test_apply_rejects_forged_create_url_and_overbounds_without_post(tmp_path):
    engine, context, vendor = setup(tmp_path)
    adapter = BoardableSeriesWriteAdapter(vendor)
    change = WriteChange.from_dict(CREATE)
    deadline = time.monotonic() + 10
    prepared = adapter.prepare(Source.from_dict(SOURCE), change, context, BOUNDS, deadline)
    prepared["native"]["url"] = "https://evil.example/meetings"
    with pytest.raises(WriteFailure):
        adapter.apply(Source.from_dict(SOURCE), prepared, context, BOUNDS, deadline)
    assert not any(call[1] == ORG + "meetings" for call in vendor.calls)
    prepared = adapter.prepare(Source.from_dict(SOURCE), change, context, BOUNDS, deadline)
    prepared["native"]["body"]["description"] = "x" * (BOUNDS.transfer_bytes + 1)
    with pytest.raises((WriteFailure, ValueError)):
        adapter.apply(Source.from_dict(SOURCE), prepared, context, BOUNDS, deadline)
    assert not any(call[1] == ORG + "meetings" for call in vendor.calls)


def test_apply_rejects_current_owner_change_before_create_without_post(tmp_path):
    engine, context, vendor = setup(tmp_path)
    adapter = BoardableSeriesWriteAdapter(vendor)
    change = WriteChange.from_dict(CREATE)
    deadline = time.monotonic() + 10
    prepared = adapter.prepare(Source.from_dict(SOURCE), change, context, BOUNDS, deadline)
    context.credentials["boardable"]["owner_id"] = 999
    with pytest.raises(WriteFailure):
        adapter.apply(Source.from_dict(SOURCE), prepared, context, BOUNDS, deadline)
    assert not any(call[1] == ORG + "meetings" for call in vendor.calls)


def test_cancelled_after_native_identity_persisted_recovers_read_only_without_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    adapter = BoardableSeriesWriteAdapter(vendor)
    change = WriteChange.from_dict(CREATE)
    deadline = time.monotonic() + 10
    prepared = adapter.prepare(Source.from_dict(SOURCE), change, context, BOUNDS, deadline)
    persisted = []

    def persist(item):
        persisted.append(deepcopy(item))
        return len(persisted) == 2

    with pytest.raises(AmbiguousWrite):
        adapter.apply(Source.from_dict(SOURCE), prepared, context, BOUNDS, deadline, persist=persist)
    assert persisted[1]["resource_id"] == "526700"
    assert persisted[1]["series_id"] == "12620"
    recovered = BoardableSeriesWriteAdapter(vendor).reconcile(
        Source.from_dict(SOURCE), prepared, persisted[1], context, BOUNDS, time.monotonic() + 10,
    )
    assert recovered["state"] == "succeeded"
    assert sum(call[1] == ORG + "meetings" for call in vendor.calls) == 1
