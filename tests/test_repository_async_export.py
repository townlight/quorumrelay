"""Owned asynchronous export lifecycle using pinned vendor task response shapes."""

import base64
import json

import pytest

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response
from test_repository_content import DOWNLOAD, PDF, ExportTransport
from test_repository_discovery import BASE, context, entry
from test_repository_fetch import ENTRY_URL

TASK_ID = "synthetic-export-task-71"
TASK_URL = ENTRY_URL.split("/Entries/", 1)[0] + "/Tasks?taskIds=" + TASK_ID


class AsyncTransport(ExportTransport):
    def __init__(self, states=None, *, on_poll=None, cleanup_state="Cancelled", malformed=None):
        super().__init__()
        self.states = list(states or ["InProgress", "Completed"])
        self.on_poll, self.cleanup_state, self.malformed = on_poll, cleanup_state, malformed
        self.stopped = False

    def request(self, url, **kwargs):
        if url in {ENTRY_URL + "/ExportAsync", TASK_URL}:
            self.calls.append((url, kwargs))
            assert kwargs["allow_redirects"] is False
            assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
            assert kwargs["allowed_origins"] == ("https://api.laserfiche.com",)
            if url.endswith("/ExportAsync"):
                assert kwargs["method"] == "POST" and json.loads(kwargs["body"]) == {"part": "Edoc"}
                block = {"taskId": TASK_ID}
                if self.malformed == "start":
                    block = {"unexpected": True}
                return Response(url, json.dumps(block).encode(), "application/json", 202)
            if kwargs["method"] == "DELETE":
                self.stopped = True
                return Response(url, json.dumps({"value": [{"id": TASK_ID, "taskType": "ExportEntry", "result": True}]}).encode(),
                                "application/json")
            if self.on_poll and not self.stopped:
                self.on_poll()
            status = self.cleanup_state if self.stopped else self.states.pop(0) if len(self.states) > 1 else self.states[0]
            row = {"id": TASK_ID, "taskType": "ExportEntry", "status": status,
                   "result": {"entryId": 71, "uri": DOWNLOAD}, "errors": []}
            if not self.stopped:
                if self.malformed == "identity":
                    row["id"] = "different-task"
                elif self.malformed == "type":
                    row["taskType"] = "DeleteEntry"
                elif self.malformed == "entry":
                    row["result"]["entryId"] = 72
                elif self.malformed == "errors":
                    row["errors"] = [{"detail": "private-download"}]
                elif self.malformed == "echo":
                    row["echo"] = "secret-read-token"
                elif self.malformed == "no_uri":
                    row["result"] = {}
            return Response(url, json.dumps({"value": [row]}).encode(), "application/json")
        return super().request(url, **kwargs)


def fetch_async(transport, *, bounds=None, caller=None, option=True):
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json", options={
        "download_origins": ["https://files.example.org"], "repository_export_async": option})
    owner = create_engine(provider_transport=transport)
    capture = json.dumps(entry(71)).encode()
    normalized = owner.normalize(source, capture, input_format=source.input_format)
    assert normalized.status == "completed", normalized.public_dict()
    return owner.fetch_attachment(source, normalized.data["records"][0], capture=capture,
                                  bounds=bounds, context=caller or context())


def test_repository_async_export_wait_download_and_safe_task_receipt():
    transport = AsyncTransport()
    result = fetch_async(transport)
    assert result.status == "completed", result.public_dict()
    assert base64.b64decode(result.data["attachment"]["content_base64"]) == PDF
    state = result.coverage["export_task"]
    assert state["task_id"] == TASK_ID and state["status"] == "Completed"
    assert state["terminal_confirmed"] and state["polls"] == 2
    assert not state["cancellation_requested"]
    assert sum(url == DOWNLOAD for url, _ in transport.calls) == 1
    assert not any(call.get("method") == "DELETE" for _, call in transport.calls)
    assert "private-download" not in json.dumps(result.public_dict())
    assert "secret-read-token" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("malformed", ["start", "identity", "type", "entry", "errors", "echo", "no_uri"])
def test_repository_async_rejects_wrong_task_or_result_without_download(malformed):
    transport = AsyncTransport(["Completed"], malformed=malformed)
    result = fetch_async(transport)
    assert result.status == "partial", result.public_dict()
    assert result.data["record"]["identity"]["external_id"] == "71" and result.data["attachment"] is None
    assert not any(url == DOWNLOAD for url, _ in transport.calls)
    assert "private-download" not in json.dumps(result.public_dict())
    assert "secret-read-token" not in json.dumps(result.public_dict())


def test_repository_async_poll_bound_cancels_exact_task_and_checks_terminal_state():
    transport = AsyncTransport(["InProgress"])
    result = fetch_async(transport, bounds=Bounds(max_pages=1))
    assert result.status == "partial", result.public_dict()
    state = result.coverage["export_task"]
    assert state["cancellation_requested"] and state["cancellation_accepted"]
    assert state["cancellation_confirmed"] and state["terminal_confirmed"]
    assert [url for url, call in transport.calls if call.get("method") == "DELETE"] == [TASK_URL]
    assert not any(url == DOWNLOAD for url, _ in transport.calls)


def test_repository_async_cancellation_keeps_terminal_verification_separate_from_ack():
    caller = context()
    transport = AsyncTransport(["InProgress"], on_poll=caller.cancellation.set, cleanup_state="InProgress")
    result = fetch_async(transport, caller=caller)
    assert result.status == "cancelled", result.public_dict()
    state = result.coverage["export_task"]
    assert state["cancellation_accepted"] and not state["cancellation_confirmed"]
    assert not state["terminal_confirmed"]
    assert state["cleanup_unconfirmed"] and state["next_action"]
    assert not any(url == DOWNLOAD for url, _ in transport.calls)


@pytest.mark.parametrize("status", ["Failed", "Cancelled"])
def test_repository_async_terminal_failure_is_not_retried_or_downloaded(status):
    transport = AsyncTransport([status])
    result = fetch_async(transport)
    assert result.status == "partial" and result.coverage["export_task"]["terminal_confirmed"]
    assert not any(url == DOWNLOAD or call.get("method") == "DELETE" for url, call in transport.calls)


@pytest.mark.parametrize("option", [1, "true", None])
def test_repository_async_flag_requires_boolean_without_network(option):
    transport = AsyncTransport()
    assert fetch_async(transport, option=option).status == "failed"
    assert not transport.calls


def test_repository_async_transport_timeout_retains_cleanup_budget():
    class PollTimeout(AsyncTransport):
        def request(self, url, **kwargs):
            if url == TASK_URL and kwargs["method"] == "GET" and not self.stopped:
                self.calls.append((url, kwargs))
                raise TimeoutError("private-download must not escape")
            return super().request(url, **kwargs)

    transport = PollTimeout()
    result = fetch_async(transport)
    assert result.status == "partial" and result.coverage["export_task"]["cancellation_confirmed"]
    assert "private-download" not in json.dumps(result.public_dict())


def test_repository_async_late_start_retains_owned_task_for_cleanup(monkeypatch):
    from civic_data_connectors.providers import repository, repository_export

    clock = [0.0]
    monkeypatch.setattr(repository, "monotonic", lambda: clock[0])
    monkeypatch.setattr(repository_export, "monotonic", lambda: clock[0])

    class LateStart(AsyncTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if url.endswith("/ExportAsync"):
                clock[0] = 43.0  # Beyond the polling allowance, inside the cleanup reserve.
            return response

    transport = LateStart()
    result = fetch_async(transport, bounds=Bounds(deadline_seconds=45))
    assert result.status == "partial"
    state = result.coverage["export_task"]
    assert state["task_id"] == TASK_ID and state["cancellation_confirmed"]
    assert not any(url == DOWNLOAD for url, _ in transport.calls)
