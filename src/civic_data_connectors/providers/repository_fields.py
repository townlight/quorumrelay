"""Assigned entry field values, using the pinned Repository v2 ListFields route."""

import base64
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic

from ..engine import canonical_hash
from .account_api import reject_credential_echo
from .repository import _page_url


def requested(source):
    value = source.options.get("repository_include_fields", False)
    if type(value) is not bool:
        raise ValueError("repository_include_fields must be a JSON boolean.")
    return value


def captured_fields(record, rows):
    """Preserve original field objects, including absence/null/unknown values."""
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Repository fields require a supplied object list.")
    record["normalized"]["repository_fields"] = deepcopy(rows)
    record["normalized_sha256"] = canonical_hash(record["normalized"])


class FieldReader:
    """One operation's cumulative field budget; task searches inject their shared read."""

    def __init__(self, source, bounds, context, transport, deadline, *, read=None):
        self.source, self.bounds, self.context = source, bounds, context
        self.transport, self.deadline, self.shared_read = transport, deadline, read
        self.remaining = min(bounds.parser_bytes, bounds.transfer_bytes)
        self.states, self.failures = [], []

    def read(self, url):
        if self.context.check_cancelled():
            raise InterruptedError()
        if self.shared_read:
            return self.shared_read(url, raw=True)
        seconds = self.deadline - monotonic()
        if self.remaining <= 0 or seconds <= 0:
            raise ValueError("Field retrieval exhausted its byte/deadline bound.")
        limit, self.remaining = self.remaining, 0
        response = self.transport.request(url, headers={"Accept": "application/json",
            "Authorization": "Bearer " + self.context.credentials["laserfiche_token"]},
            byte_limit=limit, deadline_seconds=seconds, allowed_origins=("https://api.laserfiche.com",),
            allow_redirects=False)
        self.remaining = limit - min(limit, len(response.content))
        if (response.url != url or response.status != 200 or len(response.content) > limit
                or monotonic() >= self.deadline):
            raise ValueError("Field response violated its bounded exact-route contract.")
        reject_credential_echo(response.content, {"token": self.context.credentials["laserfiche_token"]})
        block = json.loads(response.content)
        if not isinstance(block, dict):
            raise ValueError("Field response must be a JSON object.")
        return block, response

    def enrich(self, record, bundle):
        base = record["normalized"]["url"] + "/Fields"
        state = {"external_id": record["identity"]["external_id"], "complete": False,
                 "pages": 0, "returned_fields": 0, "truncated": False,
                 "snapshot_consistency": "not_guaranteed", "failures": []}
        self.states.append(state)
        rows, provenance, seen, names, visited, total = [], [], set(), set(), set(), None
        url = base
        try:
            while url and state["pages"] < self.bounds.max_pages:
                if self.context.check_cancelled():
                    raise InterruptedError()
                url = _page_url(base, url)
                if url in visited:
                    raise ValueError("Field pagination repeated a URL.")
                visited.add(url)
                block, response = self.read(url)
                if self.context.check_cancelled():
                    raise InterruptedError()
                page = block.get("value")
                if not isinstance(page, list) or len(page) > 150:
                    raise ValueError("Invalid field collection.")
                keys, page_names = [], []
                for field in page:
                    if (not isinstance(field, dict) or not isinstance(field.get("name"), str)
                            or not field["name"] or (field.get("values") is not None
                            and (not isinstance(field["values"], list)
                                 or any(not isinstance(value, str) for value in field["values"])))
                            or ("hasMoreValues" in field and type(field["hasMoreValues"]) is not bool)
                            or ("id" in field and (type(field["id"]) is not int or field["id"] < 0))):
                        raise ValueError("Invalid assigned field metadata.")
                    key = field.get("id", field["name"].casefold())
                    name = field["name"].casefold()
                    if key in seen or key in keys or name in names or name in page_names:
                        raise ValueError("Field collection repeated its identity.")
                    keys.append(key)
                    page_names.append(name)
                count = block.get("@odata.count")
                if count is not None:
                    if type(count) is not int or count < len(rows) + len(page) or (total is not None and total != count):
                        raise ValueError("Invalid or unstable field count.")
                    total = count
                next_url = block.get("@odata.nextLink")
                if next_url is not None:
                    next_url = _page_url(base, next_url)
                    if next_url in visited:
                        raise ValueError("Field continuation cycled.")
                if len(rows) + len(page) > self.bounds.max_records:
                    state["truncated"] = True
                selected = page[:max(0, self.bounds.max_records - len(rows))]
                rows.extend(deepcopy(selected))
                seen.update(keys)
                names.update(page_names)
                state["pages"] += 1
                capture = {"source_url": self.source.url, "retrieval_url": response.url,
                    "input_format": "laserfiche-repository-fields-json",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(response.content).hexdigest(), "byte_length": len(response.content),
                    "content_type": response.content_type, "original_values": block,
                    "content_base64": base64.b64encode(response.content).decode("ascii")}
                bundle.setdefault("captures", []).append(capture)
                provenance.extend({"field_index": len(rows) - len(selected) + index,
                    "field_id": value.get("id"), "field_name": value["name"],
                    "capture_sha256": capture["sha256"], "citation_url": record["normalized"]["url"],
                    "retrieval_url": response.url} for index, value in enumerate(selected))
                url = next_url
                if state["truncated"] or (url and len(rows) >= self.bounds.max_records):
                    state["truncated"] = True
                    break
            state["truncated"] = state["truncated"] or bool(url)
            if total is not None and not url and len(rows) != total:
                raise ValueError("Field collection ended before its declared count.")
            # Missing hasMoreValues is unknown; never promote a listing's first
            # value, a null, or absent metadata into a complete-field claim.
            state["complete"] = not state["truncated"] and all(row.get("hasMoreValues") is False for row in rows)
            if not state["complete"]:
                state["failures"].append("field_values_incomplete")
        except InterruptedError:
            state["cancelled"] = True
            raise
        except Exception:
            state["failures"].append("field_metadata_unavailable")
        finally:
            state["returned_fields"] = len(rows)
            if rows or state["complete"]:
                captured_fields(record, rows)
            record.setdefault("extensions", {})["repository_field_coverage"] = deepcopy(state)
            record["extensions"]["repository_field_provenance"] = provenance
            self.failures.extend({"reason": reason, "external_id": state["external_id"]}
                                 for reason in state["failures"])
        return state
