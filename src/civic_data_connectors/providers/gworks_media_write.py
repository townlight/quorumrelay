"""Recovered development media upload/list/association for gWorks writes."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from ..write_transport import WriteResponse
from . import gworks_editor

P = "cms_meeting."
F = "cms_file."
MEDIA_ROOT = gworks_editor.ORIGIN + "/cms/secure/media"
MEDIA_LIST = MEDIA_ROOT + "/list"
FILES_ORIGIN = "https://files.dev.gworks.cloud"
ALLOWED_EXTENSIONS = {"gif", "jpg", "jpeg", "png", "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}
MAX_SIZE_KB = 30000
MEDIA_ENTITIES = {"media", "media_upload", "meeting_media", "agenda_item_media", "media_association", "meeting_file"}
ASSOCIATION_FIELDS = {"meeting_id", "target", "filename", "usetype", "section_index", "item_index",
                      "section_title", "item_value", "expected_item", "item", "file", "media_id"}


def is_media_change(change):
    return change.entity in MEDIA_ENTITIES


def _id(value):
    if type(value) not in {int, str} or not re.fullmatch(r"[1-9][0-9]{0,18}", str(value)):
        raise ValueError("A positive native ID is required.")
    return str(value)


def _int(value, label, minimum=0):
    if type(value) is bool:
        raise ValueError(label + " must be an integer.")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        result = int(value)
    else:
        raise ValueError(label + " must be an integer.")
    if result < minimum:
        raise ValueError(label + " is out of range.")
    return result


def _safe_filename(value):
    if not isinstance(value, str) or not value or len(value) > 255 or value != value.strip():
        raise ValueError("A safe bounded filename is required.")
    if any(ord(c) < 32 or ord(c) == 127 or c in '\\/:*?"<>|' for c in value) or ".." in value:
        raise ValueError("Unsafe media filename.")
    if not all(c.isalnum() or c in " ._()-" for c in value):
        raise ValueError("Unsafe media filename.")
    if "." not in value:
        raise ValueError("A media filename extension is required.")
    if value.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("The media extension is not supported.")
    return value


def _mime(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+", value):
        raise ValueError("A safe MIME type is required.")
    return value


def _city_code(config, *, uncertain=False):
    city = config.get("city_code")
    if not isinstance(city, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", city):
        if uncertain:
            raise AmbiguousWrite("A separately bound trusted files city code is unavailable after mutation.")
        raise WriteFailure("permission_denied", "A separately bound trusted files city code is required.")
    return city


def _row(value):
    if not isinstance(value, dict):
        raise ValueError("Media list rows must be objects.")
    needed = {F + "id", F + "filename", F + "mime_type", F + "size_kb", F + "created_ts"}
    if not needed.issubset(value):
        raise ValueError("A media row is missing a documented field.")
    created = value[F + "created_ts"]
    if not isinstance(created, str):
        raise ValueError("Media created_ts must be a string.")
    return {F + "id": _id(value[F + "id"]), F + "filename": _safe_filename(value[F + "filename"]),
            F + "mime_type": _mime(value[F + "mime_type"]),
            F + "size_kb": _int(value[F + "size_kb"], "size_kb"), F + "created_ts": created}


def _fields(change):
    value = change.fields if isinstance(change.fields, dict) else {}
    unknown = set(value) - ASSOCIATION_FIELDS
    if unknown:
        raise ValueError("Unsupported media association field(s): " + ", ".join(sorted(unknown)))
    return value


def _needs_association(change, fields):
    keys = {"meeting_id", "target", "usetype", "section_index", "item_index", "section_title",
            "item_value", "expected_item", "item", "file", "media_id"}
    return bool(change.meeting_id or keys & set(fields) or change.entity in {"meeting_media", "agenda_item_media", "media_association"})


def _meeting_id(change, fields):
    value = change.meeting_id or fields.get("meeting_id")
    return _id(value)


def authorize(adapter, source, change, context):
    config = adapter.credentials(source, context)
    permissions = config.get("permissions", ())
    if change.files:
        _city_code(config)
        if "media:upload" not in permissions:
            raise WriteFailure("permission_denied", "Media upload is outside current policy.")
    elif change.operation not in {"update", "associate"}:
        raise WriteFailure("unsupported_operation", "Media association requires an explicit update.")
    fields = _fields(change)
    if _needs_association(change, fields):
        meeting = _meeting_id(change, fields)
        ids = config.get("meeting_ids")
        if not isinstance(ids, (list, tuple, set, frozenset)) or meeting not in ids:
            raise WriteFailure("permission_denied", "The meeting is outside media association policy.")
        if "meeting:update" not in permissions:
            raise WriteFailure("permission_denied", "Media association requires meeting update permission.")
    if change.files and change.operation not in {"create", "upload"}:
        raise WriteFailure("unsupported_operation", "Upload operation must be create/upload.")
    if not change.files and change.operation not in {"update", "associate"}:
        raise WriteFailure("unsupported_operation", "Association operation must be update/associate.")


def _file_info(adapter, change, bounds):
    if len(change.files) != 1:
        raise ValueError("Media upload requires exactly one file part.")
    part = deepcopy(change.files[0])
    if set(part) != {"part", "filename", "content_type", "reference"} or part["part"] != "file":
        raise ValueError("Media upload requires one part named file.")
    filename = _safe_filename(part["filename"])
    content_type = _mime(part["content_type"])
    reference = part.get("reference")
    if not isinstance(reference, dict):
        raise ValueError("An immutable file reference is required.")
    length = _int(reference.get("byte_length"), "byte_length", 1)
    digest = reference.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("A SHA-256 file reference is required.")
    if length > bounds.transfer_bytes or length > bounds.parser_bytes or length // 1000 > MAX_SIZE_KB:
        raise ValueError("The file exceeds configured parser/transfer/development media bounds.")
    with adapter._open_file(part) as stream:
        data = stream.read(length + 1)
    if len(data) != length or sha256(data).hexdigest() != digest.lower():
        raise ValueError("The local file does not match its immutable reference.")
    return {"part": part, "filename": filename, "content_type": content_type,
            "byte_length": length, "sha256": digest.lower(), "size_kb": length // 1000}


def _form_params(start, length, draw):
    columns = [("cms_file.filename", "true", "true"), ("cms_file.mime_type", "true", "true"),
               ("cms_file.size_kb", "true", "true"), ("cms_file.created_ts", "true", "true"),
               ("cms_file.id", "false", "false")]
    params = {"draw": str(draw), "start": str(start), "length": str(length),
              "search[value]": "", "search[regex]": "false",
              "order[0][column]": "4", "order[0][dir]": "desc"}
    for index, (data, searchable, orderable) in enumerate(columns):
        params[f"columns[{index}][data]"] = data
        params[f"columns[{index}][name]"] = ""
        params[f"columns[{index}][searchable]"] = searchable
        params[f"columns[{index}][orderable]"] = orderable
        params[f"columns[{index}][search][value]"] = ""
        params[f"columns[{index}][search][regex]"] = "false"
    return params


def _response_json(response, limit, uncertain, config, read=False):
    if not isinstance(response, WriteResponse) or len(response.content) > limit:
        raise AmbiguousWrite("Invalid or oversized provider response.") if uncertain else WriteFailure("provider_response", "Invalid provider response.")
    if response.status in {401, 403}:
        if uncertain:
            raise AmbiguousWrite("The provider denied or could not confirm the operation after a possible mutation.")
        raise WriteFailure("permission_denied", "The provider denied this operation.")
    if read and response.status != 200:
        raise AmbiguousWrite("Media listing failed.") if uncertain else WriteFailure("listing_failed", "Media listing failed.")
    if not read and not 200 <= response.status < 300:
        raise AmbiguousWrite("Media allocation outcome is uncertain.")
    try:
        value = json.loads(response.content)
    except (ValueError, TypeError):
        raise AmbiguousWrite("Provider JSON is invalid.") if uncertain else WriteFailure("provider_response", "Provider JSON is invalid.")
    return value


def _list_media(adapter, source, context, bounds, deadline, *, uncertain=False):
    config = adapter.credentials(source, context)
    token = config["token"]
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)
    max_records = max(1, int(bounds.max_records))
    length = min(100, max_records)
    start, draw, rows, seen_ids, seen_pages = 0, 1, [], set(), set()
    records_total = records_filtered = None
    while True:
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AmbiguousWrite("Media listing exceeded the deadline.") if uncertain else WriteFailure("deadline_exceeded", "Media listing exceeded the deadline.")
        body = urlencode(_form_params(start, length, draw)).encode()
        if len(body) > limit:
            raise ValueError("Media listing request exceeds bounds.")
        try:
            response = adapter.transport.send(MEDIA_LIST, method="POST", body=body, headers={
                "Authorization": "Bearer " + token, "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"}, byte_limit=limit, deadline_seconds=remaining)
        except (OSError, RuntimeError, ValueError):
            raise AmbiguousWrite("Media listing failed.") if uncertain else WriteFailure("listing_failed", "Media listing failed.")
        value = _response_json(response, limit, uncertain, config, read=True)
        if not isinstance(value, dict) or any(k not in value for k in ("draw", "recordsTotal", "recordsFiltered", "data")):
            raise AmbiguousWrite("Media listing envelope is incomplete.") if uncertain else WriteFailure("listing_failed", "Media listing envelope is incomplete.")
        if _int(value["draw"], "draw") != draw:
            raise AmbiguousWrite("Media listing draw did not match.") if uncertain else WriteFailure("listing_failed", "Media listing draw did not match.")
        total, filtered = _int(value["recordsTotal"], "recordsTotal"), _int(value["recordsFiltered"], "recordsFiltered")
        if filtered > total or filtered > max_records or not isinstance(value["data"], list):
            raise AmbiguousWrite("Contradictory media totals.") if uncertain else WriteFailure("listing_failed", "Contradictory media totals.")
        if records_total is None:
            records_total, records_filtered = total, filtered
        elif (total, filtered) != (records_total, records_filtered):
            raise AmbiguousWrite("Media totals changed during paging.") if uncertain else WriteFailure("listing_failed", "Media totals changed during paging.")
        page = [_row(row) for row in value["data"]]
        expected_len = min(length, max(0, records_filtered - start))
        if len(page) != expected_len or (start > 0 and not page):
            raise AmbiguousWrite("Media page length contradicts envelope totals.") if uncertain else WriteFailure("listing_failed", "Media page length contradicts envelope totals.")
        signature = (start, tuple(row[F + "id"] for row in page))
        if signature in seen_pages:
            raise AmbiguousWrite("Repeated media page.") if uncertain else WriteFailure("listing_failed", "Repeated media page.")
        seen_pages.add(signature)
        for row in page:
            if row[F + "id"] in seen_ids:
                raise AmbiguousWrite("Repeated media row.") if uncertain else WriteFailure("listing_failed", "Repeated media row.")
            seen_ids.add(row[F + "id"])
            rows.append(row)
        if len(rows) == records_filtered:
            break
        if len(rows) > records_filtered or not page:
            raise AmbiguousWrite("Media paging did not terminate.") if uncertain else WriteFailure("listing_failed", "Media paging did not terminate.")
        start += length
        draw += 1
    return rows


def _signed_url(value, config):
    if not isinstance(value, str) or len(value) > 8192:
        raise AmbiguousWrite("The media allocation did not return a signed URL.")
    parsed = urlsplit(value)
    allowed = config.get("media_storage_origins", (FILES_ORIGIN,))
    if not isinstance(allowed, (list, tuple, set, frozenset)) or not allowed:
        raise AmbiguousWrite("No approved media storage destinations are configured.")
    origin = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in {None, 443} or origin not in allowed):
        raise AmbiguousWrite("The media allocation returned an unapproved storage destination.")
    return value


def _metadata(adapter, source, context, bounds, deadline, file_info):
    config = adapter.credentials(source, context)
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)
    body = json.dumps({F + "filename": file_info["filename"], F + "mime_type": file_info["content_type"],
                       F + "size_kb": file_info["size_kb"]}, separators=(",", ":")).encode()
    if len(body) > limit:
        raise ValueError("Media metadata request exceeds bounds.")
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise WriteFailure("deadline_exceeded", "Media deadline expired before allocation.")
    try:
        response = adapter.transport.send(MEDIA_ROOT, method="POST", body=body, headers={
            "Authorization": "Bearer " + config["token"], "Accept": "application/json",
            "Content-Type": "application/json"}, byte_limit=limit, deadline_seconds=remaining)
    except (OSError, RuntimeError, ValueError):
        raise AmbiguousWrite("Media allocation may have succeeded.")
    value = _response_json(response, limit, True, config)
    if not isinstance(value, dict):
        raise AmbiguousWrite("Media allocation response is invalid.")
    return _signed_url(value.get("signedUrl"), config)


def _put_storage(adapter, context, bounds, deadline, url, file_info, data):
    if context.check_cancelled():
        raise AmbiguousWrite("Media allocation completed; storage upload is uncertain.")
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise AmbiguousWrite("Media allocation completed; storage upload deadline expired.")
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)
    try:
        response = adapter.transport.send(url, method="PUT", body=data,
                                          headers={"Content-Type": file_info["content_type"]},
                                          byte_limit=limit,
                                          deadline_seconds=remaining)
    except (OSError, RuntimeError, ValueError):
        raise AmbiguousWrite("Storage upload outcome is uncertain.")
    if context.check_cancelled() or monotonic() >= deadline:
        raise AmbiguousWrite("Storage upload completed outside the active bounds.")
    if not isinstance(response, WriteResponse) or not 200 <= response.status < 300 or len(response.content) > limit:
        raise AmbiguousWrite("Storage upload was not confirmed.")


def _storage_get(adapter, source, context, bounds, deadline, filename):
    try:
        city = _city_code(adapter.credentials(source, context), uncertain=True)
    except WriteFailure as error:
        raise AmbiguousWrite("Trusted files city code is unavailable after upload.") from error
    url = FILES_ORIGIN + "/city/" + quote(city, safe="") + "/media/" + quote(filename, safe="")
    remaining = deadline - monotonic()
    if remaining <= 0 or context.check_cancelled():
        raise AmbiguousWrite("Media readback exceeded the deadline.")
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)
    try:
        response = adapter.transport.send(url, method="GET", body=None, headers={},
                                          byte_limit=limit, deadline_seconds=remaining)
    except (OSError, RuntimeError, ValueError):
        raise AmbiguousWrite("Media readback failed.")
    if context.check_cancelled() or monotonic() >= deadline:
        raise AmbiguousWrite("Media readback completed outside the active bounds.")
    if not isinstance(response, WriteResponse) or response.status != 200 or len(response.content) > limit:
        raise AmbiguousWrite("Media readback was not confirmed.")
    return response.content


def _verify_bytes(adapter, source, context, bounds, deadline, file_info):
    content = _storage_get(adapter, source, context, bounds, deadline, file_info["filename"])
    if len(content) != file_info["byte_length"] or sha256(content).hexdigest() != file_info["sha256"]:
        raise AmbiguousWrite("Uploaded media bytes/hash do not match the local file.")


def _unique(rows, filename, media_id=None):
    matches = [row for row in rows if row[F + "filename"] == filename]
    if media_id is not None:
        matches = [row for row in matches if row[F + "id"] == _id(media_id)]
    if len(matches) != 1:
        raise AmbiguousWrite("Media filename does not identify exactly one native row.")
    return matches[0]


def _new_row(rows, file_info, preexisting_ids, media_id=None):
    matches = [row for row in rows if row[F + "filename"] == file_info["filename"]
               and row[F + "id"] not in preexisting_ids]
    if media_id is not None:
        matches = [row for row in matches if row[F + "id"] == _id(media_id)]
    if len(matches) != 1:
        raise AmbiguousWrite("The new media filename does not identify exactly one native row.")
    row = matches[0]
    if not _row_matches(row, file_info):
        raise AmbiguousWrite("The new media row does not match the uploaded file.")
    return row


def _row_matches(row, file_info):
    return (row[F + "filename"] == file_info["filename"] and row[F + "mime_type"] == file_info["content_type"]
            and row[F + "size_kb"] == file_info["size_kb"])


def _select_item(current, fields):
    data = current.get(P + "data")
    if not isinstance(data, list):
        raise ValueError("The meeting has no section array.")
    positional = "section_index" in fields or "item_index" in fields
    snapshot = fields.get("expected_item", fields.get("item"))
    if positional:
        if "section_index" not in fields or "item_index" not in fields:
            raise ValueError("Both section_index and item_index are required.")
        if snapshot is None:
            raise ValueError("Item positional selection requires the original expected_item snapshot.")
        si, ii = _int(fields["section_index"], "section_index"), _int(fields["item_index"], "item_index")
        if si >= len(data) or not isinstance(data[si].get("items"), list) or ii >= len(data[si]["items"]):
            raise ValueError("The agenda item position is out of range.")
    else:
        title, value = fields.get("section_title"), fields.get("item_value")
        if not isinstance(title, str) or not isinstance(value, str):
            raise ValueError("Provide section_index/item_index or section_title/item_value.")
        matches = []
        for si, section in enumerate(data):
            if isinstance(section, dict) and section.get("title") == title and isinstance(section.get("items"), list):
                for ii, item in enumerate(section["items"]):
                    if isinstance(item, dict) and item.get("value") == value:
                        matches.append((si, ii))
        if len(matches) != 1:
            raise ValueError("Agenda item selection must be unique.")
        si, ii = matches[0]
    item = data[si]["items"][ii]
    if not isinstance(item, dict):
        raise ValueError("The selected agenda item is invalid.")
    if snapshot is not None and canonical_hash(snapshot) != canonical_hash(item):
        raise WriteFailure("conflict", "The original agenda item snapshot does not match.")
    return {"section_index": si, "item_index": ii, "item_hash": canonical_hash(item), "item": deepcopy(item)}


def _prepare_association(adapter, source, change, context, bounds, deadline, fields, file_info, media_row):
    meeting_id = _meeting_id(change, fields)
    target = fields.get("target", "meeting")
    if target not in {"meeting", "agenda_item"}:
        raise ValueError("Association target must be meeting or agenda_item.")
    current = adapter._request(source, change, context, bounds, deadline, identity=meeting_id)
    if not isinstance(current, dict) or not isinstance(current.get(P + "files"), list):
        raise ValueError("The meeting snapshot is invalid.")
    assoc = {"meeting_id": meeting_id, "target": target, "before_fingerprint": canonical_hash(current),
             "before": deepcopy(current)}
    if target == "agenda_item":
        usetype = fields.get("usetype")
        if usetype not in {"official", "public"}:
            raise ValueError("Agenda media usetype must be explicit official/public.")
        descriptor = fields.get("file")
        provided = fields.get("filename")
        if provided is None and isinstance(descriptor, dict):
            provided = descriptor.get("name")
        if media_row is not None:
            row_filename = media_row[F + "filename"]
            if provided is not None and _safe_filename(provided) != row_filename:
                raise WriteFailure("conflict", "The supplied filename does not identify the selected media row.")
            filename = row_filename
        elif file_info is not None:
            filename = file_info["filename"]
        else:
            if provided is None:
                raise ValueError("Agenda media association requires a filename or exact media row.")
            filename = _safe_filename(provided)
        assoc.update(usetype=usetype, filename=filename, selected=_select_item(current, fields))
    else:
        if fields.get("usetype") is not None:
            raise ValueError("Meeting media does not accept usetype.")
    if media_row is not None:
        expected, body, noop, descriptor = _expected_association(current, assoc, media_row)
        assoc.update(expected=expected, body=body, noop=noop, media_descriptor=descriptor, media_row=media_row)
    return assoc


def _meeting_body(current):
    timestamp = current.get(P + "meeting_ts")
    if not isinstance(timestamp, str):
        raise ValueError("The meeting timestamp is invalid.")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    title, location = current.get(P + "title"), current.get(P + "location")
    category = current.get(P + "category_ref_type_id")
    data, files = current.get(P + "data"), current.get(P + "files")
    if (not isinstance(title, str) or not isinstance(location, str) or category is None
            or not isinstance(data, list) or not isinstance(files, list)):
        raise ValueError("The meeting snapshot is missing required fields.")
    body = {P + "title": title, P + "location": location, P + "category_ref_type_id": str(category),
            P + "date": parsed.date().isoformat(), P + "time": parsed.strftime("%H:%M"),
            P + "meeting_ts": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            P + "data": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            P + "files": json.dumps(files, ensure_ascii=False, separators=(",", ":")),
            P + "section_count": len(data)}
    if current.get(P + "template_fl") is True:
        body[P + "template_fl"] = "true"
    return body


def _descriptor(row):
    return {"name": row[F + "filename"], "id": row[F + "id"],
            "size": str(row[F + "size_kb"]), "type": row[F + "mime_type"]}


def _expected_association(current, assoc, row):
    expected = deepcopy(current)
    if assoc["target"] == "meeting":
        descriptor = _descriptor(row)
        files = expected[P + "files"]
        if descriptor in files:
            return expected, None, True, descriptor
        if any(isinstance(f, dict) and (str(f.get("id")) == descriptor["id"] or f.get("name") == descriptor["name"]) for f in files):
            raise WriteFailure("conflict", "The meeting already contains an ambiguous media descriptor.")
        files.append(descriptor)
    else:
        selected = assoc["selected"]
        data = expected.get(P + "data")
        try:
            item = data[selected["section_index"]]["items"][selected["item_index"]]
        except (TypeError, IndexError, KeyError):
            raise WriteFailure("conflict", "The selected agenda item no longer exists.")
        if canonical_hash(item) != selected["item_hash"]:
            raise WriteFailure("conflict", "The selected agenda item changed after preparation.")
        descriptor = {"filename": row[F + "filename"], "usetype": assoc["usetype"]}
        files = item.get("files")
        if not isinstance(files, list):
            raise ValueError("The agenda item files array is invalid.")
        if descriptor in files:
            return expected, None, True, descriptor
        if any(isinstance(f, dict) and f.get("filename") == descriptor["filename"] for f in files):
            raise WriteFailure("conflict", "The agenda item already contains an ambiguous media descriptor.")
        files.append(descriptor)
    return expected, _meeting_body(expected), False, descriptor


def _comparable(value):
    result = deepcopy(value)
    result.pop(P + "mod_ts", None)
    if P + "meeting_ts" in result:
        result[P + "meeting_ts"] = datetime.fromisoformat(result[P + "meeting_ts"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    if P + "category_ref_type_id" in result:
        result[P + "category_ref_type_id"] = str(result[P + "category_ref_type_id"])
    return result


def _association_expected(assoc, row):
    expected = assoc.get("expected")
    if expected is not None:
        return expected
    before = assoc.get("before")
    if not isinstance(before, dict):
        raise AmbiguousWrite("The original meeting snapshot is unavailable for exact reconciliation.")
    value, body, noop, descriptor = _expected_association(deepcopy(before), assoc, row)
    return value


def _resolve_media(adapter, source, context, bounds, deadline, fields):
    media_id = fields.get("media_id")
    descriptor = fields.get("file")
    filename = fields.get("filename")
    if isinstance(descriptor, dict):
        if descriptor.get("id") is not None:
            descriptor_id = _id(descriptor["id"])
            if media_id is not None and _id(media_id) != descriptor_id:
                raise ValueError("The media_id and file.id descriptor disagree.")
            media_id = descriptor_id
        if filename is None:
            filename = descriptor.get("name")
    if media_id is None and filename is None:
        raise ValueError("Association-only changes require media_id, filename, or file.id/name.")
    rows = _list_media(adapter, source, context, bounds, deadline)
    if media_id is not None:
        matches = [row for row in rows if row[F + "id"] == _id(media_id)]
        if len(matches) != 1:
            raise WriteFailure("not_found", "The exact media ID was not found.")
        row = matches[0]
        if filename is not None and _safe_filename(filename) != row[F + "filename"]:
            raise WriteFailure("conflict", "The supplied filename does not identify the selected media ID.")
        return row
    return _unique(rows, _safe_filename(filename), media_id)


def prepare(adapter, source, change, context, bounds, deadline):
    adapter.authorize(source, change, context)
    if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
        raise ValueError("A bounded change key is required.")
    fields = _fields(change)
    file_info = _file_info(adapter, change, bounds) if change.files else None
    assoc = None
    media_row = None
    if _needs_association(change, fields):
        if file_info is None:
            media_row = _resolve_media(adapter, source, context, bounds, deadline, fields)
        assoc = _prepare_association(adapter, source, change, context, bounds, deadline, fields, file_info, media_row)
    elif file_info is None:
        raise ValueError("A media change must upload or associate media.")
    preexisting = []
    if file_info is not None:
        rows = _list_media(adapter, source, context, bounds, deadline)
        if any(row[F + "filename"] == file_info["filename"] for row in rows):
            raise WriteFailure("ambiguous_filename", "A media filename already exists; exact new identity is ambiguous.")
        preexisting = [row[F + "id"] for row in rows]
    action = "upload_associate" if file_info is not None and assoc is not None else "upload" if file_info is not None else "associate"
    files = [deepcopy(change.files[0])] if file_info is not None else []
    return {"change": change.__dict__, "kind": "gworks_media", "action": action,
            "file": file_info, "preexisting_ids": preexisting, "association": assoc,
            "native": {"method": "POST", "url": MEDIA_ROOT, "files": files},
            "conflict_semantics": "preflight_list_and_meeting_compare_not_atomic_upstream_cas"}


def _upload(adapter, source, change, prepared, context, bounds, deadline, persist):
    file_info = prepared["file"]
    if persist and persist({"media_step": "metadata_intent", "filename": file_info["filename"]}):
        raise WriteCancelled()
    if context.check_cancelled():
        raise WriteCancelled()
    signed_url = _metadata(adapter, source, context, bounds, deadline, file_info)
    if persist and persist({"media_step": "metadata_allocated"}):
        raise AmbiguousWrite("Media allocation completed but cancellation was requested.")
    if context.check_cancelled() or monotonic() >= deadline:
        raise AmbiguousWrite("Media allocation completed outside the active bounds.")
    with adapter._open_file(file_info["part"]) as stream:
        data = stream.read(file_info["byte_length"] + 1)
    if len(data) != file_info["byte_length"] or sha256(data).hexdigest() != file_info["sha256"]:
        raise AmbiguousWrite("Local media bytes changed after allocation.")
    if persist and persist({"media_step": "storage_put_intent"}):
        raise AmbiguousWrite("Media allocation completed; storage upload was cancelled.")
    _put_storage(adapter, context, bounds, deadline, signed_url, file_info, data)
    if persist and persist({"media_step": "uploaded"}):
        raise AmbiguousWrite("Storage upload completed but cancellation was requested.")
    rows = _list_media(adapter, source, context, bounds, deadline, uncertain=True)
    row = _new_row(rows, file_info, set(prepared["preexisting_ids"]))
    _verify_bytes(adapter, source, context, bounds, deadline, file_info)
    if persist and persist({"resource_id": row[F + "id"], "media_row": row}):
        raise AmbiguousWrite("Uploaded media identity was retained before cancellation.")
    return row


def _apply_association(adapter, source, change, prepared, row, context, bounds, deadline, persist, prior_mutation):
    assoc = prepared["association"]
    current = adapter._request(source, change, context, bounds, deadline, identity=assoc["meeting_id"])
    if canonical_hash(current) != assoc["before_fingerprint"]:
        raise WriteFailure("conflict", "The meeting changed after media association preparation.")
    expected, body, noop, descriptor = _expected_association(current, assoc, row)
    if noop:
        return {"state": "succeeded", "resource_id": row[F + "id"], "meeting_id": assoc["meeting_id"],
                "readback": current, "media_row": row, "media_descriptor": descriptor}
    intent = {"media_step": "association_intent", "resource_id": row[F + "id"], "meeting_id": assoc["meeting_id"]}
    if persist and persist(intent):
        if prior_mutation:
            raise AmbiguousWrite("Upload succeeded; association was cancelled before save.")
        raise WriteCancelled()
    if context.check_cancelled() or monotonic() >= deadline:
        if prior_mutation:
            raise AmbiguousWrite("Upload succeeded; association save was not started.")
        raise WriteCancelled() if context.check_cancelled() else WriteFailure("deadline_exceeded", "Association deadline expired.")
    adapter._request(source, change, context, bounds, deadline, identity=assoc["meeting_id"], body=body)
    if persist and persist({"media_step": "association_ack", "resource_id": row[F + "id"], "meeting_id": assoc["meeting_id"]}):
        raise AmbiguousWrite("Association save returned but cancellation was requested.")
    if context.check_cancelled() or monotonic() >= deadline:
        raise AmbiguousWrite("Association save completed outside the active bounds.")
    readback = adapter._request(source, change, context, bounds, deadline, identity=assoc["meeting_id"])
    if canonical_hash(_comparable(readback)) != canonical_hash(_comparable(expected)):
        return {"state": "uncertain", "resource_id": row[F + "id"], "meeting_id": assoc["meeting_id"],
                "readback": readback, "media_row": row, "reason": "Final association readback did not match exactly."}
    return {"state": "succeeded", "resource_id": row[F + "id"], "meeting_id": assoc["meeting_id"],
            "readback": readback, "media_row": row, "media_descriptor": descriptor}


def apply(adapter, source, prepared, context, bounds, deadline, *, persist=None):
    change = WriteChange.from_dict(prepared["change"])
    adapter.authorize(source, change, context)
    if prepared["action"] in {"upload", "upload_associate"}:
        row = _upload(adapter, source, change, prepared, context, bounds, deadline, persist)
        if prepared["action"] == "upload":
            return {"state": "succeeded", "resource_id": row[F + "id"], "media_row": row}
        try:
            return _apply_association(adapter, source, change, prepared, row, context, bounds, deadline, persist, True)
        except AmbiguousWrite:
            raise
        except WriteFailure as error:
            return {"state": "uncertain", "resource_id": row[F + "id"], "media_row": row,
                    "reason": "Upload succeeded but association failed: " + str(error)}
    row = prepared["association"].get("media_row")
    if row is None:
        raise ValueError("Association media identity is missing.")
    return _apply_association(adapter, source, change, prepared, row, context, bounds, deadline, persist, False)


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    change = WriteChange.from_dict(prepared["change"])
    adapter.authorize(source, change, context)
    if prepared["action"] in {"upload", "upload_associate"}:
        row = None
        try:
            rows = _list_media(adapter, source, context, bounds, deadline, uncertain=True)
            row = _new_row(rows, prepared["file"], set(prepared.get("preexisting_ids", ())), item.get("resource_id"))
            _verify_bytes(adapter, source, context, bounds, deadline, prepared["file"])
        except (AmbiguousWrite, WriteFailure, ValueError):
            return {"state": "uncertain", "resource_id": item.get("resource_id"),
                    "reason": "Read-only media reconciliation is incomplete."}
        assoc = prepared.get("association")
        if assoc is not None:
            try:
                current = adapter._request(source, change, context, bounds, deadline, identity=assoc["meeting_id"])
                expected = _association_expected(assoc, row)
            except (WriteFailure, ValueError):
                return {"state": "uncertain", "resource_id": row[F + "id"], "media_row": row,
                        "reason": "Media upload is confirmed; exact association readback is unavailable."}
            if canonical_hash(_comparable(current)) != canonical_hash(_comparable(expected)):
                return {"state": "uncertain", "resource_id": row[F + "id"], "media_row": row,
                        "readback": current, "reason": "Media upload is confirmed; exact association postcondition is not present."}
            return {"state": "succeeded", "resource_id": row[F + "id"], "media_row": row,
                    "readback": current, "reconciled": True}
        return {"state": "succeeded", "resource_id": row[F + "id"], "media_row": row, "reconciled": True}
    assoc = prepared.get("association") or {}
    row = assoc.get("media_row")
    if row is None:
        return {"state": "uncertain", "reason": "Association media identity is unavailable."}
    try:
        current = adapter._request(source, change, context, bounds, deadline, identity=assoc["meeting_id"])
        expected = _association_expected(assoc, row)
    except (WriteFailure, ValueError):
        return {"state": "uncertain", "resource_id": row[F + "id"],
                "reason": "Association readback is unavailable."}
    if canonical_hash(_comparable(current)) == canonical_hash(_comparable(expected)):
        return {"state": "succeeded", "resource_id": row[F + "id"], "readback": current, "reconciled": True}
    return {"state": "uncertain", "resource_id": row[F + "id"], "readback": current,
            "reason": "Exact association postcondition is not present; do not repeat the save."}
