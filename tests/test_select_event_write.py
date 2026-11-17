"""Synthetic exact native Select PUT contract; no inferred clock conversions."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import pytest

from quorumrelay import Engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers.select_event_write import contract
import test_civicclerk_section_write as section

BEFORE = {"id": 7, "eventName": "Before", "eventDescription": None,
    "eventDate": "2026-11-15T00:00:00", "startDateTime": "2026-11-15T18:30:00",
    "eventCategoryId": 3, "categoryId": 3, "eventTemplateId": 2, "agendaId": 11,
    "isPublished": 0, "publishStart": "0001-01-01T00:00:00", "startEventAutomatically": False,
    "streamId": 0, "externalMediaUrl": None, "actualStartTime": "2026-11-15T18:30:00",
    "meetingEndTime": "2026-11-15T20:00:00", "eventLocation": {"id": 91, "eventId": 7,
        "address1": "1 Main", "address2": None, "city": "Town", "state": "CO", "zipCode": "80501"}}
BODY = {"eventName": "After", "eventDescription": "Source description", "eventStartDate": "2026-11-15T00:00:00",
    "eventStartTime": "6:30:00 PM", "address1": "1 Main", "address2": None, "city": "Town", "state": "CO",
    "zipCode": "80501", "startEventAutomatically": False, "streamId": 0, "eventCategoryId": 3,
    "isPublished": 0, "publishStart": "0001-01-01T00:00:00", "externalMediaUrl": None,
    "actualStartTime": "6:30:00 PM", "meetingEndTime": "8:00:00 PM"}
EXPECTED = {**BEFORE, "eventName": "After", "eventDescription": "Source description"}
CHANGE = {"key": "native-event", "entity": "event", "operation": "update", "resource_id": 7, "meeting_id": "7",
    "fields": {"native_request": BODY, "expected_readback": EXPECTED}}


class Vendor:
    mock = True

    def __init__(self):
        self.value = deepcopy(BEFORE)
        self.calls = []
        self.lose = False
        self.mismatch = False
        self.success_status = 204

    def send(self, url, **kwargs):
        assert url == section.ORIGIN + "/v1/Events/7"
        assert kwargs["headers"]["Authorization"] == "Bearer private-test-token"
        method = kwargs["method"]
        self.calls.append(method)
        if method == "PUT":
            assert json.loads(kwargs["body"]) == BODY  # Native literals are sent without conversion/defaults.
            self.value["eventName"] = BODY["eventName"]
            self.value["eventDescription"] = BODY["eventDescription"]
            if self.mismatch:
                self.value["eventDate"] = "2026-11-16T00:00:00"
            if self.lose:
                raise OSError("response lost after send")
            return WriteResponse(self.success_status, b"")
        return WriteResponse(200, json.dumps(self.value).encode())


def setup(tmp_path):
    engine, caller, _ = section.setup(tmp_path)
    config = {**caller.credentials["civicplus-select"], "permissions": ["event:update"], "resource_ids": ["7"]}
    caller = replace(caller, credentials={"civicplus-select": config})
    vendor = Vendor()
    engine = Engine(storage=engine.storage)
    register(engine, default_adapters(vendor))
    return engine, caller, vendor


def test_pinned_request_and_read_models_are_reproducible():
    path = Path(__file__).resolve().parents[1] / "scripts/pin_select_event_contract.py"
    spec = importlib.util.spec_from_file_location("select_pin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.compile_contract() == contract()
    assert len(contract()["models"]) == 9


@pytest.mark.parametrize("status", [200, 204])
def test_exact_update_full_readback_reopen_and_receipt(tmp_path, status):
    engine, caller, vendor = setup(tmp_path)
    vendor.success_status = status
    approval = section.plan(engine, caller, CHANGE)
    assert vendor.calls == ["GET"]
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"] == EXPECTED
    assert vendor.calls == ["GET", "GET", "PUT", "GET"]
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=caller).status == "completed"
    assert vendor.calls == ["GET", "GET", "PUT", "GET"]
    receipt = reopened.execute("receipt", {"plan_id": approval["plan_id"]}, context=caller)
    assert "private-test-token" not in json.dumps(receipt.public_dict())


@pytest.mark.parametrize("case", ["missing", "unknown", "bool_enum", "int32", "date", "null_name", "empty_time",
    "publish", "stream", "template", "unrelated", "location_identity", "location_value", "expected_id",
    "expected_unknown", "expected_shape", "create", "meeting", "parent", "version", "denied", "bound"])
def test_native_validation_authorization_and_preservation_reject_without_put(tmp_path, case):
    engine, caller, vendor = setup(tmp_path)
    change = deepcopy(CHANGE)
    body, expected = change["fields"]["native_request"], change["fields"]["expected_readback"]
    if case == "missing":
        body.pop("actualStartTime")
    elif case == "unknown":
        body["unverified"] = True
    elif case == "bool_enum":
        body["isPublished"] = False
    elif case == "int32":
        body["eventCategoryId"] = 2 ** 31
    elif case == "date":
        body["eventStartDate"] = "2026-11-15"
    elif case == "null_name":
        body["eventName"] = None
    elif case == "empty_time":
        body["eventStartTime"] = ""
    elif case == "publish":
        body["isPublished"] = expected["isPublished"] = 1
    elif case == "stream":
        body["streamId"] = expected["streamId"] = 8
    elif case == "template":
        expected["eventTemplateId"] = 9
    elif case == "unrelated":
        expected["agendaId"] = 13
    elif case == "location_identity":
        expected["eventLocation"]["id"] = 92
    elif case == "location_value":
        body["city"] = "Elsewhere"
    elif case == "expected_id":
        expected["id"] = 8
    elif case == "expected_unknown":
        expected["unknown"] = 3
    elif case == "expected_shape":
        expected.pop("agendaId")
    elif case == "create":
        change["operation"] = "create"
    elif case == "meeting":
        change["meeting_id"] = "8"
    elif case == "parent":
        change["parent_id"] = 11
    elif case == "version":
        change["expected_version"] = "stale"
    elif case == "denied":
        caller = replace(caller, allowed_namespaces=frozenset())
    result = engine.execute("plan_write", {"source": section.SOURCE, "changes": [change],
        **({"bounds": {"parser_bytes": 64}} if case == "bound" else {})}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert "PUT" not in vendor.calls


@pytest.mark.parametrize("case", ["conflict", "loss", "mismatch"])
def test_conflict_and_uncertainty_reconcile_without_second_put(tmp_path, case):
    engine, caller, vendor = setup(tmp_path)
    approval = section.plan(engine, caller, CHANGE)
    if case == "conflict":
        vendor.value["eventDescription"] = "Concurrent edit"
    else:
        setattr(vendor, "lose" if case == "loss" else "mismatch", True)
    result = engine.execute("commit_write", approval, context=caller)
    if case == "conflict":
        assert result.status == "failed" and "PUT" not in vendor.calls
        return
    assert result.status == "partial" and result.data["items"][0]["state"] == "uncertain"
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=caller)
    assert result.status == ("completed" if case == "loss" else "partial"), result.public_dict()
    assert vendor.calls.count("PUT") == 1
