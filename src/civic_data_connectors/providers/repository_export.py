"""Bounded owned-task lifecycle shared by Repository exports and searches."""

import json
from time import monotonic
from urllib.parse import urlencode

from .account_api import reject_credential_echo


def run_task(repository_root, start_url, task_type, body, bounds, context, transport, deadline, coverage,
             consume, *, cleanup_completed=False, coverage_key="export_task"):
    token = context.credentials["laserfiche_token"]
    state = {"status": "not_started", "terminal_confirmed": False, "polls": 0,
             "cancellation_requested": False, "cancellation_confirmed": False}
    coverage[coverage_key] = state
    task_id = None
    byte_budget = min(bounds.parser_bytes, bounds.transfer_bytes)
    cleanup_bytes = min(16384, byte_budget // 4)
    remaining_bytes = byte_budget - cleanup_bytes
    reserve = min(3.0, bounds.deadline_seconds / 5)
    poll_deadline = deadline - reserve

    def read(url, *, method="GET", request_body=None, expected=200, end=None, cleanup=False,
             capture_late_ownership=False, raw=False):
        nonlocal remaining_bytes, cleanup_bytes
        end = end if end is not None else deadline if cleanup else poll_deadline
        remaining = end - monotonic()
        limit = cleanup_bytes if cleanup else remaining_bytes
        if remaining <= 0 or limit <= 0:
            raise ValueError("Export task exhausted its read bounds.")
        if cleanup:
            cleanup_bytes = 0
        else:
            remaining_bytes = 0  # An interrupted transfer may have consumed its allowance.
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        if request_body is not None:
            headers["Content-Type"] = "application/json"
            state["status"] = "start_unconfirmed"
        response = transport.request(url, method=method, body=request_body, headers=headers,
            byte_limit=limit, deadline_seconds=remaining, allowed_origins=("https://api.laserfiche.com",),
            allow_redirects=False)
        leftover = limit - min(len(response.content), limit)
        if cleanup:
            cleanup_bytes = leftover
        else:
            remaining_bytes = leftover
        if (response.status != expected or response.url != url or len(response.content) > limit
                or (monotonic() >= end and not capture_late_ownership)):
            raise ValueError("Export task response did not meet its bounded contract.")
        reject_credential_echo(response.content, {"token": token})
        block = json.loads(response.content)
        if not isinstance(block, dict):
            raise ValueError("Export task requires a JSON object.")
        return (block, response) if raw else block

    def task(block):
        rows = block.get("value")
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                or rows[0].get("id") != task_id or rows[0].get("taskType") != task_type):
            raise ValueError("Only the exact owned Repository task may be observed.")
        row = rows[0]
        status = row.get("status")
        if status not in {"NotStarted", "InProgress", "Completed", "Failed", "Cancelled"}:
            raise ValueError("Unknown export task state.")
        state["status"] = status
        state["terminal_confirmed"] = status in {"Completed", "Failed", "Cancelled"}
        state["cancellation_confirmed"] = status == "Cancelled"
        return row

    try:
        if context.check_cancelled():
            raise InterruptedError()
        started = read(start_url, method="POST", request_body=json.dumps(body).encode(),
                       expected=202, end=poll_deadline, capture_late_ownership=True)
        task_id = started.get("taskId")
        if (not isinstance(task_id, str) or not task_id or len(task_id) > 512
                or any(ord(char) < 33 or ord(char) == 127 for char in task_id)):
            task_id = None
            state["status"] = "start_unconfirmed"
            raise ValueError("Export task reference was not returned safely.")
        state.update({"task_id": task_id, "status": "NotStarted"})
        tasks_url = repository_root + "/Tasks?" + urlencode({"taskIds": task_id})
        for _ in range(bounds.max_pages):
            if context.check_cancelled():
                raise InterruptedError()
            row = task(read(tasks_url, end=poll_deadline))
            state["polls"] += 1
            if context.check_cancelled():
                raise InterruptedError()
            if row.get("errors") or row["status"] in {"Failed", "Cancelled"}:
                raise ValueError("The export task did not complete successfully.")
            if row["status"] == "Completed":
                result = row.get("result")
                if not isinstance(result, dict):
                    raise ValueError("Repository task result is invalid.")
                return consume(result, task_id, read)
            context.report(stage="repository_search" if task_type == "SearchEntry" else "repository_export",
                           task_id=task_id, status=row["status"], polls=state["polls"])
            # Long polling normally waits server-side; avoid a tight loop when it returns immediately.
            context.cancellation.wait(min(0.1, max(0, poll_deadline - monotonic())))
        raise ValueError("The export task exceeded its poll bound.")
    finally:
        if task_id and (not state["terminal_confirmed"] or cleanup_completed):
            state["cancellation_requested"] = True
            try:
                cancelled = read(tasks_url, method="DELETE", cleanup=True)
                rows = cancelled.get("value")
                state["cancellation_accepted"] = bool(isinstance(rows, list) and len(rows) == 1
                    and isinstance(rows[0], dict) and rows[0].get("id") == task_id
                    and rows[0].get("taskType") == task_type and rows[0].get("result") is True)
                # Acknowledgement alone is not terminal evidence.
                task(read(tasks_url, cleanup=True))
            except Exception:
                state["cleanup_unconfirmed"] = True
            if not state["terminal_confirmed"] or (cleanup_completed and not state["cancellation_confirmed"]):
                state["cleanup_unconfirmed"] = True
                state["next_action"] = "Check this exact task and confirm its terminal status before considering cleanup complete."


def export_async(citation, body, bounds, context, transport, deadline, coverage):
    def consume(result, task_id, read):
        if "entryId" in result and (type(result["entryId"]) is not int
                                    or str(result["entryId"]) != citation.rsplit("/", 1)[1]):
            raise ValueError("Export task result does not match the selected document.")
        return result.get("uri")

    return run_task(citation.split("/Entries/", 1)[0], citation + "/ExportAsync", "ExportEntry", body,
                    bounds, context, transport, deadline, coverage, consume)
