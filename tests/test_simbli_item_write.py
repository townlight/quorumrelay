"""Synthetic Simbli staff/item DTOs through the real Engine and SQLite coordinator."""

from copy import deepcopy
import json
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.compat import source_namespace
from quorumrelay.models import Bounds, Source
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import WriteChange, default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers.simbli_write import SimbliWriteAdapter


URL = "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=42&MID=123"
NAMESPACE = source_namespace("simbli", urlsplit(URL))
SOURCE = {"provider": "simbli", "url": URL, "namespace": NAMESPACE}
TREE = "/Services/api/MeetingView/GetItemsTreeDTO/"
DETAILS = "/Services/api/MeetingView/GetMeetingItemDetailsModel/"
SAVE = "/Services/api/MeetingView/SaveAgendaItem/"
LOCK = "/api/Workflow/GetItemEditAccess/"
RELEASE = "/api/Workflow/ReleaseItemEditing/"
CHANGE = {
    "key": "title",
    "entity": "agenda_item",
    "operation": "update",
    "meeting_id": "123",
    "resource_id": "176766",
    "fields": {"title": "Updated Called to Order"},
}
BOUNDS = {
    "max_pages": 20,
    "parser_bytes": 200000,
    "transfer_bytes": 200000,
    "max_records": 1000,
    "deadline_seconds": 5,
}


def tree(root_sentinel="ROOT-SENTINEL=="):
    def row(ident, agenda, parent, title, level, children=(), label=""):
        return {
            "ID": ident,
            "AgendaID": agenda,
            "ParentID": parent,
            "Title": title,
            "Level": level,
            "SeqUnderParent": 1,
            "IsExpanded": True,
            "Children": list(children),
            "HasAttachment": False,
            "IsSelected": False,
            "HasStickyNotes": False,
            "IsChanged": False,
            "IsReady": True,
            "Visibility": 0,
            "WorkflowStatus": "",
            "WorkflowStepIndicator": "",
            "IsActiveWorkflowStepUser": False,
            "IsWorkflowUser": False,
            "UserWorkflowStatus": "",
            "ChildrenCount": 0,
            "ShowVisibilityIcon": False,
            "Deleted": False,
            "DeletionCount": 0,
            "bulletLabel": label,
        }

    child = row("enc-child", 201, "enc-parent", "a. Child Item", 1, label="a")
    parent = row("enc-parent", 200, root_sentinel, "III. Consent Agenda", 0, [child], "III")
    selected = row("enc-selected", 176766, root_sentinel, "II. Meeting Called to Order", 0, label="II")
    first = row("enc-first", 100, root_sentinel, "I. Opening", 0, label="I")
    return {"Items": [first, selected, parent], "DeletedItems": None}


def details(selected_id="enc-selected", editable=True, title="Meeting Called to Order"):
    return {
        "ItemDetails": {
            "EncrID": selected_id,
            "EncrParentID": None,
            "SelectedTab": 1,
            "Title": title,
            "Sequence": "II",
            "Level": 0,
            "VisibilityMode": 0,
            "IsReady": True,
            "IsEditable": editable,
            "AssignedTo": "0",
            "HasStickyNote": False,
            "CreatedOn": "10/19/2026",
            "CreatedOnTime": "12:38 PM",
            "CreatedBy": "Amy Bishop",
            "ModifiedOn": "11/12/2026",
            "ModifiedOnTime": "07:57 AM",
            "ModifiedBy": "Amy Bishop",
            "DeletedOn": None,
            "DeletedOnTime": None,
            "DeletedBy": None,
            "RestoredOn": None,
            "RestoredOnTime": None,
            "RestoredBy": None,
            "SiteTimeZoneDate": "ET",
            "WIPComment": "preserve this comment",
            "IsPublicCommentOn": False,
            "HasWorkflow": False,
            "Deleted": False,
            "Operation": 1,
            "MinutesTabHighlighted": False,
            "ContentTabHighlighted": False,
            "ParentItemEffectiveVisibility": 0,
            "HasAnyChild": False,
        },
        "ItemContents": [
            {
                "FieldName": "abstract",
                "FieldTitle": "Quick Summary / Abstract",
                "ControlType": 11,
                "Content": "<html><body>Business text</body></html>",
                "Date": None,
                "IsEdit": False,
                "DraftPolicies": None,
                "AdoptedPolicies": None,
                "Policies": None,
                "PolicyTypes": None,
                "Goals": None,
                "PlanItems": [],
                "EditGoals": None,
                "MinuteAttachementData": None,
                "HyperLinks": None,
                "Attachments": None,
                "FieldVisibility": 0,
                "IsExpanded": False,
                "HasData": True,
                "Order": 1,
                "IncDraftPolicyInlineComments": False,
                "IncAdoptedPolicyInlineComments": False,
                "IncludeInlineComments": None,
                "IncludeTrackChanges": None,
                "SiteName": None,
                "HasComporePolicyAccess": False,
                "UnknownField": {"keep": [1, None, False]},
            },
            {
                "FieldName": "fileAttachment",
                "FieldTitle": "Supporting Documents",
                "ControlType": 9,
                "Content": "",
                "Date": None,
                "IsEdit": False,
                "DraftPolicies": None,
                "AdoptedPolicies": None,
                "Policies": None,
                "PolicyTypes": None,
                "Goals": None,
                "PlanItems": [],
                "EditGoals": None,
                "MinuteAttachementData": None,
                "HyperLinks": [],
                "Attachments": [
                    {
                        "AttachmentID": 131003,
                        "Title": "Sign In Sheet",
                        "FileName": "sign.pdf",
                        "ContentType": "application/pdf",
                        "FileSize": 0,
                        "SecurityToken": None,
                        "UnknownAttachment": "keep",
                    }
                ],
                "FieldVisibility": 0,
                "IsExpanded": False,
                "HasData": True,
                "Order": 13,
                "IncDraftPolicyInlineComments": False,
                "IncAdoptedPolicyInlineComments": False,
                "IncludeInlineComments": None,
                "IncludeTrackChanges": None,
                "SiteName": None,
                "HasComporePolicyAccess": False,
            },
        ],
        "HasAnyChild": False,
        "PublicCommentConfiguration": {
            "ID": "comment-config",
            "AllowPublicComment": False,
            "AnyCommentVisibliToPublic": False,
        },
        "CommentViewDTO": {
            "publicCommentLst": [],
            "DummyObj": {
                "ID": "dummy",
                "UserID": None,
                "UserName": None,
                "Comments": "keep-comment",
                "AgendaID": "enc-first",
                "MeetingID": "enc-meeting",
                "IsDeleted": False,
                "UnknownCommentField": True,
            },
            "IsDeletedItem": False,
        },
        "IsLoadContent": True,
        "MinutesDto": None,
    }


def _node(value, agenda):
    for row in value["Items"]:
        if row["AgendaID"] == agenda:
            return row
        for child in row["Children"]:
            if child["AgendaID"] == agenda:
                return child
    raise AssertionError("missing node")


class Vendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.tree = tree()
        self.details = details()
        self.faults = set()
        self.rotate = None
        self.lock_count = 0
        self.release_count = 0
        self.save_count = 0
        self.save_bodies = []
        self.release_forms = []
        self.last_lock_item = None
        self.context = None
        self.lock_dto = {
            "SessionID": "session-secret",
            "UserID": "lock-user",
            "Username": "Lock Editor",
            "ItemID": None,
            "MeetingID": "lock-meeting",
            "SiteID": "lock-site",
            "LastActivity": "2026-11-12T00:00:00Z",
            "Access": True,
        }

    def selected_id(self):
        return self.rotate or _node(self.tree, 176766)["ID"]

    def page(self, logged="True"):
        raw = json.dumps(self.lock_dto)
        return f"""<html><script>
var did = '42';
var meetingID = '123';
var isUserLoggedIn = '{logged}';
var enDID = 'enc-did-secret';
var enMeetingID = 'enc-meeting-secret';
var encrTZ = 'enc-tz-secret';
var sToken = 'secret-token';
var enCuUID = 'enc-user-secret';
var encrIpAddress = '10.0.0.1';
var viewMode = 'myview';
var app2Url = 'https://app2.eboardsolutions.com';
var itemEditAccess = JSON.parse({raw!r});
</script></html>"""

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        self.calls.append((method, url, headers, body))
        parsed = urlsplit(url)
        if method == "GET" and url == URL:
            if "redirect" in self.faults:
                return WriteResponse(302, b"")
            if "oversize_page" in self.faults:
                return WriteResponse(200, b"x" * (byte_limit + 1))
            if "login" in self.faults:
                return WriteResponse(200, self.page("False").encode())
            return WriteResponse(200, self.page().encode())
        if method == "GET" and parsed.path == TREE:
            if "malformed_tree" in self.faults:
                return WriteResponse(200, b"not json")
            value = deepcopy(self.tree)
            if "duplicate_tree" in self.faults:
                value["Items"].append(deepcopy(value["Items"][0]))
            if "missing_selected" in self.faults:
                value["Items"] = [row for row in value["Items"] if row["AgendaID"] != 176766]
            if "conflict_after_lock" in self.faults and self.lock_count:
                value["UnknownTreeChange"] = True
            return WriteResponse(200, json.dumps(value).encode())
        if method == "GET" and parsed.path == DETAILS:
            if "deleted" in self.faults:
                value = deepcopy(self.details)
                value["ItemDetails"]["Deleted"] = True
                return WriteResponse(200, json.dumps(value).encode())
            if "workflow" in self.faults:
                value = deepcopy(self.details)
                value["ItemDetails"]["HasWorkflow"] = True
                return WriteResponse(200, json.dumps(value).encode())
            return WriteResponse(200, json.dumps(self.details).encode())
        if method == "POST" and parsed.path == LOCK:
            self.lock_count += 1
            sent = json.loads(body)
            self.last_lock_item = sent["ItemID"]
            if "lock_false" in self.faults:
                return WriteResponse(200, json.dumps({"HasAccess": False}).encode())
            if "lock_malformed" in self.faults:
                return WriteResponse(200, b"not json")
            if "lock_timeout" in self.faults:
                raise TimeoutError()
            if "cancel_on_lock" in self.faults and self.context is not None:
                self.context.cancellation.set()
            return WriteResponse(200, json.dumps({"HasAccess": True, "AccessTakenBy": "other"}).encode())
        if method == "POST" and parsed.path == RELEASE:
            self.release_count += 1
            form = parse_qs(body.decode(), keep_blank_values=True)
            self.release_forms.append(form)
            if "release_fail" in self.faults:
                return WriteResponse(500, b"")
            return WriteResponse(200, b"")
        if method == "POST" and parsed.path == SAVE:
            self.save_count += 1
            value = json.loads(body)
            self.save_bodies.append(value)
            title = value["itemDetailsDTO"]["Title"]
            node = _node(self.tree, 176766)
            node["Title"] = node["bulletLabel"] + ". " + title
            self.details["ItemDetails"]["Title"] = title
            self.details["ItemDetails"]["ModifiedOn"] = "11/13/2026"
            self.details["ItemDetails"]["ModifiedBy"] = "Editor"
            for field in self.details["ItemContents"]:
                field["IsEdit"] = True
            if "collateral" in self.faults:
                self.details["ItemDetails"]["VisibilityMode"] = 99
                self.details["CommentViewDTO"]["DummyObj"]["Comments"] = "changed"
            if "save_timeout" in self.faults:
                raise TimeoutError()
            if "cancel_after_save" in self.faults and self.context is not None:
                self.context.cancellation.set()
            return WriteResponse(200, b"")
        raise AssertionError(url)

    def rotate_selected(self):
        old = _node(self.tree, 176766)["ID"]
        new = "enc-rotated"
        node = _node(self.tree, 176766)
        node["ID"] = new
        self.details["ItemDetails"]["EncrID"] = new
        if self.details["CommentViewDTO"]["DummyObj"]["AgendaID"] == old:
            self.details["CommentViewDTO"]["DummyObj"]["AgendaID"] = new
        self.rotate = new


def setup(tmp_path, *, max_pages=20):
    vendor = Vendor()
    context = OperationContext(
        principal="editor",
        client_id="fixture",
        tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({NAMESPACE}),
        credentials={
            "simbli": {
                "tenant": "city",
                "site_url": URL,
                "allowed_namespaces": [NAMESPACE],
                "site_id": "42",
                "meeting_id": "123",
                "item_ids": ["176766"],
                "permissions": ["agenda_item:update"],
                "encrypted_user_id": "enc-user-secret",
                "lock_user_id": "lock-user",
                "session_cookie": "simbli_session=secret-cookie",
                "token": "secret-jwt-token",
            }
        },
    )
    vendor.context = context
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def bounds(max_pages=20):
    return {**BOUNDS, "max_pages": max_pages}


def plan(engine, context, change=None, max_pages=20):
    result = engine.execute(
        "plan_write",
        {"source": SOURCE, "changes": [change or CHANGE], "bounds": bounds(max_pages)},
        context=context,
    )
    assert result.status == "completed", result.public_dict()
    return result


def approval(result):
    return {"plan_id": result.data["plan_id"], "plan_hash": result.data["plan_hash"]}


def posts(vendor):
    return [call for call in vendor.calls if call[0] == "POST"]


def safe(value):
    text = json.dumps(value)
    for secret in (
        "secret-token",
        "secret-cookie",
        "secret-jwt-token",
        "enc-did-secret",
        "enc-meeting-secret",
        "enc-user-secret",
        "lock-user",
        "session-secret",
    ):
        assert secret not in text
    return text


def test_plan_commit_title_only_preserves_tree_dto_and_release(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    assert not posts(vendor)
    safe(prepared.data)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.lock_count == 1 and vendor.save_count == 1 and vendor.release_count == 1
    assert vendor.save_bodies[0]["EncrID"] == "enc-selected"
    assert vendor.save_bodies[0]["itemDetailsDTO"]["WIPComment"] == "preserve this comment"
    assert all(field["IsEdit"] is True for field in vendor.save_bodies[0]["itemContentDTO"])
    assert vendor.save_bodies[0]["itemContentDTO"][0]["UnknownField"] == {"keep": [1, None, False]}
    assert vendor.release_forms[0]["ItemID"] == ["enc-selected"]
    assert vendor.release_forms[0]["Access"] == ["true"]
    assert _node(vendor.tree, 201)["Title"] == "a. Child Item"
    assert vendor.details["CommentViewDTO"]["DummyObj"]["Comments"] == "keep-comment"
    safe(result.data)


def test_same_value_title_is_explicit_no_send(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    change["fields"]["title"] = "Meeting Called to Order"
    prepared = plan(engine, context, change)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["no_send"] is True
    assert vendor.lock_count == 0 and vendor.save_count == 0 and vendor.release_count == 0


def test_public_noneditable_fixture_and_prepare_posts_zero(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.details = details(editable=False)
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed"
    assert not posts(vendor)


@pytest.mark.parametrize(
    "fault",
    [
        "redirect",
        "oversize_page",
        "login",
        "malformed_tree",
        "duplicate_tree",
        "missing_selected",
        "deleted",
        "workflow",
    ],
)
def test_invalid_page_or_item_never_locks_or_saves(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed"
    assert not posts(vendor)
    safe(result.public_dict())


def test_conflict_before_lock_then_after_lock_releases_only_exact_item(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.tree["UnknownTreeChange"] = True
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed"
    assert vendor.lock_count == 0 and vendor.save_count == 0 and vendor.release_count == 0
    engine2, context2, vendor2 = setup(tmp_path / "second")
    prepared2 = plan(engine2, context2)
    vendor2.faults.add("conflict_after_lock")
    result2 = engine2.execute("commit_write", approval(prepared2), context=context2)
    assert result2.status == "failed"
    assert vendor2.lock_count == 1 and vendor2.save_count == 0 and vendor2.release_count == 1
    assert vendor2.release_forms[0]["ItemID"] == ["enc-selected"]
    assert RELEASE in vendor2.calls[-1][1]
    assert "ReleaseAllItemsEditAccess" not in vendor2.calls[-1][1]


@pytest.mark.parametrize("fault", ["lock_false", "lock_malformed", "lock_timeout", "cancel_on_lock"])
def test_lock_failure_or_cancel_fails_closed_and_releases(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add(fault)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status != "completed"
    assert vendor.save_count == 0 and vendor.release_count == 1
    assert vendor.release_forms[0]["ItemID"] == ["enc-selected"]
    safe(result.public_dict())


@pytest.mark.parametrize("case", ["tenant", "namespace", "permission", "item"])
def test_saved_policy_revocation_fails_before_network(tmp_path, case):
    engine, context, vendor = setup(tmp_path)
    if case == "tenant":
        context.tenant = "other"
    elif case == "namespace":
        context.allowed_namespaces = frozenset({"other"})
    elif case == "permission":
        context.credentials["simbli"]["permissions"] = []
    else:
        context.credentials["simbli"]["item_ids"] = ["9"]
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed"
    assert not vendor.calls


def test_budget_and_expected_version_and_rotation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds(2)}, context=context
    )
    assert result.status == "failed" and not vendor.calls
    engine2, context2, vendor2 = setup(tmp_path / "two")
    first = plan(engine2, context2)
    fingerprint = first.data["plan"]["changes"][0]["before_fingerprint"]
    wrong = deepcopy(CHANGE)
    wrong["expected_version"] = "wrong"
    assert (
        engine2.execute(
            "plan_write", {"source": SOURCE, "changes": [wrong], "bounds": bounds()}, context=context2
        ).status
        == "failed"
    )
    right = deepcopy(CHANGE)
    right["expected_version"] = fingerprint
    plan(engine2, context2, right)
    vendor2.rotate_selected()
    prepared = plan(engine2, context2)
    committed = engine2.execute("commit_write", approval(prepared), context=context2)
    assert committed.status == "completed", committed.public_dict()
    assert vendor2.save_bodies[0]["EncrID"] == "enc-rotated"


def test_insufficient_commit_budget_cannot_acquire_lock(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context, max_pages=9)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed"
    assert vendor.lock_count == 0 and vendor.save_count == 0 and vendor.release_count == 0


def test_save_timeout_restart_reconciles_read_only(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("save_timeout")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert result.data["items"][0]["resource_id"] == "176766"
    assert vendor.save_count == 1 and vendor.release_count == 1
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    recovered = reopened.execute("commit_write", approval(prepared), context=context)
    assert recovered.status == "completed", recovered.public_dict()
    assert vendor.save_count == 1
    assert vendor.lock_count == 1 and vendor.release_count == 1
    safe(recovered.data)


def test_collateral_readback_is_uncertain(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("collateral")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.save_count == 1


def test_cancel_after_save_retains_id_and_no_second_send(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("cancel_after_save")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert result.data["items"][0]["resource_id"] == "176766"
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.save_count == 1 and vendor.release_count == 1


def test_prepared_mutation_is_rejected_directly(tmp_path):
    engine, context, vendor = setup(tmp_path)
    adapter = SimbliWriteAdapter(vendor)
    source = Source(**SOURCE)
    prepared = adapter.prepare(
        source, WriteChange.from_dict(CHANGE), context, Bounds(**BOUNDS), monotonic() + 5
    )
    prepared["after"]["item"]["ItemDetails"]["Title"] = "Tampered"
    with pytest.raises(ValueError):
        adapter.apply(source, prepared, context, Bounds(**BOUNDS), monotonic() + 5)
    assert vendor.save_count == 0


def test_default_registry_wiring():
    assert "simbli" in default_adapters()


@pytest.mark.parametrize("route", [TREE, DETAILS])
@pytest.mark.parametrize("status", [302, 401, 403, 500])
def test_valid_shaped_denied_read_never_locks(tmp_path, route, status):
    engine, context, vendor = setup(tmp_path)
    send = vendor.send

    def denied(url, **kwargs):
        response = send(url, **kwargs)
        return WriteResponse(status, response.content) if urlsplit(url).path == route else response

    vendor.send = denied
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed"
    assert not posts(vendor)


@pytest.mark.parametrize("field,value", [("body", "x"), ("input_format", "html")])
def test_source_overrides_rejected_without_network(tmp_path, field, value):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute(
        "plan_write",
        {"source": {**SOURCE, field: value}, "changes": [CHANGE], "bounds": bounds()},
        context=context,
    )
    assert result.status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("value", [True, 176766.0])
def test_noncanonical_native_id_rejected_without_network(tmp_path, value):
    engine, context, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    change["resource_id"] = value
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [change], "bounds": bounds()}, context=context
    )
    assert result.status == "failed"
    assert not vendor.calls


def test_low_nested_array_bound_and_duplicate_json_keys():
    from civic_data_connectors.providers.simbli_write import _bounded_json

    with pytest.raises(ValueError):
        _bounded_json(b'{"nested":[1,2,3]}', Bounds(max_records=2))
    with pytest.raises(ValueError):
        _bounded_json(b'{"Items":[],"Items":[]}', Bounds())


def test_public_capture_not_editable_and_derived_authorized_dto_preserved(tmp_path):
    capture = json.loads(
        (
            Path(__file__).parents[1]
            / "docs/investigations/2026-11-16-paused/simbli-public-item-model-sanitized.json"
        ).read_text(encoding="utf-8")
    )
    assert capture["ItemDetails"]["IsEditable"] is False
    engine, context, vendor = setup(tmp_path)
    vendor.details = deepcopy(capture)
    _node(vendor.tree, 176766)["ID"] = capture["ItemDetails"]["EncrID"]
    denied = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert denied.status == "failed" and not posts(vendor)
    # Synthetic authorized derivative: never an observed staff response.
    vendor.details["ItemDetails"]["IsEditable"] = True
    vendor.details["CommentViewDTO"]["DummyObj"]["MeetingID"] = "enc-meeting-secret"
    vendor.details["CommentViewDTO"]["DummyObj"]["EncrTimeZone"] = "enc-tz-secret"
    attachment = vendor.details["ItemContents"][2]["Attachments"][0]
    attachment["SecurityToken"] = "attachment-secret-before"
    prepared = plan(engine, context)
    attachment["SecurityToken"] = "attachment-secret-rotated"
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    sent = vendor.save_bodies[0]
    assert sent["itemContentDTO"][2]["Attachments"][0] == attachment
    assert sent["itemDetailsDTO"]["VisibilityMode"] == capture["ItemDetails"]["VisibilityMode"]
    assert vendor.details["CommentViewDTO"]["DummyObj"]["UserID"] is None
    durable = safe(prepared.public_dict()) + safe(result.public_dict())
    database = (tmp_path / "write.sqlite").read_bytes()
    for token in [
        "attachment-secret-before",
        "attachment-secret-rotated",
        "enc-meeting-secret",
        "enc-tz-secret",
    ]:
        assert token not in durable and token.encode() not in database
    assert capture["ItemDetails"]["IsEditable"] is False


@pytest.mark.parametrize("field", ["AttachmentID", "Title", "UnknownAttachment"])
def test_attachment_business_changes_conflict_before_lock(tmp_path, field):
    engine, context, vendor = setup(tmp_path)
    attachment = vendor.details["ItemContents"][1]["Attachments"][0]
    attachment["SecurityToken"] = "attachment-secret"
    prepared = plan(engine, context)
    attachment[field] = 999 if field == "AttachmentID" else "changed"
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed"
    assert vendor.lock_count == 0 and vendor.save_count == 0


@pytest.mark.parametrize("field,value", [("token", "unrecognized-secret"), ("$simbli_ref", "agenda:176766")])
def test_unknown_credential_or_reserved_provider_key_is_rejected(tmp_path, field, value):
    engine, context, vendor = setup(tmp_path)
    vendor.details["Unexpected"] = {field: value}
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed" and not posts(vendor)


@pytest.mark.parametrize("stage", ["read", "lock"])
def test_midflight_grant_revocation_prevents_mutation(tmp_path, stage):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def revoke(url, **kwargs):
        response = send(url, **kwargs)
        path = urlsplit(url).path
        if (stage == "read" and path == DETAILS) or (stage == "lock" and path == LOCK):
            context.credentials["simbli"]["permissions"] = []
        return response

    vendor.send = revoke
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed" and vendor.save_count == 0
    assert vendor.lock_count == (stage == "lock")
    assert vendor.release_count == (stage == "lock")


def test_success_with_release_failure_is_durable_and_never_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("release_fail")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["lock_release_error"] is True
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    repeated = reopened.execute("commit_write", approval(prepared), context=context)
    assert repeated.data["items"][0]["lock_release_error"] is True
    assert vendor.save_count == vendor.lock_count == vendor.release_count == 1


@pytest.mark.parametrize("change", ["content", "child", "order", "visibility", "comment", "tree_title"])
def test_independent_collateral_changes_remain_uncertain(tmp_path, change):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def collateral(url, **kwargs):
        response = send(url, **kwargs)
        if urlsplit(url).path == SAVE:
            if change == "content":
                vendor.details["ItemContents"][0]["Content"] = "changed"
            elif change == "child":
                _node(vendor.tree, 201)["Title"] = "changed"
            elif change == "order":
                vendor.tree["Items"].reverse()
            elif change == "visibility":
                vendor.details["ItemDetails"]["VisibilityMode"] = 99
            elif change == "comment":
                vendor.details["CommentViewDTO"]["DummyObj"]["Comments"] = "changed"
            else:
                _node(vendor.tree, 176766)["Title"] = "wrong tree title"
        return response

    vendor.send = collateral
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial" and result.data["items"][0]["state"] == "uncertain"
    assert vendor.save_count == vendor.release_count == 1


def test_cancel_after_send_restart_recovers_with_gets_only(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    vendor.faults.add("cancel_after_save")
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    context.cancellation.clear()
    start = len(vendor.calls)
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    assert all(call[0] == "GET" for call in vendor.calls[start:])
    assert vendor.save_count == vendor.lock_count == vendor.release_count == 1


def test_native_auth_queries_and_exact_lock_protocol(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed"
    for method, url, headers, body in vendor.calls:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        assert headers["Authorization"] == "Bearer secret-jwt-token"
        if parsed.hostname == "app2.eboardsolutions.com":
            assert "Cookie" not in headers
        else:
            assert headers["Cookie"] == "simbli_session=secret-cookie"
        if parsed.path == TREE:
            assert query == {
                "sct": ["secret-token"],
                "endid": ["enc-did-secret"],
                "enmid": ["enc-meeting-secret"],
                "enuid": ["enc-user-secret"],
                "v": ["myview"],
            }
        elif parsed.path == DETAILS:
            assert set(query) == {"sct", "endid", "enmid", "enitemid", "enuid", "view", "stab"}
            assert query["stab"] == ["1"] and query["view"] == ["myview"]
        elif parsed.path == LOCK:
            assert headers["Content-Type"] == "application/json"
            assert json.loads(body) == {**vendor.lock_dto, "ItemID": "enc-selected"}
        elif parsed.path == RELEASE:
            assert query == {"sct": ["secret-token"]}
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            assert parse_qs(body.decode())["Access"] == ["true"]


@pytest.mark.parametrize("fault", ["cycle", "nonfinite"])
def test_direct_prepared_unserializable_input_never_sends(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    adapter = SimbliWriteAdapter(vendor)
    prepared = adapter.prepare(
        Source(**SOURCE), WriteChange.from_dict(CHANGE), context, Bounds(**BOUNDS), monotonic() + 5
    )
    if fault == "cycle":
        prepared["loop"] = prepared
    else:
        prepared["number"] = float("nan")
    count = len(vendor.calls)
    with pytest.raises(ValueError):
        adapter.apply(Source(**SOURCE), prepared, context, Bounds(**BOUNDS), monotonic() + 5)
    assert len(vendor.calls) == count


@pytest.mark.parametrize("stage", ["before_lock", "after_lock"])
def test_current_application_grant_revocation(tmp_path, stage):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def revoke(url, **kwargs):
        response = send(url, **kwargs)
        route = urlsplit(url).path
        if (stage == "before_lock" and route == DETAILS) or (stage == "after_lock" and route == LOCK):
            context.authorization = frozenset({"write:plan"})
        return response

    vendor.send = revoke
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "failed" and vendor.save_count == 0
    assert vendor.release_count == (stage == "after_lock")


def test_page_and_native_identifiers_rotate_without_persisting_controls(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.details["CommentViewDTO"]["DummyObj"]["MeetingID"] = "enc-meeting-secret"
    prepared = plan(engine, context)
    vendor.rotate_selected()
    page = vendor.page
    vendor.page = lambda *args: page(*args).replace("enc-meeting-secret", "rotated-meeting-control")
    vendor.details["CommentViewDTO"]["DummyObj"]["MeetingID"] = "rotated-meeting-control"
    vendor.tree = json.loads(json.dumps(vendor.tree).replace("ROOT-SENTINEL==", "rotated-root"))
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "completed", result.public_dict()
    durable = safe(prepared.public_dict()) + safe(result.public_dict())
    for control in ["enc-selected", "enc-rotated", "rotated-root", "rotated-meeting-control"]:
        assert control not in durable
        assert control.encode() not in (tmp_path / "write.sqlite").read_bytes()


def test_credential_reflection_in_business_text_rejected(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.details["ItemContents"][0]["Content"] = "enc-meeting-secret"
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed" and not posts(vendor)
    safe(result.public_dict())


def test_empty_lock_session_rejected_and_short_jwt_component_not_a_business_secret(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.lock_dto["SessionID"] = ""
    result = engine.execute(
        "plan_write", {"source": SOURCE, "changes": [CHANGE], "bounds": bounds()}, context=context
    )
    assert result.status == "failed" and not posts(vendor)
    vendor.lock_dto["SessionID"] = "session-secret"
    context.credentials["simbli"]["token"] = "abc.def.ghi"
    vendor.details["ItemContents"][0]["Content"] = "abc"
    vendor.details["ItemDetails"]["WIPComment"] = vendor.lock_dto["LastActivity"]
    assert plan(engine, context).status == "completed"


def test_uncertain_save_with_unchanged_state_never_replays(tmp_path):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def no_acknowledgment(url, **kwargs):
        if urlsplit(url).path == SAVE:
            vendor.calls.append((kwargs["method"], url, kwargs["headers"], kwargs["body"]))
            vendor.save_count += 1
            raise TimeoutError()
        return send(url, **kwargs)

    vendor.send = no_acknowledgment
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert vendor.save_count == vendor.lock_count == vendor.release_count == 1


def test_matching_title_without_durable_mutation_marker_is_not_success(tmp_path):
    engine, context, vendor = setup(tmp_path)
    adapter = SimbliWriteAdapter(vendor)
    prepared = adapter.prepare(
        Source(**SOURCE), WriteChange.from_dict(CHANGE), context, Bounds(**BOUNDS), monotonic() + 5
    )
    vendor.details["ItemDetails"]["Title"] = CHANGE["fields"]["title"]
    _node(vendor.tree, 176766)["Title"] = "II. " + CHANGE["fields"]["title"]
    result = adapter.reconcile(Source(**SOURCE), prepared, {}, context, Bounds(**BOUNDS), monotonic() + 5)
    assert result["state"] == "uncertain" and not posts(vendor)


@pytest.mark.parametrize("status", [401, 500])
def test_denied_save_after_attempt_is_uncertain(tmp_path, status):
    engine, context, vendor = setup(tmp_path)
    prepared = plan(engine, context)
    send = vendor.send

    def denied(url, **kwargs):
        response = send(url, **kwargs)
        return WriteResponse(status, response.content) if urlsplit(url).path == SAVE else response

    vendor.send = denied
    result = engine.execute("commit_write", approval(prepared), context=context)
    assert result.status == "partial"
    assert result.data["items"][0]["mutation_attempted"] is True
    assert result.data["items"][0]["resource_id"] == "176766"
    assert vendor.release_count == 1
