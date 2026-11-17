"""Current Boardable Agenda Builder item create/update and attachment upload.

This adapter is selected only by an explicit trusted
``current_agenda_builder=True`` Boardable credential. It deliberately does not
implement submit/publish/template/invite/owner-change/delete workflows.
"""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re
from time import monotonic
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse

API_ROOT = "https://app.boardable.com/api/agenda-approvals"
ITEM_FIELD_NAMES = {"text", "description", "duration", "is_private"}
DOWNLOAD_SEGMENT = "agenda/uploads/download/"


def _bounded_id(value, label="native ID"):
    if type(value) is int and 0 < value < 10 ** 19:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
        return int(value)
    raise ValueError(f"A bounded positive {label} is required.")


def _safe_header_value(value):
    return (isinstance(value, str) and 0 < len(value) <= 16384
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _safe_filename(value):
    if (not isinstance(value, str) or not value or len(value) > 255 or value != value.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(c in '\\/:*?"<>|' for c in value) or ".." in value):
        raise ValueError("Unsafe attachment filename.")
    return value


def _safe_mime(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", value):
        raise ValueError("Unsafe attachment MIME type.")
    return value


def _private(value):
    if type(value) is bool:
        return value
    if type(value) is int and value in {0, 1}:
        return bool(value)
    raise ValueError("is_private must be boolean or 0/1.")


def _owner_id(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("The item owner shape is ambiguous.")
    return _bounded_id(value.get("id"), "owner ID")


def _approval_tree_id(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("The approval tree shape is ambiguous.")
    return _bounded_id(value.get("id"), "approval tree ID")


def _presenters(value):
    if not isinstance(value, list):
        raise ValueError("The presenters field must be a list.")
    result = []
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Presenter rows must be objects.")
        result.append(_bounded_id(row.get("id"), "presenter ID"))
    if len(result) != len(set(result)):
        raise ValueError("The item repeats a presenter identity.")
    return result


class BoardableBuilderWriteAdapter(WriteAdapter):
    """Current Boardable agenda item and attachment upload mapping."""

    def __init__(self, transport=None):
        super().__init__("boardable", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        if not isinstance(config, dict):
            raise WriteFailure("credentials_required", "Trusted Boardable current-builder credentials are required.")
        if config.get("current_agenda_builder") is not True or config.get("legacy_agenda_editor") is True:
            raise WriteFailure("permission_denied", "Select current_agenda_builder or legacy_agenda_editor, never both.")
        parsed = urlsplit(source.url)
        if (not context.tenant or config.get("tenant") != context.tenant
                or config.get("org_url") != source.url
                or parsed.scheme != "https" or parsed.netloc != "app.boardable.com"
                or parsed.query or parsed.fragment or parsed.username or parsed.password
                or not re.fullmatch(r"/(?:[A-Za-z0-9_-]{1,128}/){1,5}", parsed.path)):
            raise WriteFailure("permission_denied", "An exact trusted app.boardable.com organization root is required.")
        if (not source.namespace or source.namespace not in config.get("allowed_namespaces", ())
                or (context.allowed_namespaces is not None
                    and source.namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "The Boardable namespace is outside current policy.")
        org = config.get("organization_id")
        if type(org) is int:
            org = str(org)
        if not isinstance(org, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", org):
            raise WriteFailure("credentials_required", "An exact numeric Boardable organization ID is required.")
        cookie = config.get("session_cookie")
        if (not _safe_header_value(cookie)
                or not re.fullmatch(r"[A-Za-z0-9_-]+=[^;,\s]+(?:; [A-Za-z0-9_-]+=[^;,\s]+)*", cookie)):
            raise WriteFailure("credentials_required", "A safe Boardable session cookie is required.")
        csrf = config.get("csrf_token")
        if csrf is not None and not _safe_header_value(csrf):
            raise WriteFailure("credentials_required", "The configured Boardable CSRF header is unsafe.")
        meetings = config.get("meeting_ids")
        if not isinstance(meetings, (list, tuple, set, frozenset)) or not meetings:
            raise WriteFailure("permission_denied", "An explicit Boardable meeting allowlist is required.")
        normalized_meetings = []
        for meeting in meetings:
            meeting = str(meeting) if type(meeting) is int else meeting
            if not isinstance(meeting, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", meeting):
                raise WriteFailure("permission_denied", "The Boardable meeting allowlist is malformed.")
            normalized_meetings.append(meeting)
        permissions = config.get("permissions")
        if not isinstance(permissions, (list, tuple, set, frozenset)):
            raise WriteFailure("permission_denied", "Explicit Boardable permissions are required.")
        value = dict(config)
        value["_organization_id"] = org
        value["_meeting_ids"] = tuple(normalized_meetings)
        return value

    def validate_source(self, source, context):
        if source.provider != self.provider or source.options:
            raise ValueError("Only the exact current Boardable organization source without options is supported.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if change.entity != "item" or change.operation not in {"create", "update"}:
            raise WriteFailure("mapping_unverified", "Current Boardable supports item create/update only.")
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        if change.language is not None or change.page_number is not None:
            raise ValueError("Current Boardable item writes do not accept language/page_number.")
        meeting = str(change.meeting_id) if type(change.meeting_id) is int else change.meeting_id
        if not isinstance(meeting, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", meeting):
            raise ValueError("A bounded numeric meeting_id is required.")
        if meeting not in config["_meeting_ids"]:
            raise WriteFailure("permission_denied", "The meeting is outside the trusted Boardable allowlist.")
        if f"item:{change.operation}" not in config.get("permissions", ()):
            raise WriteFailure("permission_denied", "The Boardable item operation is outside current policy.")
        if not isinstance(change.fields, dict) or set(change.fields) - ITEM_FIELD_NAMES:
            raise ValueError("Current Boardable item fields are text/description/duration/is_private only.")
        if change.operation == "create":
            if change.resource_id is not None:
                raise ValueError("A create cannot reuse an existing item ID.")
            if type(change.parent_id) is not int or not 0 <= change.parent_id < 10 ** 19:
                raise ValueError("A create requires the original exact parent_id (0 for root).")
            if not isinstance(change.fields.get("text"), str) or not change.fields["text"].strip():
                raise ValueError("A new agenda item requires nonempty text.")
        else:
            _bounded_id(change.resource_id, "item ID")
            if change.parent_id is not None:
                raise ValueError("An item update cannot move its native parent.")
        for part in change.files:
            self._validate_part(part)

    def _validate_part(self, part):
        if not isinstance(part, dict) or set(part) != {"part", "filename", "content_type", "reference"}:
            raise ValueError("A file requires part, filename, content_type and one immutable reference.")
        if part["part"] != "file":
            raise ValueError("Current Boardable file parts must be named file.")
        _safe_filename(part["filename"])
        _safe_mime(part["content_type"])
        reference = part.get("reference")
        if not isinstance(reference, dict):
            raise ValueError("An immutable file reference is required.")
        length = reference.get("byte_length")
        digest = reference.get("sha256")
        if (type(length) is not int or length <= 0
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
            raise ValueError("A positive byte_length and SHA256 are required for files.")

    def _prepare_files(self, files, bounds):
        result = []
        total = 0
        names = set()
        for part in files:
            self._validate_part(part)
            filename = part["filename"]
            if filename in names:
                raise WriteFailure("ambiguous_filename", "Duplicate new attachment filenames are ambiguous.")
            names.add(filename)
            length = part["reference"]["byte_length"]
            total += length
            if total > bounds.transfer_bytes:
                raise ValueError("The submitted attachments exceed the transfer byte limit.")
            self._read_part(part)
            result.append(deepcopy(part))
        return result

    def _read_part(self, part):
        reference = part["reference"]
        length = reference["byte_length"]
        with self._open_file(part) as stream:
            data = stream.read(length + 1)
        if len(data) != length or hashlib.sha256(data).hexdigest() != reference["sha256"]:
            raise ValueError("The local attachment no longer matches its immutable digest/size.")
        return data

    def _meeting_id(self, change):
        value = change.meeting_id
        if type(value) is int:
            value = str(value)
        if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
            raise ValueError("A bounded numeric meeting_id is required.")
        return value

    def _headers(self, config, content_type=None):
        headers = {
            "Accept": "application/json",
            "Cookie": config["session_cookie"],
            "X-Requested-With": "XMLHttpRequest",
            "Organization": config["_organization_id"],
        }
        if config.get("csrf_token") is not None:
            headers["X-CSRF-TOKEN"] = config["csrf_token"]
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers

    def _send(self, url, method, body, headers, limit, deadline, context):
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The Boardable operation deadline expired.")
        try:
            response = self.transport.send(url, method=method, body=body, headers=headers,
                                           byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise AmbiguousWrite("Invalid or oversized Boardable response.")
        return response

    def _request_json(self, source, context, method, url, body, config, bounds, deadline, *,
                      content_type=None, expected_status=None):
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        headers = self._headers(config, content_type)
        response = self._send(url, method, body, headers, limit, deadline, context)
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "Boardable denied the operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "Boardable rejected a conflicting change.")
        if expected_status is not None and 200 <= response.status < 300 and response.status != expected_status:
            raise AmbiguousWrite(
                f"Boardable returned HTTP {response.status}; expected {expected_status} for this request."
            )
        if not 200 <= response.status < 300:
            if response.status >= 500 or response.status in {408, 429}:
                raise AmbiguousWrite()
            raise WriteFailure("provider_rejected", f"Boardable rejected the request (HTTP {response.status}).")
        try:
            value = json.loads(response.content)
        except (ValueError, UnicodeError):
            raise AmbiguousWrite("Boardable returned invalid JSON.") from None
        return sanitize(value, config)

    def _fetch_meeting(self, source, context, meeting_id, config, bounds, deadline):
        value = self._request_json(source, context, "GET", API_ROOT + "/meetings/" + meeting_id,
                                   None, config, bounds, deadline, expected_status=200)
        data = value.get("data") if isinstance(value, dict) else None
        if not isinstance(data, dict):
            raise WriteFailure("provider_response", "The Boardable meeting response is incomplete.")
        return data

    def _fetch_item(self, source, context, item_id, config, bounds, deadline):
        value = self._request_json(source, context, "GET", API_ROOT + "/agenda-items/" + str(item_id),
                                   None, config, bounds, deadline, expected_status=200)
        data = value.get("data") if isinstance(value, dict) else None
        if not isinstance(data, dict):
            raise WriteFailure("provider_response", "The Boardable item response is incomplete.")
        return data

    def _check_meeting(self, meeting, meeting_id):
        if _bounded_id(meeting.get("id"), "meeting ID") != int(meeting_id):
            raise WriteFailure("conflict", "Boardable returned a different meeting identity.")
        if meeting.get("needs_draft_preparation") is True:
            raise WriteFailure("mapping_unverified", "needs_draft_preparation=true is not mapped.")
        if meeting.get("can_manage_agenda") is not True:
            raise WriteFailure("permission_denied", "The trusted meeting does not permit agenda management.")

    def _create_fields(self, fields):
        text = fields.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("A new agenda item requires nonempty text.")
        description = fields.get("description", "")
        if not isinstance(description, str):
            raise ValueError("description must be a string.")
        duration = fields.get("duration", 0)
        if type(duration) is not int or not 0 <= duration <= 100000:
            raise ValueError("duration must be a bounded nonnegative integer.")
        return {"text": text, "description": description, "duration": duration,
                "is_private": _private(fields.get("is_private", False))}

    def _update_desired(self, fields, item):
        before_text = item.get("text")
        before_description = item.get("description")
        before_duration = item.get("duration")
        before_private = _private(item.get("is_private", False))
        text = fields.get("text", before_text)
        description = fields.get("description", before_description)
        duration = fields.get("duration", before_duration)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Item text must remain nonempty.")
        if not isinstance(description, str):
            raise ValueError("description must be a string.")
        if type(duration) is not int or not 0 <= duration <= 100000:
            raise ValueError("duration must be a bounded nonnegative integer.")
        private = _private(fields.get("is_private", before_private))
        range_value = item.get("durationRange")
        if isinstance(range_value, dict):
            minimum, maximum = range_value.get("min"), range_value.get("max")
            if type(minimum) is int and duration < minimum:
                raise ValueError("duration is below the native durationRange.min.")
            if type(maximum) is int and duration > maximum:
                raise ValueError("duration exceeds the native durationRange.max.")
        return {
            "text": text,
            "description": description,
            "duration": duration,
            "is_private": private,
            "owner_id": _owner_id(item.get("owner")),
            "approval_tree_id": _approval_tree_id(item.get("approval_tree")),
            "presenters": _presenters(item.get("presenters", [])),
        }

    def _upload_summary(self, value):
        if not isinstance(value, dict):
            raise ValueError("Attachment rows must be objects.")
        filename = value.get("filename")
        mime = value.get("mime_type")
        size = value.get("file_size")
        if not isinstance(filename, str) or not filename or len(filename) > 255:
            raise ValueError("Attachment filename is invalid.")
        if not isinstance(mime, str) or not re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", mime):
            raise ValueError("Attachment MIME type is invalid.")
        if type(size) is not int or size < 0:
            raise ValueError("Attachment file_size is invalid.")
        agenda_id = value.get("agenda_id")
        organization_id = value.get("organization_id")
        download_url = value.get("downloadUrl")
        if download_url is None:
            download_url = value.get("url")
        if download_url is not None and not isinstance(download_url, str):
            raise ValueError("Attachment download URL is invalid.")
        return {
            "id": _bounded_id(value.get("id"), "attachment ID"),
            "filename": filename,
            "mime_type": mime,
            "file_size": size,
            "agenda_id": agenda_id if type(agenda_id) is int else None,
            "organization_id": organization_id if type(organization_id) is int else None,
            "download_url": download_url,
        }

    def _uploads(self, value, bounds):
        if not isinstance(value, list) or len(value) > bounds.max_records:
            raise ValueError("The item uploads list is missing or exceeds bounds.")
        result, seen = [], set()
        for row in value:
            summary = self._upload_summary(row)
            if summary["id"] in seen:
                raise ValueError("The item repeats an attachment identity.")
            seen.add(summary["id"])
            result.append(summary)
        return result

    def _tree_relevant(self, rows, bounds, parent=0, depth=0, seen=None):
        if seen is None:
            seen = set()
        if not isinstance(rows, list) or depth > min(64, bounds.max_records):
            raise ValueError("The Boardable agenda tree is not bounded.")
        result = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("The Boardable agenda tree contains a non-object.")
            identity = _bounded_id(row.get("id"), "agenda item ID")
            if identity in seen or len(seen) >= bounds.max_records:
                raise ValueError("The Boardable agenda tree repeats an identity or exceeds bounds.")
            seen.add(identity)
            parent_field = row.get("parent_agenda_id", parent)
            if type(parent_field) is not int or parent_field != parent:
                raise ValueError("The Boardable agenda parent field conflicts with the nested tree.")
            children = row.get("children") if isinstance(row.get("children"), list) else row.get("agenda")
            uploads = row.get("uploads") or []
            if not isinstance(uploads, list) or len(uploads) > bounds.max_records:
                raise ValueError("The Boardable uploads list exceeds bounds.")
            result.append({
                "id": identity,
                "parent_agenda_id": parent,
                "text": row.get("text"),
                "description": row.get("description"),
                "duration": row.get("duration"),
                "is_private": _private(row.get("is_private", False)),
                "order": row.get("order"),
                "owner_id": _owner_id(row.get("owner")),
                "approval_tree_id": _approval_tree_id(row.get("approval_tree")),
                "presenters": _presenters(row.get("presenters", [])),
                "uploads": [self._upload_summary(u) for u in uploads],
                "children": self._tree_relevant(children, bounds, identity, depth + 1, seen)
                if children is not None else [],
            })
        return result

    def _tree_identity_map(self, rows, bounds, parent=0, depth=0, seen=None):
        if seen is None:
            seen = set()
        if not isinstance(rows, list) or depth > min(64, bounds.max_records):
            raise ValueError("The Boardable agenda tree is not bounded.")
        result = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("The Boardable agenda tree contains a non-object.")
            identity = _bounded_id(row.get("id"), "agenda item ID")
            if identity in seen or len(seen) >= bounds.max_records:
                raise ValueError("The Boardable agenda tree repeats an identity or exceeds bounds.")
            seen.add(identity)
            parent_field = row.get("parent_agenda_id", parent)
            if type(parent_field) is not int or parent_field != parent:
                raise ValueError("The Boardable agenda parent field conflicts with the nested tree.")
            children = row.get("children") if isinstance(row.get("children"), list) else row.get("agenda")
            uploads = row.get("uploads") or []
            if not isinstance(uploads, list) or len(uploads) > bounds.max_records:
                raise ValueError("The Boardable uploads list exceeds bounds.")
            upload_map = {}
            for upload in uploads:
                summary = self._upload_summary(upload)
                key = str(summary["id"])
                if key in upload_map:
                    raise ValueError("The Boardable agenda node repeats an attachment identity.")
                upload_map[key] = summary
            result[str(identity)] = {
                "id": identity,
                "parent_agenda_id": parent,
                "text": row.get("text"),
                "description": row.get("description"),
                "duration": row.get("duration"),
                "is_private": _private(row.get("is_private", False)),
                "order": row.get("order"),
                "owner_id": _owner_id(row.get("owner")),
                "approval_tree_id": _approval_tree_id(row.get("approval_tree")),
                "presenters": _presenters(row.get("presenters", [])),
                "uploads": upload_map,
            }
            if children is not None:
                result.update(self._tree_identity_map(children, bounds, identity, depth + 1, seen))
        return result

    def _meeting_relevant(self, meeting, bounds):
        return {
            "id": _bounded_id(meeting.get("id"), "meeting ID"),
            "owner_id": meeting.get("owner_id") if type(meeting.get("owner_id")) is int else None,
            "can_manage_agenda": meeting.get("can_manage_agenda"),
            "needs_draft_preparation": meeting.get("needs_draft_preparation"),
            "agenda_live_version": meeting.get("agenda_live_version"),
            "agenda_draft_version": meeting.get("agenda_draft_version"),
            "agenda_items": self._tree_relevant(meeting.get("agenda_items", []), bounds),
        }

    def _meeting_normalized(self, meeting, bounds):
        return {
            "id": _bounded_id(meeting.get("id"), "meeting ID"),
            "owner_id": meeting.get("owner_id") if type(meeting.get("owner_id")) is int else None,
            "can_manage_agenda": meeting.get("can_manage_agenda"),
            "needs_draft_preparation": meeting.get("needs_draft_preparation"),
            "agenda_live_version": meeting.get("agenda_live_version"),
            "agenda_draft_version": meeting.get("agenda_draft_version"),
            "agenda_items": self._tree_identity_map(meeting.get("agenda_items", []), bounds),
        }

    def _item_relevant(self, item, bounds):
        meeting = item.get("meeting")
        if not isinstance(meeting, dict):
            raise ValueError("The item meeting relationship is missing.")
        parent = item.get("parent_agenda_id")
        if type(parent) is not int:
            raise ValueError("The item parent identity is ambiguous.")
        uploads = self._uploads(item.get("uploads"), bounds)
        return {
            "id": _bounded_id(item.get("id"), "item ID"),
            "meeting_id": _bounded_id(meeting.get("id"), "meeting ID"),
            "parent_agenda_id": parent,
            "text": item.get("text"),
            "description": item.get("description"),
            "duration": item.get("duration") if type(item.get("duration")) is int else None,
            "is_private": _private(item.get("is_private", False)),
            "order": item.get("order"),
            "owner_id": _owner_id(item.get("owner")),
            "approval_tree_id": _approval_tree_id(item.get("approval_tree")),
            "presenters": _presenters(item.get("presenters", [])),
            "uploads": uploads,
        }

    def _item_normalized(self, item, bounds):
        value = self._item_relevant(item, bounds)
        value["uploads"] = {str(row["id"]): row for row in value["uploads"]}
        return value

    def _flatten_ids(self, rows, bounds, depth=0, seen=None):
        if seen is None:
            seen = set()
        if not isinstance(rows, list) or depth > min(64, bounds.max_records):
            raise ValueError("The Boardable agenda tree is not bounded.")
        result = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("The Boardable agenda tree contains a non-object.")
            identity = _bounded_id(row.get("id"), "agenda item ID")
            if identity in seen or len(seen) >= bounds.max_records:
                raise ValueError("The Boardable agenda tree repeats an identity or exceeds bounds.")
            seen.add(identity)
            result.add(identity)
            children = row.get("children") if isinstance(row.get("children"), list) else row.get("agenda")
            if children is not None:
                result |= self._flatten_ids(children, bounds, depth + 1, seen)
        return result

    def _find_nodes(self, rows, identity, parent=0, depth=0):
        if not isinstance(rows, list) or depth > 64:
            return []
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("id") == identity:
                result.append((row, parent))
            children = row.get("children") if isinstance(row.get("children"), list) else row.get("agenda")
            if children is not None:
                result.extend(self._find_nodes(children, identity, row.get("id"), depth + 1))
        return result

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        config = self.credentials(source, context)
        meeting_id = self._meeting_id(change)
        files = self._prepare_files(change.files, bounds)
        if change.operation == "create":
            return self._prepare_create(source, change, context, bounds, deadline, config, meeting_id, files)
        return self._prepare_update(source, change, context, bounds, deadline, config, meeting_id, files)

    def _prepare_create(self, source, change, context, bounds, deadline, config, meeting_id, files):
        fields = self._create_fields(change.fields)
        owner_id = _bounded_id(config.get("owner_id"), "trusted owner ID")
        meeting = self._fetch_meeting(source, context, meeting_id, config, bounds, deadline)
        self._check_meeting(meeting, meeting_id)
        parents = self._flatten_ids(meeting.get("agenda_items", []), bounds)
        if change.parent_id and change.parent_id not in parents:
            raise WriteFailure("permission_denied", "The selected parent is not in the exact authorized meeting.")
        parent_id = change.parent_id if change.parent_id else 0
        if files:
            parts = [
                {"kind": "field", "name": "title", "value": fields["text"]},
                {"kind": "field", "name": "description", "value": fields["description"]},
                {"kind": "field", "name": "duration", "value": str(fields["duration"])},
                {"kind": "field", "name": "meeting_id", "value": meeting_id},
            ]
            if parent_id:
                parts.append({"kind": "field", "name": "parent_id", "value": str(parent_id)})
            parts.extend([
                {"kind": "field", "name": "owner_id", "value": str(owner_id)},
                {"kind": "field", "name": "is_private", "value": "1" if fields["is_private"] else "0"},
            ])
            for index, part in enumerate(files):
                parts.append({"kind": "field", "name": f"attachments[{index}][type]", "value": "upload"})
                parts.append({"kind": "file", "name": f"attachments[{index}][file]", "part": part})
            native = {"method": "POST", "url": API_ROOT + "/agenda-items", "multipart": parts, "files": files}
        else:
            body = {
                "title": fields["text"],
                "description": fields["description"],
                "duration": fields["duration"],
                "meeting_id": int(meeting_id),
                "extra_meeting_date_id": None,
                "parent_id": parent_id if parent_id else None,
                "approval_tree_id": None,
                "owner_id": owner_id,
                "presenters": [],
                "is_private": fields["is_private"],
                "attachments": [],
            }
            native = {"method": "POST", "url": API_ROOT + "/agenda-items", "json": body, "files": []}
        before = {"meeting": self._meeting_normalized(meeting, bounds)}
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected Boardable meeting differs from readback.")
        return {
            "change": asdict(change), "builder": "current", "before": before,
            "before_fingerprint": fingerprint, "native": native,
            "desired": {**fields, "owner_id": owner_id, "approval_tree_id": None, "presenters": []},
            "existing_uploads": [], "new_files": files,
            "conflict_semantics": "preflight_normalized_snapshot_compare_not_atomic_upstream_cas",
        }

    def _prepare_update(self, source, change, context, bounds, deadline, config, meeting_id, files):
        meeting = self._fetch_meeting(source, context, meeting_id, config, bounds, deadline)
        self._check_meeting(meeting, meeting_id)
        item_id = _bounded_id(change.resource_id, "item ID")
        item = self._fetch_item(source, context, str(item_id), config, bounds, deadline)
        item_meeting = item.get("meeting")
        if not isinstance(item_meeting, dict) or _bounded_id(item_meeting.get("id"), "meeting ID") != int(meeting_id):
            raise WriteFailure("permission_denied", "The item is not in the exact authorized meeting.")
        before_item = self._item_relevant(item, bounds)
        nodes = self._find_nodes(meeting.get("agenda_items", []), item_id)
        if len(nodes) != 1:
            raise WriteFailure("permission_denied", "The selected item is not uniquely present in the authorized meeting tree.")
        tree_row, tree_parent = nodes[0]
        if (tree_parent != before_item["parent_agenda_id"]
                or tree_row.get("parent_agenda_id", tree_parent) != before_item["parent_agenda_id"]):
            raise WriteFailure("permission_denied", "The selected item parent does not match the authorized meeting tree.")
        existing_uploads = before_item["uploads"]
        if not change.fields and not files:
            raise ValueError("An item update requires changed fields or new files.")
        desired = self._update_desired(change.fields, item)
        if files:
            parts = [
                {"kind": "field", "name": "title", "value": desired["text"]},
                {"kind": "field", "name": "description", "value": desired["description"]},
                {"kind": "field", "name": "duration", "value": str(desired["duration"])},
            ]
            if desired["owner_id"] is not None:
                parts.append({"kind": "field", "name": "owner_id", "value": str(desired["owner_id"])})
            parts.append({"kind": "field", "name": "approval_tree_id",
                          "value": "" if desired["approval_tree_id"] is None else str(desired["approval_tree_id"])})
            parts.append({"kind": "field", "name": "is_private", "value": "1" if desired["is_private"] else "0"})
            parts.append({"kind": "field", "name": "_method", "value": "PUT"})
            for index, presenter in enumerate(desired["presenters"]):
                parts.append({"kind": "field", "name": f"presenters[{index}]", "value": str(presenter)})
            for index, upload in enumerate(existing_uploads):
                parts.append({"kind": "field", "name": f"attachments[{index}][type]", "value": "attachment"})
                parts.append({"kind": "field", "name": f"attachments[{index}][attachment_id]",
                              "value": str(upload["id"])})
            for offset, part in enumerate(files, start=len(existing_uploads)):
                parts.append({"kind": "field", "name": f"attachments[{offset}][type]", "value": "upload"})
                parts.append({"kind": "file", "name": f"attachments[{offset}][file]", "part": part})
            native = {"method": "POST", "url": API_ROOT + "/agenda-items/" + str(item_id),
                      "multipart": parts, "files": files}
        else:
            body = {
                "title": desired["text"],
                "description": desired["description"],
                "duration": desired["duration"],
                "owner_id": desired["owner_id"],
                "approval_tree_id": desired["approval_tree_id"],
                "presenters": desired["presenters"],
                "is_private": desired["is_private"],
                "attachments": [{"type": "attachment", "attachment_id": upload["id"]}
                                for upload in existing_uploads],
            }
            native = {"method": "PUT", "url": API_ROOT + "/agenda-items/" + str(item_id),
                      "json": body, "files": []}
        before = {
            "meeting": self._meeting_normalized(meeting, bounds),
            "item": self._item_normalized(item, bounds),
        }
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected Boardable item differs from readback.")
        return {
            "change": asdict(change), "builder": "current", "before": before,
            "before_fingerprint": fingerprint, "native": native, "desired": desired,
            "existing_uploads": existing_uploads, "new_files": files,
            "conflict_semantics": "preflight_normalized_snapshot_compare_not_atomic_upstream_cas",
        }

    def _multipart_body(self, parts, bounds):
        boundary = "civic-connectors-" + uuid4().hex
        chunks = []
        for part in parts:
            if not isinstance(part, dict) or part.get("kind") not in {"field", "file"}:
                raise ValueError("Invalid multipart part.")
            name = part.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.\[\]-]+", name):
                raise ValueError("Unsafe multipart field name.")
            if part["kind"] == "field":
                value = part.get("value")
                if not isinstance(value, str):
                    value = str(value)
                chunks.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
                )
            else:
                file_part = part.get("part")
                self._validate_part(file_part)
                data = self._read_part(file_part)
                chunks.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                    f'filename="{file_part["filename"]}"\r\nContent-Type: {file_part["content_type"]}\r\n\r\n'.encode("utf-8")
                    + data + b"\r\n"
                )
        body = b"".join(chunks) + f"--{boundary}--\r\n".encode()
        if len(body) > bounds.transfer_bytes:
            raise ValueError("The multipart Boardable request exceeds transfer byte bounds.")
        return body, "multipart/form-data; boundary=" + boundary

    def _preflight_apply(self, source, change, prepared, context, bounds, deadline, config):
        meeting_id = self._meeting_id(change)
        meeting = self._fetch_meeting(source, context, meeting_id, config, bounds, deadline)
        self._check_meeting(meeting, meeting_id)
        if change.operation == "create":
            parent_id = change.parent_id if change.parent_id else 0
            if parent_id:
                parents = self._flatten_ids(meeting.get("agenda_items", []), bounds)
                if parent_id not in parents:
                    raise WriteFailure("conflict", "The selected parent is no longer in the exact authorized meeting.")
            current = {"meeting": self._meeting_normalized(meeting, bounds)}
        else:
            item_id = _bounded_id(change.resource_id, "item ID")
            item = self._fetch_item(source, context, str(item_id), config, bounds, deadline)
            item_meeting = item.get("meeting")
            if not isinstance(item_meeting, dict) or _bounded_id(item_meeting.get("id"), "meeting ID") != int(meeting_id):
                raise WriteFailure("conflict", "The selected item is no longer in the exact authorized meeting.")
            parent = item.get("parent_agenda_id")
            if type(parent) is not int:
                raise WriteFailure("conflict", "The selected item parent is ambiguous at commit time.")
            nodes = self._find_nodes(meeting.get("agenda_items", []), item_id)
            if len(nodes) != 1:
                raise WriteFailure("conflict", "The selected item is not uniquely present in the authorized meeting tree.")
            tree_row, tree_parent = nodes[0]
            if tree_parent != parent or tree_row.get("parent_agenda_id", tree_parent) != parent:
                raise WriteFailure("conflict", "The selected item parent changed after planning.")
            current = {
                "meeting": self._meeting_normalized(meeting, bounds),
                "item": self._item_normalized(item, bounds),
            }
        if canonical_hash(current) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The Boardable state changed after planning.")

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        config = self.credentials(source, context)
        self._preflight_apply(source, change, prepared, context, bounds, deadline, config)
        if persist and persist({"builder_step": "outbound_started"}):
            raise WriteCancelled()
        native = prepared["native"]
        if "json" in native:
            body = json.dumps(native["json"], ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
            content_type = "application/json"
        else:
            body, content_type = self._multipart_body(native["multipart"], bounds)
        if len(body) > bounds.transfer_bytes:
            raise ValueError("The Boardable request exceeds transfer byte bounds.")
        expected_status = 201 if change.operation == "create" else 200
        value = self._request_json(source, context, native["method"], native["url"], body, config,
                                   bounds, deadline, content_type=content_type,
                                   expected_status=expected_status)
        if change.operation == "create":
            data = value.get("data") if isinstance(value, dict) else None
            if not isinstance(data, dict):
                raise AmbiguousWrite("Boardable did not return the created item object.")
            try:
                identity = str(_bounded_id(data.get("id"), "created item ID"))
            except ValueError:
                raise AmbiguousWrite("Boardable did not return the created native identity.") from None
            if persist and persist({"resource_id": identity}):
                raise AmbiguousWrite("Created native identity was retained before cancellation.")
            if context.check_cancelled() or monotonic() >= deadline:
                raise AmbiguousWrite("Creation completed outside the active bounds; identity retained.")
            try:
                return self.reconcile(source, prepared, {"resource_id": identity}, context, bounds, deadline)
            except (WriteFailure, ValueError, AmbiguousWrite):
                raise AmbiguousWrite("Created identity was retained but exact readback did not complete.") from None
        if context.check_cancelled() or monotonic() >= deadline:
            raise AmbiguousWrite("Item update completed outside the active bounds.")
        try:
            return self.reconcile(source, prepared, {"resource_id": change.resource_id}, context, bounds, deadline)
        except (WriteFailure, ValueError, AmbiguousWrite):
            raise AmbiguousWrite("Item update was sent but exact readback did not complete.") from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        try:
            config = self.credentials(source, context)
            meeting_id = self._meeting_id(change)
            meeting = self._fetch_meeting(source, context, meeting_id, config, bounds, deadline)
            if change.operation == "create":
                identity = item.get("resource_id")
                if not isinstance(identity, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", identity):
                    return {"state": "uncertain", "reason": "Created native identity was not confirmed; no title matching."}
                item_data = self._fetch_item(source, context, identity, config, bounds, deadline)
                return self._verify_create(source, change, prepared, item_data, meeting, identity,
                                           config, context, bounds, deadline)
            item_data = self._fetch_item(source, context, str(_bounded_id(change.resource_id)),
                                         config, bounds, deadline)
            return self._verify_update(source, change, prepared, item_data, meeting,
                                       config, context, bounds, deadline)
        except (WriteFailure, ValueError, AmbiguousWrite):
            return {"state": "uncertain", "resource_id": item.get("resource_id"),
                    "reason": "Read-only Boardable reconciliation could not complete."}

    def _verify_create(self, source, change, prepared, item_data, meeting, identity, config, context, bounds, deadline):
        desired = prepared["desired"]
        expected_parent = change.parent_id if change.parent_id else 0
        try:
            self._check_meeting(meeting, self._meeting_id(change))
        except WriteFailure:
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "Readback meeting permission or draft flags differ."}
        if _bounded_id(item_data.get("id"), "item ID") != int(identity):
            return {"state": "uncertain", "resource_id": identity, "reason": "Readback item identity differs."}
        item_meeting = item_data.get("meeting")
        if not isinstance(item_meeting, dict) or _bounded_id(item_meeting.get("id")) != int(self._meeting_id(change)):
            return {"state": "uncertain", "resource_id": identity, "reason": "Readback meeting identity differs."}
        if item_data.get("parent_agenda_id") != expected_parent:
            return {"state": "uncertain", "resource_id": identity, "reason": "Readback parent differs."}
        if (item_data.get("text") != desired["text"]
                or item_data.get("description") != desired["description"]
                or item_data.get("duration") != desired["duration"]
                or _private(item_data.get("is_private")) != desired["is_private"]
                or _owner_id(item_data.get("owner")) != desired["owner_id"]
                or _approval_tree_id(item_data.get("approval_tree")) is not None
                or _presenters(item_data.get("presenters", [])) != []):
            return {"state": "uncertain", "resource_id": identity, "reason": "Readback fields differ."}
        try:
            self._verify_uploads(source, item_data, [], prepared["new_files"], config, context, bounds, deadline)
        except (WriteFailure, ValueError, AmbiguousWrite):
            return {"state": "uncertain", "resource_id": identity, "reason": "Readback attachments differ."}
        try:
            current_meeting = self._meeting_normalized(meeting, bounds)
            current_item = self._item_normalized(item_data, bounds)
        except (WriteFailure, ValueError):
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "Readback meeting tree or item detail is ambiguous."}
        prior_map = prepared["before"]["meeting"]["agenda_items"]
        current_map = current_meeting["agenda_items"]
        key = str(identity)
        if key not in current_map:
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "Created item is not present in the authorized tree."}
        if set(current_map) != set(prior_map) | {key}:
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "The create introduced or removed an unrequested agenda node."}
        for prior_key, prior_node in prior_map.items():
            if current_map.get(prior_key) != prior_node:
                return {"state": "uncertain", "resource_id": identity,
                        "reason": "An existing agenda node changed during create."}
        new_node = current_map[key]
        if new_node["parent_agenda_id"] != expected_parent:
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "The created node parent differs in the tree."}
        for field in ("text", "description", "duration", "is_private", "owner_id",
                      "approval_tree_id", "presenters", "uploads"):
            if new_node[field] != current_item[field]:
                return {"state": "uncertain", "resource_id": identity,
                        "reason": "The created tree node and item detail disagree."}
        return {"state": "succeeded", "resource_id": identity,
                "readback": {"item": item_data, "meeting": meeting}, "reconciled": True}

    def _verify_update(self, source, change, prepared, item_data, meeting, config, context, bounds, deadline):
        desired = prepared["desired"]
        try:
            self._check_meeting(meeting, self._meeting_id(change))
        except WriteFailure:
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "Readback meeting permission or draft flags differ."}
        try:
            current_item = self._item_normalized(item_data, bounds)
            current_meeting = self._meeting_normalized(meeting, bounds)
        except (WriteFailure, ValueError):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "Readback meeting tree or item detail is ambiguous."}
        before_item = prepared["before"]["item"]
        for key in ("id", "meeting_id", "parent_agenda_id"):
            if current_item[key] != before_item[key]:
                return {"state": "uncertain", "resource_id": change.resource_id,
                        "reason": "Readback identity or relationship changed."}
        for key in ("text", "description", "duration", "is_private"):
            if current_item[key] != desired[key]:
                return {"state": "uncertain", "resource_id": change.resource_id,
                        "reason": "Readback item fields differ."}
        if current_item["owner_id"] != desired["owner_id"] or current_item["approval_tree_id"] != desired["approval_tree_id"]:
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "Readback owner or approval tree changed."}
        if current_item["presenters"] != desired["presenters"]:
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "Readback presenters changed."}
        try:
            self._verify_uploads(source, item_data, prepared["existing_uploads"], prepared["new_files"],
                                 config, context, bounds, deadline)
        except (WriteFailure, ValueError, AmbiguousWrite):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "Readback attachments differ or are ambiguous."}
        prior_map = prepared["before"]["meeting"]["agenda_items"]
        current_map = current_meeting["agenda_items"]
        target_key = str(_bounded_id(change.resource_id, "item ID"))
        if target_key not in prior_map or target_key not in current_map:
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "The target item is not uniquely present before and after update."}
        if set(current_map) != set(prior_map):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "The update introduced or removed an unrequested agenda node."}
        prior_target = prior_map[target_key]
        current_target = current_map[target_key]
        if (current_target["parent_agenda_id"] != prior_target["parent_agenda_id"]
                or current_target["parent_agenda_id"] != current_item["parent_agenda_id"]
                or current_target.get("order") != prior_target.get("order")):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "The target item relationship or order changed implicitly."}
        if (current_target["owner_id"] != desired["owner_id"]
                or current_target["approval_tree_id"] != desired["approval_tree_id"]
                or current_target["presenters"] != desired["presenters"]):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "The target tree node has an implicit owner, presenter or approval-tree change."}
        for key in ("text", "description", "duration", "is_private"):
            if current_target[key] != current_item[key]:
                return {"state": "uncertain", "resource_id": change.resource_id,
                        "reason": "The target tree node and item detail disagree."}
        if current_target["uploads"] != current_item["uploads"]:
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "reason": "The target tree uploads and item detail disagree."}
        for prior_key, prior_node in prior_map.items():
            if prior_key == target_key:
                continue
            if current_map.get(prior_key) != prior_node:
                return {"state": "uncertain", "resource_id": change.resource_id,
                        "reason": "An unrelated agenda node changed during update."}
        return {"state": "succeeded", "resource_id": change.resource_id,
                "readback": {"item": item_data, "meeting": meeting}, "reconciled": True}

    def _verify_uploads(self, source, item_data, existing, new_files, config, context, bounds, deadline):
        uploads = item_data.get("uploads")
        if not isinstance(uploads, list) or len(uploads) > bounds.max_records:
            raise ValueError("Readback uploads are missing or exceed bounds.")
        summaries = [self._upload_summary(row) for row in uploads]
        if len({row["id"] for row in summaries}) != len(summaries):
            raise WriteFailure("ambiguous_upload", "Readback repeats an attachment identity.")
        if len(summaries) < len(existing):
            raise WriteFailure("conflict", "Readback discarded an existing attachment.")
        for index, expected in enumerate(existing):
            if summaries[index] != expected:
                raise WriteFailure("conflict", "Readback changed an existing attachment.")
        current_new = summaries[len(existing):]
        if not new_files:
            if current_new:
                raise WriteFailure("conflict", "Readback added unrequested attachments.")
            return
        if len(current_new) != len(new_files):
            raise WriteFailure("ambiguous_upload", "Readback new attachment count is ambiguous.")
        existing_ids = {row["id"] for row in existing}
        item_id = _bounded_id(item_data.get("id"), "item ID")
        organization_id = int(config["_organization_id"])
        used = set()
        for part in new_files:
            candidates = [row for row in current_new if row["filename"] == part["filename"]]
            if len(candidates) != 1:
                raise WriteFailure("ambiguous_filename", "A new filename does not identify exactly one upload.")
            upload = candidates[0]
            if upload["id"] in existing_ids or upload["id"] in used:
                raise WriteFailure("ambiguous_upload", "A new upload identity is duplicate.")
            used.add(upload["id"])
            reference = part["reference"]
            if (upload["mime_type"] != part["content_type"]
                    or upload["file_size"] != reference["byte_length"]
                    or upload.get("agenda_id") != item_id
                    or upload.get("organization_id") != organization_id):
                raise WriteFailure("conflict", "The new upload metadata/association differs.")
            self._download_verify(source, upload, part, config, context, bounds, deadline)
        if used != {row["id"] for row in current_new}:
            raise WriteFailure("ambiguous_upload", "Readback supplied an unmatched new attachment.")

    def _download_verify(self, source, upload, part, config, context, bounds, deadline):
        identity = _bounded_id(upload.get("id"), "upload ID")
        filename = upload.get("filename")
        if filename != part["filename"]:
            raise WriteFailure("conflict", "The new upload filename differs.")
        declared = upload.get("download_url")
        if not isinstance(declared, str) or not declared:
            raise WriteFailure("conflict", "The new upload did not declare its original download URL.")
        expected_url = source.url + DOWNLOAD_SEGMENT + str(identity) + "/" + quote(filename, safe="")
        expected = urlsplit(expected_url)
        declared_parsed = urlsplit(declared)
        if (declared_parsed.scheme != "https" or declared_parsed.netloc != "app.boardable.com"
                or declared_parsed.username or declared_parsed.password
                or declared_parsed.query or declared_parsed.fragment):
            raise WriteFailure("permission_denied", "The declared attachment download URL is outside the exact organization.")

        def path_segments(parsed):
            return [unquote(segment) for segment in parsed.path.split("/")]

        if path_segments(declared_parsed) != path_segments(expected):
            raise WriteFailure("permission_denied", "The declared attachment download URL does not match the exact approved route.")
        headers = self._headers(config)
        headers["Accept"] = "application/octet-stream"
        response = self._send(expected_url, "GET", None, headers, bounds.transfer_bytes, deadline, context)
        if response.status != 200 or len(response.content) > bounds.transfer_bytes:
            raise AmbiguousWrite("The attachment download did not return exact bytes.")
        response_headers = getattr(response, "headers", {}) or {}
        if any(str(key).lower() == "location" for key in response_headers):
            raise AmbiguousWrite("The attachment download attempted a redirect.")
        reference = part["reference"]
        if len(response.content) != reference["byte_length"]:
            raise WriteFailure("conflict", "The downloaded attachment length differs.")
        if hashlib.sha256(response.content).hexdigest() != reference["sha256"]:
            raise WriteFailure("conflict", "The downloaded attachment digest differs.")
