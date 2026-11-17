"""Synthetic Boardable native meeting form through the shared WriteCoordinator."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pytest

from quorumrelay import Engine, OperationContext
from civic_data_connectors.providers.boardable_meeting_write import _normalize_meeting, _response_identity, _verify_create
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

ORG = "https://app.boardable.com/quorumrelay-evaluation/"
NS = "boardable:46098"
URL = ORG + "meetings/0e58cf-contract-fixture"


def _capture(name):
    evidence = Path("docs/capabilities/evidence/boardable-meeting-form")
    root = Path(__file__).resolve().parent
    env_root = os.environ.get("BOARDABLE_EVIDENCE_ROOT")
    if env_root:
        candidate = Path(env_root) / name
        if candidate.is_file():
            return candidate
    for directory in (root, *root.parents):
        candidate = directory / evidence / name
        if candidate.is_file():
            return candidate
    fallback = Path("C:/Users/scott/Documents/Codex/qr9/integrated/docs/capabilities/evidence/boardable-meeting-form") / name
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(name)


SOURCE = {"provider": "boardable", "url": ORG, "namespace": NS}
CREATE = {
    "key": "new", "entity": "meeting", "operation": "create",
    "fields": {
        "title": "Contract Fixture", "description": "<p>Description</p>", "location": "Room 1",
        "timezone": "America/New_York",
        "dates": [{"date": "11/16/2026", "from": "10:00 pm", "to": "11:00 pm"}],
    },
}
UPDATE = {
    "key": "edit", "entity": "meeting", "operation": "update", "resource_id": "526577",
    "fields": {"title": "Contract Fixture Revised"},
}


def _server_clock(value):
    match = re.fullmatch(r"([1-9]|1[0-2]):([0-5][0-9]) ([ap]m)", value, re.I)
    assert match
    hour, minute = int(match.group(1)), int(match.group(2))
    if match.group(3).lower() == "pm" and hour != 12:
        hour += 12
    if match.group(3).lower() == "am" and hour == 12:
        hour = 0
    return hour, minute


def _server_utc(entry, timezone_name):
    day = datetime.strptime(entry["date"], "%m/%d/%Y")
    fh, fm = _server_clock(entry["from"])
    th, tm = _server_clock(entry["to"])
    start = datetime(day.year, day.month, day.day, fh, fm, tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)
    end = datetime(day.year, day.month, day.day, th, tm, tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)
    return (start.strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
            end.strftime("%Y-%m-%dT%H:%M:%S.000000Z"))


def _base_meeting():
    return {
        "id": 526577, "organization_id": 46098, "owner_id": 403839,
        "title": "Contract Fixture", "description": "<p>Description</p>", "location": "Room 1",
        "start": "2026-11-17T03:00:00.000000Z", "end": "2026-11-17T04:00:00.000000Z",
        "timezone": "America/New_York",
        "datesTimezone": [{"date": "11/16/2026", "from": "10:00 pm", "to": "11:00 pm",
                           "id": 526577, "timezone": "America/New_York"}],
        "slug": "0e58cf-contract-fixture", "url": URL,
        "remote_option": "no_remote", "remote_url": None, "remote_url_description": None,
        "disable_remote_rsvp": 0, "minutes_type": "free_form",
        "public_member_dashboard": 0, "public_page": 0, "published": False,
        "published_level": 0, "published_at": None, "minutes_published": 0,
        "materials_published_status": None, "published_materials_status": None,
        "agenda_live_version": None, "agenda_draft_version": None, "agenda_last_published_at": None,
        "enable_recording": 0, "enable_transcription": 0, "enable_ai_summary": 0,
        "series_id": 0, "recurrence_id": None, "alternative_dates": None,
        "additional_dates": [], "video_conference_enabled": False, "starred_public_page": 0,
        "notify": [403839], "group_id": None, "group": None,
        "members": [{"id": 403839, "pivot": {
            "meeting_id": 526577, "user_id": 403839, "rsvp": "", "attendance": "",
            "collaborator": 0, "is_voter": 1, "token": "secret-token",
        }, "email": "secret@example.test", "profile": {"email": "secret@example.test"}}],
        "groups": [], "guests": [], "guest_members": [],
        "agenda_downloads_aggregate": None, "previous_meeting": None,
        "created_at": "2026-11-16T21:53:54.000000Z",
        "updated_at": "2026-11-16T21:53:54.000000Z",
        "formattedMeetingTime": {"datetime": "display only"},
        "timeUntilStart": "display only", "meetingHasStarted": False,
        "name": "Contract Fixture", "blurb": "<p>Description</p>",
    }


class Vendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.fault = None
        self.created = 0
        self.meetings = {"526577": _base_meeting()}

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert headers["Cookie"] == "boardable_session=secret-session"
        assert headers["X-XSRF-TOKEN"] == "secret-csrf"
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert "Authorization" not in headers
        self.calls.append((method, url, body))
        if method == "GET":
            exact = url[:-len("?format=json")] if url.endswith("?format=json") else None
            for meeting in self.meetings.values():
                if exact == meeting["url"]:
                    payload = deepcopy(meeting)
                    if self.fault == "oversize_members":
                        payload["members"] = [
                            {"id": 700000 + index, "pivot": {"meeting_id": 526577, "user_id": 700000 + index}}
                            for index in range(10001)
                        ]
                    return WriteResponse(200, json.dumps({"meeting": payload}).encode())
            return WriteResponse(404, b'{"error":"not found"}')
        data = json.loads(body)
        if url == ORG + "meetings":
            self.created += 1
            identity = 526600 + self.created
            slug = str(identity) + "-" + re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:80]
            start, end = _server_utc(data["dates"][0], data["timezone"])
            meeting = _base_meeting()
            meeting.update({
                "id": identity, "owner_id": data["owner_id"], "title": data["title"],
                "description": data["description"], "location": data["location"],
                "timezone": data["timezone"], "start": start, "end": end,
                "slug": slug, "url": ORG + "meetings/" + slug,
                "datesTimezone": [{"date": data["dates"][0]["date"],
                                   "from": data["dates"][0]["from"],
                                   "to": data["dates"][0]["to"],
                                   "id": identity, "timezone": data["timezone"]}],
                "members": [{"id": data["owner_id"], "pivot": {
                    "meeting_id": identity, "user_id": data["owner_id"], "is_voter": 1,
                    "token": "secret-token",
                }, "email": "secret@example.test"}],
                "groups": [], "guests": [], "guest_members": [],
            })
            self.meetings[str(identity)] = meeting
            if self.fault == "timeout_after_create":
                raise TimeoutError()
            if self.fault == "wrong_create_status":
                return WriteResponse(200, json.dumps(meeting).encode())
            if self.fault == "null_id":
                return WriteResponse(201, json.dumps({"organization_id": 46098, "url": meeting["url"]}).encode())
            if self.fault == "oversize_post":
                return WriteResponse(201, b"x" * (byte_limit + 1))
            return WriteResponse(201, json.dumps(meeting).encode())
        assert url == ORG + "meetings_v2/526577"
        meeting = self.meetings["526577"]
        if self.fault != "ignore_update":
            meeting["title"] = data["title"]
            meeting["description"] = data["description"]
            meeting["location"] = data["location"]
            meeting["timezone"] = data["timezone"]
            meeting["start"], meeting["end"] = _server_utc(data["dates"][0], data["timezone"])
            meeting["datesTimezone"] = [{"date": data["dates"][0]["date"],
                                         "from": data["dates"][0]["from"],
                                         "to": data["dates"][0]["to"],
                                         "id": 526577, "timezone": data["timezone"]}]
            slug = "0e58cf-" + re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:80]
            meeting["slug"] = slug
            meeting["url"] = ORG + "meetings/" + slug
            if self.fault == "collateral":
                meeting["agenda_downloads_aggregate"] = "changed"
            if self.fault == "wrong_owner":
                meeting["owner_id"] = 999
            if self.fault == "wrong_invitee":
                meeting["members"].append({"id": 999, "pivot": {"meeting_id": 526577, "user_id": 999}})
            if self.fault == "public":
                meeting["public_page"] = 1
            if self.fault == "materials_published":
                meeting["materials_published_at"] = "11/16/2026 at 5:00 PM"
        if self.fault == "timeout_after_update":
            raise TimeoutError()
        if self.fault == "wrong_update_status":
            return WriteResponse(201, json.dumps(meeting).encode())
        if self.fault == "bad_reply":
            return WriteResponse(200, b'{"no":true}')
        return WriteResponse(200, json.dumps(meeting).encode())


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(
        principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({NS}),
        credentials={"boardable": {
            "current_meeting_form": True,
            "tenant": "city",
            "org_url": ORG,
            "organization_id": 46098,
            "allowed_namespaces": [NS],
            "session_cookie": "boardable_session=secret-session",
            "xsrf_token": "secret-csrf",
            "owner_id": 403839,
            "permissions": ["meeting:create", "meeting:update"],
            "meeting_ids": ["526577"],
            "meeting_urls": {"526577": URL},
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def plan(engine, context, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


def test_create_minimal_request_readback_and_restart_no_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    assert vendor.calls == []
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == "526601"
    assert item["readback"]["title"] == "Contract Fixture"
    assert item["readback"]["members"][0]["id"] == 403839
    post = next(call for call in vendor.calls if call[0] == "POST")
    assert post[1] == ORG + "meetings"
    body = json.loads(post[2])
    assert body["owner_id"] == 403839
    assert body["meeting_type"] == "single"
    assert body["minutes_type"] == "free_form"
    assert body["remote_option"] == "no_remote"
    assert body["invitee_ids"] == [403839]
    assert "secret-session" not in json.dumps(result.public_dict())
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(call[0] == "POST" for call in vendor.calls) == 1


def test_captured_sanitized_actual_response_normalizes_and_verifies_create():
    create_capture = json.loads(_capture("boardable-meeting-minimal-create.json").read_text(encoding="utf-8"))
    update_capture = json.loads(_capture("boardable-meeting-minimal-update.json").read_text(encoding="utf-8"))
    config = {"organization_id": 46098}

    created_id, created_url, created_slug = _response_identity(create_capture["data"], config, ORG)
    assert created_id == 526577
    assert created_url == (
        "https://app.boardable.com/quorumrelay-evaluation/meetings/"
        "0e58cf-quorumrelay-contract-fixture"
    )
    assert created_slug == "0e58cf-quorumrelay-contract-fixture"

    updated = _normalize_meeting(update_capture["readback"]["meeting"], config, ORG)
    assert updated["id"] == 526577
    assert updated["organization_id"] == 46098
    assert updated["url"] == (
        "https://app.boardable.com/quorumrelay-evaluation/meetings/"
        "0e58cf-quorumrelay-contract-fixture-revised"
    )
    assert updated["datesTimezone"][0]["date"] == "11/16/2026"

    expected = {
        "title": updated["title"],
        "description": updated["description"],
        "location": updated["location"],
        "timezone": updated["timezone"],
        "owner_id": updated["owner_id"],
        "start": updated["start"],
        "end": updated["end"],
        "date": updated["datesTimezone"][0]["date"],
        "from": updated["datesTimezone"][0]["from"],
        "to": updated["datesTimezone"][0]["to"],
    }
    assert _verify_create(updated, {"create_expected": expected}, config)


def test_update_title_changes_canonical_url_and_preserves_business_state(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute("commit_write", plan(engine, context, UPDATE), context=context)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["readback"]["url"] == ORG + "meetings/0e58cf-contract-fixture-revised"
    assert item["readback"]["agenda_downloads_aggregate"] is None
    assert item["readback"]["members"][0]["pivot"].get("token") is None
    post = next(call for call in vendor.calls if call[0] == "POST")
    body = json.loads(post[2])
    assert body["dates"][0]["id"] == 526577
    assert body["assignable_class"] == "App\\Boardable\\Meetings\\Meeting"
    assert body["invitee_ids"] == [403839]
    assert body["public_page"] is False
    assert "secret@example.test" not in json.dumps(result.public_dict())


def test_cancel_before_create_post_sends_nothing(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    context.cancellation.set()
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "cancelled", result.public_dict()
    assert not vendor.calls


@pytest.mark.parametrize("dates", [
    [{"date": "03/08/2026", "from": "2:30 am", "to": "3:30 am"}],
    [{"date": "11/01/2026", "from": "1:30 am", "to": "2:30 am"}],
])
def test_dst_nonexistent_and_ambiguous_times_are_rejected(tmp_path, dates):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CREATE)
    change["fields"]["dates"] = dates
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


@pytest.mark.parametrize("source_url,credential_change", [
    ("https://app.boardable.com/quorumrelay-evaluation/nested/", None),
    ("https://app.boardable.com/quorumrelay-evaluation/?x=1", None),
    ("https://app.boardable.com:443/quorumrelay-evaluation/", None),
    ("https://evil.example/quorumrelay-evaluation/", None),
    (ORG, {"xsrf_token": "bad\nvalue"}),
    (ORG, {"session_cookie": "bad cookie"}),
])
def test_unsafe_source_and_credentials_never_reach_network(tmp_path, source_url, credential_change):
    engine, context, vendor = setup(tmp_path)
    if credential_change:
        context.credentials["boardable"].update(credential_change)
    else:
        context.credentials["boardable"]["org_url"] = source_url
    source = {"provider": "boardable", "url": source_url, "namespace": NS}
    result = engine.execute("plan_write", {"source": source, "changes": [CREATE]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not vendor.calls


def test_expected_version_and_fresh_preflight_conflicts(tmp_path):
    engine, context, vendor = setup(tmp_path)
    bad = {**UPDATE, "expected_version": "not-the-fingerprint"}
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [bad]}, context=context)
    assert result.status == "failed"
    assert not any(call[0] == "POST" for call in vendor.calls)
    approval = plan(engine, context, UPDATE)
    vendor.meetings["526577"]["agenda_downloads_aggregate"] = "changed"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(call[0] == "POST" for call in vendor.calls)


@pytest.mark.parametrize("fault", ["timeout_after_create", "null_id", "oversize_post"])
def test_uncertain_create_retains_no_replay(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, CREATE)
    vendor.fault = fault
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[0] == "POST" for call in vendor.calls) == 1


@pytest.mark.parametrize("fault,change", [
    ("wrong_create_status", CREATE),
    ("wrong_update_status", UPDATE),
])
def test_unexpected_success_status_is_uncertain_and_not_replayed(tmp_path, fault, change):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, change)
    vendor.fault = fault
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[0] == "POST" for call in vendor.calls) == 1


def test_oversized_member_list_rejected_before_post(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = "oversize_members"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [UPDATE]}, context=context)
    assert result.status == "failed", result.public_dict()
    assert not any(call[0] == "POST" for call in vendor.calls)


def test_update_response_lost_old_url_is_uncertain_and_never_put_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, UPDATE)
    vendor.fault = "timeout_after_update"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    assert result.data["items"][0]["resource_id"] == "526577"
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(call[0] == "POST" for call in vendor.calls) == 1


@pytest.mark.parametrize("fault", ["collateral", "wrong_owner", "wrong_invitee", "public", "materials_published"])
def test_update_collateral_or_unrequested_state_is_uncertain(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = fault
    result = engine.execute("commit_write", plan(engine, context, UPDATE), context=context)
    assert result.data["items"][0]["state"] == "uncertain", result.public_dict()
    assert sum(call[0] == "POST" for call in vendor.calls) == 1


def test_meeting_form_rejects_agenda_builder_combination(tmp_path):
    engine, context, vendor = setup(tmp_path)
    context.credentials["boardable"]["legacy_agenda_editor"] = True
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [CREATE]}, context=context)
    assert result.status == "failed"
    assert not vendor.calls
