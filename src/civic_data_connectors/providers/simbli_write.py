"""Recovered Simbli existing agenda-item title update; exact-plan only."""

from copy import deepcopy
from dataclasses import asdict
import ast
import json
import math
from time import monotonic
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from ..compat import source_namespace
from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse
from .simbli import HOST, _literal

APP2 = "https://app2.eboardsolutions.com"
TREE = "/Services/api/MeetingView/GetItemsTreeDTO/"
DETAILS = "/Services/api/MeetingView/GetMeetingItemDetailsModel/"
SAVE = "/Services/api/MeetingView/SaveAgendaItem/"
LOCK = "/api/Workflow/GetItemEditAccess/"
RELEASE = "/api/Workflow/ReleaseItemEditing/"
NATIVE = {
    "acquire": {
        "method": "POST",
        "path": LOCK,
        "query": ["sct", "endid", "enmid"],
        "body": "lock_dto_with_item_id",
    },
    "release": {"method": "POST", "path": RELEASE, "query": ["sct"], "form": "lock_dto_with_item_id"},
    "save": {
        "method": "POST",
        "path": SAVE,
        "query": ["sct", "endid", "enmid", "enitemid", "enuid", "entz", "enipaddress"],
        "body": "EncrID,itemDetailsDTO,itemContentDTO",
    },
}


def _good_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return False
    text = str(value)
    return text.isascii() and text.isdigit() and not text.startswith("0") and len(text) <= 19


def _header_safe(value):
    return (
        isinstance(value, str)
        and value
        and len(value) <= 16384
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def _cookie_safe(value):
    if not isinstance(value, str) or not value or len(value) > 16384:
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    for part in value.split("; "):
        name, sep, item = part.partition("=")
        if not sep or not name or not item:
            return False
        if any(c in " ,;" for c in name) or any(c in " ,;" for c in item):
            return False
    return True


def _parts(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "simbli.eboardsolutions.com"
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.path != "/SB_Meetings/ViewMeeting.aspx"
        or parsed.fragment
        or set(query) != {"S", "MID"}
        or any(len(query[key]) != 1 or not _good_id(query[key][0]) for key in query)
    ):
        raise ValueError("Simbli requires its exact public meeting URL.")
    return query["S"][0], query["MID"][0]


def _bad(value):
    raise ValueError("nonfinite JSON number")


def _bounded_json(content, bounds):
    if len(content) > bounds.parser_bytes:
        raise ValueError("JSON response exceeds parser bounds.")
    try:

        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON key.")
                result[key] = item
            return result

        value = json.loads(content, parse_constant=_bad, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("The response is not bounded JSON.") from None
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 100 or nodes > max(1000, bounds.max_records * 200):
            raise ValueError("JSON response exceeds structural bounds.")
        if isinstance(item, dict):
            if len(item) > 1000:
                raise ValueError("JSON object exceeds record bounds.")
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            if len(item) > bounds.max_records:
                raise ValueError("JSON array exceeds record bounds.")
            stack.extend((v, depth + 1) for v in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("JSON number is not finite.")
    return value


def _config_secrets(config):
    values = [config.get("token"), config.get("encrypted_user_id"), config.get("lock_user_id")]
    cookie = config.get("session_cookie")
    if isinstance(cookie, str):
        values.append(cookie)
        values.extend(part.partition("=")[2].strip() for part in cookie.split(";"))
    token = config.get("token")
    if isinstance(token, str):
        values.extend(part for part in token.split(".") if len(part) >= 16)
    return [v for v in values if isinstance(v, str) and v]


def _strip_credentials(value, path=()):
    placeholders = {
        "userid",
        "username",
        "sessionid",
        "securitytoken",
        "stoken",
        "endid",
        "enmeetingid",
        "encuuuid",
        "encrtz",
        "encripaddress",
        "token",
        "access_token",
        "authorization",
        "api_key",
        "cookie",
        "set-cookie",
        "password",
        "access_key",
        "secret_passphrase",
        "session_cookie",
        "csrf_token",
    }
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.startswith("$simbli_"):
                raise ValueError("A provider field collides with a reserved snapshot reference.")
            if key.lower() in placeholders:
                safe_key = "$simbli_field:" + key
                if (
                    key == "SecurityToken"
                    and item not in (None, "")
                    and len(path) == 4
                    and path[0] == "ItemContents"
                    and path[2] == "Attachments"
                    and _good_id(value.get("AttachmentID"))
                    and isinstance(item, str)
                ):
                    result[safe_key] = {
                        "$simbli_attachment_token": {
                            "attachment_id": str(value["AttachmentID"]),
                            "path": list(path),
                        }
                    }
                    continue
                if item in (None, "", False, 0):
                    result[safe_key] = item
                    continue
                raise ValueError("A credential-bearing DTO field cannot be persisted.")
            result[key] = _strip_credentials(item, path + (key,))
        return result
    if isinstance(value, list):
        return [_strip_credentials(item, path + (index,)) for index, item in enumerate(value)]
    return value


def _assert_safe(value, secrets):
    try:
        canonical_hash(value)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("The plan is not bounded finite JSON.") from None
    encoded = set()
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 4:
            encoded.add(secret)
            encoded.add(quote(secret, safe=""))

    def walk(item, key=""):
        if isinstance(item, dict):
            for child_key, child in item.items():
                if child_key.lower() in {
                    "authorization",
                    "cookie",
                    "set-cookie",
                    "stoken",
                    "securitytoken",
                } and child not in (None, "", False, 0):
                    raise ValueError("The plan contains credential authorization data.")
                walk(child, child_key)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child, key)
        elif isinstance(item, str):
            for secret in encoded:
                if secret in item:
                    raise ValueError("The plan contains credential authorization data.")

    walk(value)
    try:
        unchanged = canonical_hash(sanitize(value)) == canonical_hash(value)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("The plan is not bounded finite JSON.") from None
    if not unchanged:
        raise ValueError("The plan cannot be persisted without credential scrubbing.")


def _page_context(page, config):
    try:
        did = _literal(page, "did")
        mid = _literal(page, "meetingID")
        logged = _literal(page, "isUserLoggedIn")
        view = _literal(page, "viewMode")
        app2 = _literal(page, "app2Url")
        names = ("enDID", "enMeetingID", "encrTZ", "sToken", "enCuUID", "encrIpAddress")
        values = {name: _literal(page, name) for name in names}
    except Exception:
        raise ValueError("The fresh Simbli staff page lacks required controls.") from None
    if str(did) != str(config["site_id"]) or str(mid) != str(config["meeting_id"]):
        raise WriteFailure("permission_denied", "The fresh Simbli page is not the configured meeting.")
    if logged not in {"True", True}:
        raise WriteFailure(
            "permission_denied", "The fresh Simbli page is not an authenticated staff session."
        )
    if view not in {"", "myview"} or app2 != APP2:
        raise ValueError("The fresh Simbli page view or lock origin is not supported.")
    if any(not _header_safe(value) or len(value) > 4096 for value in values.values()):
        raise ValueError("The fresh Simbli page controls are malformed.")
    if values["enCuUID"] != config["encrypted_user_id"]:
        raise WriteFailure(
            "permission_denied", "The saved encrypted user binding is not the fresh page user."
        )
    lock = _lock_dto(page, config)
    secrets = _config_secrets(config) + list(values.values())
    secrets.append(lock["SessionID"])
    secrets.append(lock["UserID"])
    secrets.append(lock["Username"])
    secrets.append(lock["MeetingID"])
    secrets.append(lock["SiteID"])
    return {**values, "viewMode": view, "lock_dto": lock, "secrets": secrets}


def _lock_dto(page, config):
    marker = "var itemEditAccess = JSON.parse("
    start = page.find(marker)
    if start < 0:
        raise ValueError("The fresh Simbli page lacks its edit-lock DTO.")
    start += len(marker)
    if start >= len(page) or page[start] not in (chr(39), chr(34)):
        raise ValueError("The fresh Simbli page edit-lock literal is malformed.")
    quote_char = page[start]
    end = start + 1
    escaped = False
    while end < len(page):
        char = page[end]
        if escaped:
            escaped = False
        elif char == chr(92):
            escaped = True
        elif char == quote_char:
            break
        end += 1
    if end >= len(page):
        raise ValueError("The fresh Simbli page edit-lock literal is truncated.")
    try:
        raw = ast.literal_eval(page[start : end + 1])
        value = json.loads(raw, parse_constant=_bad)
    except (ValueError, SyntaxError, TypeError):
        raise ValueError("The fresh Simbli page edit-lock DTO is malformed.") from None
    keys = {"SessionID", "UserID", "Username", "MeetingID", "SiteID", "LastActivity", "ItemID", "Access"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("The fresh Simbli page edit-lock DTO has unexpected members.")
    for name in ("SessionID", "UserID", "Username", "MeetingID", "SiteID", "LastActivity"):
        if not _header_safe(value[name]):
            raise ValueError("The fresh Simbli page edit-lock DTO has invalid string members.")
    if value["ItemID"] is not None and not isinstance(value["ItemID"], str):
        raise ValueError("The fresh Simbli page edit-lock ItemID is invalid.")
    if type(value["Access"]) is not bool:
        raise ValueError("The fresh Simbli page edit-lock Access is invalid.")
    if not value["UserID"] or value["UserID"] != config["lock_user_id"]:
        raise WriteFailure("permission_denied", "The saved lock user binding does not match the fresh page.")
    return value


def _tree_index(payload, bounds):
    if not isinstance(payload, dict) or not isinstance(payload.get("Items"), list):
        raise ValueError("The Simbli tree DTO requires its Items array.")
    by_encrypted = {}
    by_agenda = {}
    root_sentinel = None
    count = 0

    def walk(rows, parent, depth):
        nonlocal root_sentinel, count
        if depth > 100 or not isinstance(rows, list):
            raise ValueError("The Simbli tree hierarchy is malformed.")
        for row in rows:
            count += 1
            if count > bounds.max_records or not isinstance(row, dict):
                raise ValueError("The Simbli tree exceeds its record bound or contains a malformed row.")
            for key in ("ID", "AgendaID", "ParentID", "Title", "Level", "Children"):
                if key not in row:
                    raise ValueError("The Simbli tree row is incomplete.")
            ident = row["ID"]
            agenda = row["AgendaID"]
            parent_id = row["ParentID"]
            children = row["Children"]
            level = row["Level"]
            if not isinstance(ident, str) or not ident or len(ident) > 4096:
                raise ValueError("The Simbli tree has an invalid encrypted ID.")
            if type(agenda) is not int or agenda <= 0:
                raise ValueError("The Simbli tree requires positive numeric AgendaID values.")
            if not isinstance(parent_id, str) or not parent_id:
                raise ValueError("The Simbli tree has an invalid ParentID.")
            if not isinstance(children, list) or type(level) is not int or level < 0:
                raise ValueError("The Simbli tree has an invalid hierarchy declaration.")
            if not isinstance(row.get("Title"), str):
                raise ValueError("The Simbli tree has an invalid Title.")
            if ident in by_encrypted or agenda in by_agenda:
                raise ValueError("The Simbli tree repeats an item identity.")
            if parent is None:
                if level != 0:
                    raise ValueError("A Simbli root item must have Level 0.")
                if root_sentinel is None:
                    root_sentinel = parent_id
                elif root_sentinel != parent_id:
                    raise ValueError("Simbli root items must share one root-parent sentinel.")
            else:
                if parent_id != parent["ID"] or level != parent["Level"] + 1:
                    raise ValueError("The Simbli tree parent hierarchy is inconsistent.")
            by_encrypted[ident] = row
            by_agenda[agenda] = row
            walk(children, row, depth + 1)

    walk(payload["Items"], None, 0)
    if not by_encrypted or root_sentinel is None or root_sentinel in by_encrypted:
        raise ValueError("The Simbli tree root-parent sentinel is invalid.")
    return by_encrypted, by_agenda, root_sentinel


def _ref_value(value, by_encrypted, root_sentinel, page, key=""):
    if isinstance(value, str):
        if key in {"ID", "ParentID", "EncrID", "EncrParentID", "AgendaID"} and value == root_sentinel:
            return {"$simbli_ref": "root"}
        row = (
            by_encrypted.get(value)
            if key in {"ID", "ParentID", "EncrID", "EncrParentID", "AgendaID"}
            else None
        )
        if row is not None:
            return {"$simbli_ref": "agenda:" + str(row["AgendaID"])}
        controls = {
            "MeetingID": ("enMeetingID", "meeting"),
            "EncrTimeZone": ("encrTZ", "timezone"),
            "SiteID": ("enDID", "site"),
            "SchoolID": ("enDID", "site"),
        }
        if key in controls:
            control, label = controls[key]
            if value == page[control]:
                return {"$simbli_ref": label}
        return value
    if isinstance(value, dict):
        return {key: _ref_value(item, by_encrypted, root_sentinel, page, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_ref_value(item, by_encrypted, root_sentinel, page, key) for item in value]
    return value


def _find_tree(tree, agenda_id):
    pending = list(tree.get("Items", []))
    while pending:
        row = pending.pop()
        if row.get("AgendaID") == agenda_id:
            return row
        pending.extend(row.get("Children", []))
    raise ValueError("The selected Simbli agenda identity is missing from the snapshot.")


def _snapshot(tree, details, selected, bounds, page):
    by_encrypted, by_agenda, root_sentinel = _tree_index(tree, bounds)
    page["secrets"].extend([root_sentinel, *by_encrypted])
    for field in details.get("ItemContents", []):
        for attachment in field.get("Attachments") or []:
            token = attachment.get("SecurityToken") if isinstance(attachment, dict) else None
            if isinstance(token, str) and token:
                page["secrets"].append(token)
    if selected["ID"] not in by_encrypted or by_agenda.get(selected["AgendaID"]) is not selected:
        raise ValueError("The selected Simbli tree row is inconsistent.")
    if details["ItemDetails"].get("EncrID") != selected["ID"]:
        raise ValueError("The item details do not match the fresh tree identity.")
    return {
        "tree": _ref_value(_strip_credentials(tree), by_encrypted, root_sentinel, page),
        "item": _ref_value(_strip_credentials(details), by_encrypted, root_sentinel, page),
        "selected_agenda_id": str(selected["AgendaID"]),
    }


def _validate_details(details, selected):
    if not isinstance(details, dict):
        raise ValueError("The Simbli item details response is malformed.")
    item = details.get("ItemDetails")
    contents = details.get("ItemContents")
    if not isinstance(item, dict) or not isinstance(contents, list):
        raise ValueError("The Simbli item details response lacks its DTO members.")
    if item.get("EncrID") != selected["ID"] or not isinstance(item.get("Title"), str):
        raise ValueError("The Simbli item details identity or title is invalid.")
    if item.get("IsEditable") is not True:
        raise WriteFailure("mapping_unverified", "The selected Simbli item is not currently editable.")
    if item.get("Deleted") is not False or item.get("HasWorkflow") is not False:
        raise WriteFailure("mapping_unverified", "Only a nondeleted no-workflow Simbli item is mapped.")
    if any(not isinstance(field, dict) for field in contents):
        raise ValueError("The Simbli item content DTO is malformed.")
    return item, contents


def _expected_after(snapshot, change):
    after = deepcopy(snapshot)
    after["item"]["ItemDetails"]["Title"] = change.fields["title"]
    return after


def _comparable(snapshot, change):
    value = deepcopy(snapshot)
    _find_tree(value["tree"], int(change.resource_id)).pop("Title", None)
    details = value["item"]["ItemDetails"]
    for key in ("ModifiedOn", "ModifiedOnTime", "ModifiedBy", "SiteTimeZoneDate"):
        details.pop(key, None)
    for field in value["item"].get("ItemContents", []):
        if isinstance(field, dict):
            field["IsEdit"] = True
    return value


def _matches_after(prepared, readback, change):
    try:
        row = _find_tree(readback["tree"], int(change.resource_id))
        original = _find_tree(prepared["before"]["tree"], int(change.resource_id))
        label = original.get("bulletLabel", "")
        expected_title = (label + ". " if label else "") + change.fields["title"]
        if row["Title"] != expected_title:
            return False
        return canonical_hash(_comparable(readback, change)) == canonical_hash(
            _comparable(prepared["after"], change)
        )
    except Exception:
        return False


class _Requests:
    def __init__(self, transport, config, context, bounds, deadline):
        self.transport = transport
        self.config = config
        self.context = context
        self.bounds = bounds
        self.deadline = deadline
        self.count = 0
        self.transfer = 0
        self.reserve_cleanup = False

    def require(self, count):
        if self.bounds.max_pages - self.count < count:
            raise WriteFailure(
                "bounds_exceeded", "The Simbli request budget is insufficient for the full safe operation."
            )

    def send(self, method, url, *, host, body=None, headers=None, cleanup=False, binary=False, file_body=False):
        if not cleanup and self.context.check_cancelled():
            raise WriteCancelled()
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != urlsplit(host).netloc
            or not url.startswith(host + "/")
        ):
            raise ValueError("The Simbli request left its fixed origin.")
        reserve = 1 if self.reserve_cleanup and not cleanup else 0
        if self.count >= self.bounds.max_pages - reserve:
            raise WriteFailure("bounds_exceeded", "The Simbli page budget is exhausted.")
        if body is not None and len(body) > (self.bounds.transfer_bytes if file_body else min(self.bounds.parser_bytes, self.bounds.transfer_bytes)):
            raise ValueError("The Simbli request body exceeds configured bounds.")
        remaining_bytes = self.bounds.transfer_bytes - self.transfer
        if self.reserve_cleanup and not cleanup:
            remaining_bytes -= min(1024, self.bounds.transfer_bytes // 10)
        request_bytes = len(body) if body is not None else 0
        if request_bytes >= remaining_bytes:
            raise WriteFailure("bounds_exceeded", "The Simbli request exceeds the remaining transfer budget.")
        remaining_bytes -= request_bytes
        if remaining_bytes <= 0:
            raise WriteFailure("bounds_exceeded", "The Simbli transfer budget is exhausted.")
        seconds = self.deadline - monotonic()
        if self.reserve_cleanup and not cleanup:
            seconds -= 0.05
        if seconds <= 0:
            raise WriteFailure("deadline_exceeded", "The Simbli operation deadline expired.")
        actual = {"Accept": "application/json", "Authorization": "Bearer " + self.config["token"]}
        if host == HOST:
            actual["Cookie"] = self.config["session_cookie"]
        elif host == APP2:
            if any(key.lower() == "cookie" for key in actual):
                raise ValueError("Cookies must not cross to the Simbli lock origin.")
        else:
            raise ValueError("Unknown Simbli request origin.")
        actual.update(headers or {})
        if host == APP2 and any(key.lower() == "cookie" for key in actual):
            raise ValueError("Cookies must not cross to the Simbli lock origin.")
        self.count += 1
        self.transfer += request_bytes
        try:
            response = self.transport.send(
                url,
                method=method,
                body=body,
                headers=actual,
                byte_limit=remaining_bytes if binary else min(self.bounds.parser_bytes, remaining_bytes),
                deadline_seconds=seconds,
            )
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse):
            raise AmbiguousWrite("The Simbli transport returned an invalid response.")
        if (
            len(response.content) > (remaining_bytes if binary else min(self.bounds.parser_bytes, remaining_bytes))
            or self.transfer + len(response.content) > self.bounds.transfer_bytes
        ):
            raise AmbiguousWrite("The Simbli response exceeded configured bounds.")
        self.transfer += len(response.content)
        if method == "GET" and not cleanup:
            if self.context.check_cancelled():
                raise WriteCancelled()
            if monotonic() >= self.deadline:
                raise WriteFailure("deadline_exceeded", "The Simbli read exceeded its deadline.")
        return response


class _Current:
    def __init__(self, page, tree, details, selected, snapshot):
        self.page = page
        self.tree = tree
        self.details = details
        self.selected = selected
        self.snapshot = snapshot


class SimbliWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("simbli", transport)

    def credentials(self, source, context):
        config = context.credentials.get("simbli")
        if not isinstance(config, dict) or not context.tenant or config.get("tenant") != context.tenant:
            raise WriteFailure("permission_denied", "An exact trusted Simbli tenant binding is required.")
        site, meeting = _parts(source.url)
        if (
            config.get("site_url") != source.url
            or str(config.get("site_id")) != site
            or str(config.get("meeting_id")) != meeting
        ):
            raise WriteFailure("permission_denied", "The Simbli site URL or numeric meeting binding changed.")
        namespace = source_namespace("simbli", urlsplit(source.url))
        if source.namespace != namespace or namespace not in config.get("allowed_namespaces", ()):
            raise WriteFailure(
                "permission_denied", "The Simbli credential does not authorize this exact namespace."
            )
        if context.allowed_namespaces is not None and namespace not in context.allowed_namespaces:
            raise WriteFailure(
                "permission_denied", "The Simbli namespace is outside the current application policy."
            )
        if not _cookie_safe(config.get("session_cookie")) or not _header_safe(config.get("token")):
            raise WriteFailure(
                "credentials_required", "Trusted Simbli session and bearer values are required."
            )
        if not _header_safe(config.get("encrypted_user_id")) or not _header_safe(config.get("lock_user_id")):
            raise WriteFailure(
                "credentials_required", "Explicit Simbli encrypted-user and lock-user bindings are required."
            )
        items = config.get("item_ids")
        if not isinstance(items, list) or any(
            not isinstance(item, str) or not _good_id(item) for item in items
        ):
            raise WriteFailure("permission_denied", "The saved Simbli item allowlist is malformed.")
        if "agenda_item:update" not in config.get("permissions", ()):
            raise WriteFailure(
                "permission_denied", "Server policy does not authorize Simbli agenda-item title updates."
            )
        return config

    def validate_source(self, source, context):
        if (
            source.provider != self.provider
            or source.options
            or source.body is not None
            or source.input_format is not None
        ):
            raise ValueError("Use an exact Simbli meeting source without options.")
        _parts(source.url)
        if source.namespace != source_namespace("simbli", urlsplit(source.url)):
            raise WriteFailure(
                "permission_denied", "The Simbli source namespace is not the canonical native identity."
            )
        self.credentials(source, context)

    def authorize(self, source, change, context):
        if change.entity == "agenda_item_attachment":
            return self._supporting().authorize(source, change, context)
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if (
            change.entity != "agenda_item"
            or change.operation != "update"
            or change.files
            or change.parent_id is not None
            or change.language is not None
            or change.page_number is not None
            or not isinstance(change.meeting_id, str)
            or change.meeting_id != str(config["meeting_id"])
            or not _good_id(change.resource_id)
            or str(change.resource_id) not in config["item_ids"]
            or not isinstance(change.fields, dict)
            or set(change.fields) != {"title"}
        ):
            raise WriteFailure("mapping_unverified", "Only one existing agenda-item title update is mapped.")
        title = change.fields["title"]
        if not isinstance(title, str) or not title or title != title.strip():
            raise WriteFailure("mapping_unverified", "The Simbli title must be a nonempty trimmed string.")

    def _authorize_commit(self, source, change, context):
        self.authorize(source, change, context)
        if "write:commit" not in context.authorization or not context.allows(
            "commit_write", source.namespace
        ):
            raise WriteFailure("permission_denied", "Current client policy denies this Simbli commit.")

    def _read_page(self, session, source, config, bounds):
        response = session.send(
            "GET", source.url, host=HOST, headers={"Accept": "text/html, application/json"}
        )
        _expect(response, ambiguous=False)
        if len(response.content) > bounds.parser_bytes:
            raise ValueError("The Simbli page exceeds parser bounds.")
        try:
            text = response.content.decode("utf-8-sig", errors="strict")
        except UnicodeError:
            raise ValueError("The Simbli page is not valid UTF-8.") from None
        page = _page_context(text, config)
        try:
            module = _literal(text, "encrModuleID")
        except Exception:
            module = None
        if module is not None:
            if not _header_safe(module) or len(module) > 4096:
                raise ValueError("The native module control is malformed.")
            page["encrModuleID"] = module
            page["secrets"].append(module)
        return page

    def _read_tree(self, session, page, bounds):
        query = urlencode(
            {
                "sct": page["sToken"],
                "endid": page["enDID"],
                "enmid": page["enMeetingID"],
                "enuid": page["enCuUID"],
                "v": page["viewMode"],
            }
        )
        response = session.send("GET", HOST + TREE + "?" + query, host=HOST)
        _expect(response, ambiguous=False)
        payload = _bounded_json(response.content, bounds)
        by_encrypted, by_agenda, root = _tree_index(payload, bounds)
        return payload, by_encrypted, by_agenda, root

    def _read_details(self, session, page, selected, bounds):
        query = urlencode(
            {
                "sct": page["sToken"],
                "endid": page["enDID"],
                "enmid": page["enMeetingID"],
                "enitemid": selected["ID"],
                "enuid": page["enCuUID"],
                "view": page["viewMode"],
                "stab": 1,
            }
        )
        response = session.send("GET", HOST + DETAILS + "?" + query, host=HOST)
        _expect(response, ambiguous=False)
        payload = _bounded_json(response.content, bounds)
        _validate_details(payload, selected)
        return payload

    def _read_current(self, session, source, config, change, bounds):
        page = self._read_page(session, source, config, bounds)
        tree, by_encrypted, by_agenda, root = self._read_tree(session, page, bounds)
        selected = by_agenda.get(int(change.resource_id))
        if selected is None or by_encrypted.get(selected["ID"]) is not selected:
            raise ValueError("The selected Simbli agenda item is not present exactly once.")
        details = self._read_details(session, page, selected, bounds)
        snapshot = _snapshot(tree, details, selected, bounds, page)
        _assert_safe(snapshot, page["secrets"])
        return _Current(page, tree, details, selected, snapshot)

    def _read_tree_details(self, session, page, change, bounds):
        tree, by_encrypted, by_agenda, root = self._read_tree(session, page, bounds)
        selected = by_agenda.get(int(change.resource_id))
        if selected is None or by_encrypted.get(selected["ID"]) is not selected:
            raise ValueError("The selected Simbli agenda item is not present exactly once.")
        details = self._read_details(session, page, selected, bounds)
        snapshot = _snapshot(tree, details, selected, bounds, page)
        _assert_safe(snapshot, page["secrets"])
        return _Current(page, tree, details, selected, snapshot)

    def _validate_prepared(self, source, prepared, context, bounds):
        if not isinstance(prepared, dict):
            raise ValueError("The Simbli prepared plan is malformed.")
        try:
            raw = json.dumps(prepared, allow_nan=False, separators=(",", ":")).encode()
        except (ValueError, TypeError, RecursionError):
            raise ValueError("The Simbli prepared plan is not finite acyclic JSON.") from None
        _bounded_json(raw, bounds)
        change = WriteChange.from_dict(prepared.get("change"))
        self.authorize(source, change, context)
        if prepared.get("native") != NATIVE:
            raise ValueError("The Simbli native plan skeleton was altered.")
        before = prepared.get("before")
        after = prepared.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError("The Simbli before/after snapshots are missing.")
        if prepared.get("before_fingerprint") != canonical_hash(before):
            raise ValueError("The Simbli prepared before fingerprint was altered.")
        if prepared.get("expected_version") != change.expected_version:
            raise ValueError("The Simbli expected version binding was altered.")
        if canonical_hash(after) != canonical_hash(_expected_after(before, change)):
            raise ValueError("The Simbli prepared expected state was altered.")
        _find_tree(before["tree"], int(change.resource_id))
        no_op = before["item"]["ItemDetails"]["Title"] == change.fields["title"]
        if prepared.get("no_op") is not no_op:
            raise ValueError("The Simbli no-op marker was altered.")
        return change, before, after

    def _lock_url(self, page):
        return (
            APP2
            + LOCK
            + "?"
            + urlencode({"sct": page["sToken"], "endid": page["enDID"], "enmid": page["enMeetingID"]})
        )

    def _release_url(self, page):
        return APP2 + RELEASE + "?" + urlencode({"sct": page["sToken"]})

    def _save_url(self, page, item_id):
        return (
            HOST
            + SAVE
            + "?"
            + urlencode(
                {
                    "sct": page["sToken"],
                    "endid": page["enDID"],
                    "enmid": page["enMeetingID"],
                    "enitemid": item_id,
                    "enuid": page["enCuUID"],
                    "entz": page["encrTZ"],
                    "enipaddress": page["encrIpAddress"],
                }
            )
        )

    def _lock(self, session, page, item_id, lock_dto, bounds):
        value = deepcopy(lock_dto)
        value["ItemID"] = item_id
        body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        response = session.send(
            "POST", self._lock_url(page), host=APP2, body=body, headers={"Content-Type": "application/json"}
        )
        _expect(response, ambiguous=True)
        answer = _bounded_json(response.content, bounds) if response.content else None
        if not isinstance(answer, dict) or answer.get("HasAccess") is not True:
            raise WriteFailure("lock_unavailable", "The native editing lock was not confirmed.")
        return value

    def _release(self, session, page, item_id, lock_dto):
        value = deepcopy(lock_dto)
        value["ItemID"] = item_id
        form = []
        for key, item in value.items():
            if item is None:
                text = ""
            elif isinstance(item, bool):
                text = "true" if item else "false"
            else:
                text = str(item)
            form.append((key, text))
        response = session.send(
            "POST",
            self._release_url(page),
            host=APP2,
            body=urlencode(form).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cleanup=True,
        )
        if not 200 <= response.status < 300:
            raise WriteFailure("release_failed", "The native editing lock release was not confirmed.")

    def _save(self, session, page, item_id, body):
        response = session.send(
            "POST",
            self._save_url(page, item_id),
            host=HOST,
            body=json.dumps(body, separators=(",", ":"), allow_nan=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        _expect(response, ambiguous=True)
        return response

    def _supporting(self):
        from .simbli_upload import SupportingUpload
        return SupportingUpload(self)

    def prepare(self, source, change, context, bounds, deadline):
        if change.entity == "agenda_item_attachment":
            return self._supporting().prepare(source, change, context, bounds, deadline)
        self.authorize(source, change, context)
        config = self.credentials(source, context)
        if context.check_cancelled():
            raise WriteCancelled()
        session = _Requests(self.transport, config, context, bounds, deadline)
        session.require(3)
        current = self._read_current(session, source, config, change, bounds)
        snapshot = current.snapshot
        fingerprint = canonical_hash(snapshot)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected Simbli agenda-item snapshot differs from readback.")
        after = _expected_after(snapshot, change)
        no_op = snapshot["item"]["ItemDetails"]["Title"] == change.fields["title"]
        prepared = {
            "change": asdict(change),
            "before": snapshot,
            "after": after,
            "before_fingerprint": fingerprint,
            "expected_version": change.expected_version,
            "native": deepcopy(NATIVE),
            "no_op": no_op,
            "conflict_semantics": "preflight_compare_and_native_editing_lock_not_atomic_upstream_cas",
        }
        _bounded_json(json.dumps(prepared, allow_nan=False, separators=(",", ":")).encode(), bounds)
        _assert_safe(prepared, current.page["secrets"])
        return prepared

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        if prepared.get("change", {}).get("entity") == "agenda_item_attachment":
            return self._supporting().apply(source, prepared, context, bounds, deadline, persist=persist)
        change, before, after = self._validate_prepared(source, prepared, context, bounds)
        config = self.credentials(source, context)
        if context.check_cancelled():
            raise WriteCancelled()
        session = _Requests(self.transport, config, context, bounds, deadline)
        session.require(3)
        current = self._read_current(session, source, config, change, bounds)
        if canonical_hash(current.snapshot) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The Simbli agenda-item state changed after planning.")
        if prepared["no_op"]:
            if persist and persist({"resource_id": str(change.resource_id), "no_send": True}):
                raise WriteCancelled()
            return {
                "state": "succeeded",
                "resource_id": str(change.resource_id),
                "readback": current.snapshot,
                "reconciled": True,
                "no_send": True,
                "reason": "Desired title already present; no mutation sent.",
            }
        session.require(7)
        self._authorize_commit(source, change, context)
        lock_item_id = current.selected["ID"]
        lock_dto = current.page["lock_dto"]
        if persist and persist({"resource_id": str(change.resource_id), "lock_attempted": True}):
            raise WriteCancelled()
        result = None
        release_error = False
        mutation_attempted = False
        try:
            self._authorize_commit(source, change, context)
            session.reserve_cleanup = True
            self._lock(session, current.page, lock_item_id, lock_dto, bounds)
            post_lock = self._read_tree_details(session, current.page, change, bounds)
            if post_lock.selected["ID"] != lock_item_id:
                raise WriteFailure("conflict", "The locked Simbli native item identity changed before save.")
            if canonical_hash(post_lock.snapshot) != prepared["before_fingerprint"]:
                raise WriteFailure(
                    "conflict", "The Simbli agenda-item state changed while the lock was acquired."
                )
            if context.check_cancelled():
                raise WriteCancelled()
            if monotonic() >= deadline:
                raise WriteFailure("deadline_exceeded", "The Simbli save deadline expired.")
            self._authorize_commit(source, change, context)
            details = deepcopy(post_lock.details["ItemDetails"])
            details["Title"] = change.fields["title"]
            contents = deepcopy(post_lock.details["ItemContents"])
            for field in contents:
                field["IsEdit"] = True
            body = {"EncrID": lock_item_id, "itemDetailsDTO": details, "itemContentDTO": contents}
            if persist and persist({"resource_id": str(change.resource_id), "mutation_attempted": True}):
                raise WriteCancelled()
            self._authorize_commit(source, change, context)
            mutation_attempted = True
            self._save(session, current.page, lock_item_id, body)
            try:
                readback = self._read_tree_details(session, current.page, change, bounds)
                if _matches_after(prepared, readback.snapshot, change):
                    result = {
                        "state": "succeeded",
                        "resource_id": str(change.resource_id),
                        "readback": readback.snapshot,
                        "reconciled": True,
                    }
                else:
                    result = {
                        "state": "uncertain",
                        "resource_id": str(change.resource_id),
                        "readback": readback.snapshot,
                        "reason": "The independent Simbli readback did not preserve every unrelated field.",
                    }
            except (WriteFailure, ValueError, AmbiguousWrite, TypeError):
                result = {
                    "state": "uncertain",
                    "resource_id": str(change.resource_id),
                    "reason": "The Simbli save was sent but exact readback could not confirm it.",
                }
        except (WriteFailure, ValueError, TypeError):
            if not mutation_attempted:
                raise
            result = {
                "state": "uncertain",
                "resource_id": str(change.resource_id),
                "reason": "The Simbli save was sent; its outcome requires read-only reconciliation.",
            }
        finally:
            try:
                self._release(session, current.page, lock_item_id, lock_dto)
                if persist:
                    persist({"lock_release_confirmed": True})
            except Exception:
                release_error = True
                if persist:
                    try:
                        persist({"lock_release_error": True})
                    except Exception:
                        pass
        if result is None:
            raise AmbiguousWrite("The Simbli save outcome is uncertain.")
        if release_error:
            result["lock_release_error"] = True
        return result

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        if prepared.get("change", {}).get("entity") == "agenda_item_attachment":
            return self._supporting().reconcile(source, prepared, item, context, bounds, deadline)
        change, before, after = self._validate_prepared(source, prepared, context, bounds)
        config = self.credentials(source, context)
        if context.check_cancelled():
            raise WriteCancelled()
        session = _Requests(self.transport, config, context, bounds, deadline)
        session.require(3)
        current = self._read_current(session, source, config, change, bounds)
        if not item.get("mutation_attempted") and not item.get("no_send"):
            return {
                "state": "uncertain",
                "resource_id": str(change.resource_id),
                "readback": current.snapshot,
                "reason": "No durable mutation attempt exists; a matching title alone cannot confirm this intent.",
            }
        if item.get("no_send"):
            matched = canonical_hash(current.snapshot) == prepared["before_fingerprint"]
            return {
                "state": "succeeded" if matched else "uncertain",
                "resource_id": str(change.resource_id),
                "readback": current.snapshot,
                "reconciled": True,
                "no_send": True,
            }
        matched = _matches_after(prepared, current.snapshot, change)
        return {
            "state": "succeeded" if matched else "uncertain",
            "resource_id": str(change.resource_id),
            "readback": current.snapshot,
            "reconciled": True,
            "reason": "Exact read-only Simbli reconciliation."
            if matched
            else "The independent Simbli readback preserved unrelated fields but the target title did not match.",
        }


def _expect(response, *, ambiguous):
    if response.status in {401, 403}:
        raise WriteFailure("permission_denied", "Simbli denied the operation.")
    if response.status in {409, 412}:
        raise WriteFailure("conflict", "Simbli rejected a conflicting change.")
    if not 200 <= response.status < 300:
        if ambiguous and (response.status >= 500 or response.status in {408, 429}):
            raise AmbiguousWrite()
        raise WriteFailure("provider_rejected", "Simbli rejected the request.")
