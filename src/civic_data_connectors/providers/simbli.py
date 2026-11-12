"""Observed anonymous Simbli listing pager; no authenticated/staff actions."""
from __future__ import annotations

import ast
from datetime import datetime
import hashlib
from http.cookiejar import CookieJar
import json
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import RetrievalError, _origin
from .native import make_bundle
from .novus import _cookies, _copy_state

HOST = "https://simbli.eboardsolutions.com"
LIST = "/SB_Meetings/SB_MeetingListing.aspx"
PAGER = "/Services/api/GetMeetingListing"
_LOCK = Lock()


class Cursors:
    """Bounded immutable scoped snapshots; private page controls stay in memory."""
    def __init__(self):
        self.values, self.payloads, self.lock = {}, {}, Lock()
        self.max_bytes = 32 * 1024**2

    def prune(self):
        self.values = {k: v for k, v in self.values.items() if v["expires"] > monotonic()}
        used = {v["digest"] for v in self.values.values()}
        self.payloads = {k: v for k, v in self.payloads.items() if k in used}

    def get(self, token, binding):
        with self.lock:
            self.prune()
            value = self.values.get(token)
            if value is None or value["binding"] != binding:
                raise ValueError("Simbli continuation expired, belongs to another source/caller/filter, or its engine restarted.")
            return {**_copy_state(value["state"]), "content": self.payloads[value["digest"]]}

    def put(self, state, binding):
        digest = hashlib.sha256(state["content"]).hexdigest()
        private = {k: v for k, v in state.items() if k != "content"}
        # Include controls/cookies only in an in-process fingerprint, never in the token.
        serial = {k: v for k, v in private.items() if k not in {"cookies", "seen"}}
        serial.update(seen=sorted(state["seen"]), cookies=[str(c) for c in state["cookies"]])
        fingerprint = canonical_hash([binding, digest, serial])
        size = len(json.dumps(serial).encode()) + 1024
        with self.lock:
            self.prune()
            for token, value in self.values.items():
                if value["fingerprint"] == fingerprint:
                    return token
            needed = size + (0 if digest in self.payloads else len(state["content"]))
            if needed + sum(v["size"] for v in self.values.values()) + sum(map(len, self.payloads.values())) > self.max_bytes:
                raise ValueError("Simbli continuation capacity reached; no active sessions were evicted.")
            token = "simbli:" + secrets.token_hex(24)
            self.payloads.setdefault(digest, state["content"])
            self.values[token] = dict(binding=binding, digest=digest, state=_copy_state(private),
                size=size, fingerprint=fingerprint, expires=monotonic() + 900)
            return token


def _cache(engine):
    with _LOCK:
        if not hasattr(engine, "_simbli_cursors"):
            engine._simbli_cursors = Cursors()
        return engine._simbli_cursors


def _literal(page, name):
    match = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|false|true)\s*;", page)
    if not match:
        raise ValueError("The anonymous page lacks required published controls.")
    return {"false": False, "true": True}.get(match[1], None) if match[1] in {"false", "true"} else ast.literal_eval(match[1])


def _listing(content, district):
    page = content.decode("utf-8", errors="strict")
    marker = re.search(r"MeetingGrid_newGrid\.dataBuffer\s*=\s*(\[)", page)
    template = re.search(r"\bvar\s+meetingCustGrd\s*=\s*JSON\.parse\(('(?:[^'\\]|\\.)*')\);", page)
    if marker is None or template is None:
        raise ValueError("The public meeting listing lacks its verified row/template controls.")
    rows, _ = json.JSONDecoder().raw_decode(page, marker.start(1))
    controls = json.loads(ast.literal_eval(template[1]))
    if not isinstance(controls, dict) or _literal(page, "schoolID") != district or _literal(page, "isLoggedInUser") is not False or _literal(page, "currUserID") != "":
        raise ValueError("Only the configured anonymous public district listing is supported.")
    controls.update(RecordCount=50, SortColName="DateTime", IsSortDesc=True,
        IsUserLoggedIn=False, SchoolID=district, UserID="", TimeZone=_literal(page, "timezoneDiff"),
        ConnectionString=_literal(page, "constr"))
    return rows, controls


def _rows_bundle(source, namespace, content, rows, district, first):
    if not isinstance(rows, list) or len(rows) > 50:
        raise ValueError("The public listing returned an invalid page size.")
    mapped = []
    for raw in rows:
        if not isinstance(raw, dict) or str(raw.get("MM_DistrictID")) != district:
            raise ValueError("The public page contains invalid or cross-district rows.")
        if raw.get("ACCESS") != "P" or raw.get("MM_Status") != "1":
            continue  # Never promote a nonpublic/unpublished row.
        identifier = str(raw.get("Master_MeetingID", ""))
        title = raw.get("MM_MeetingTitle")
        if not identifier.isascii() or not identifier.isdecimal() or not isinstance(title, str) or not title.strip():
            raise ValueError("A published meeting lacks its native identity/title.")
        start = datetime.fromisoformat(raw["MM_DateTime"])
        url = HOST + "/SB_Meetings/ViewMeeting.aspx?" + urlencode({"S": district, "MID": identifier})
        documents = [{"kind": "agenda", "url": url}]
        if raw.get("CanPrintMinutes") == 1 and raw.get("MinutesStatus") == "PUBLISHED":
            documents.append({"kind": "minutes", "url": url + "&T=1"})
        mapped.append(({"external_id": identifier, "title": title.strip(), "source_start": start.isoformat(),
            "meeting_date": start.date().isoformat(), "time_zone_status": "unknown", "url": url,
            "documents": documents}, raw, "meeting"))
    return make_bundle(source, namespace, content, "simbli-html" if first else "simbli-listing-json", mapped)


def discover_public(engine, source, namespace, bounds, context, transport, *, record_types=None):
    parts = urlsplit(source.url)
    query = parse_qs(parts.query)
    district = query.get("S", [""])[0]
    if (_origin(source.url) != HOST or parts.path.lower() not in {"/index.aspx", LIST.lower()}
            or set(query) != {"S"} or len(query["S"]) != 1 or not district.isascii() or not district.isdecimal()):
        raise ValueError("Simbli automatic discovery requires the configured public index/listing with one numeric S district.")
    types = record_types or []
    if not isinstance(types, list) or set(types) - {"meeting"}:
        raise ValueError("Simbli public listing record_types supports meeting only.")
    if source.body:
        raise ValueError("The public listing does not supply a verified body field for filtering.")
    binding = canonical_hash([source.public_dict(), namespace, context.scope, bounds.date_from, bounds.date_to, types])
    cache = _cache(engine)
    state = cache.get(bounds.checkpoint, binding) if bounds.checkpoint else dict(content=None, cookies=CookieJar(),
        controls=None, offset=0, start=1, seen=set(), signatures=[], first=True, pending=False)
    deadline = monotonic() + bounds.deadline_seconds
    records, bundles, failures, errors = [], [], [], []
    pages, requests, filtered, finished = 0, 0, 0, False

    def request(url, *, method="GET", body=None):
        nonlocal requests
        if context.check_cancelled() or monotonic() >= deadline:
            raise RetrievalError("cancelled_or_deadline")
        headers = {"Accept": "application/json" if method == "POST" else "text/html, application/json"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "Authorization": "Bearer "})
            if len(body) > bounds.parser_bytes:
                raise ValueError("Public pager request exceeds parser bounds.")
        cookie_request = Request(url)
        state["cookies"].add_cookie_header(cookie_request)
        if cookie_request.has_header("Cookie"):
            headers["Cookie"] = cookie_request.get_header("Cookie")
        # This handler never consumes an authenticated browser/account session.
        if any(cookie.name.lower() == "auth_token" for cookie in state["cookies"]):
            raise ValueError("Authenticated Simbli sessions are outside this anonymous listing contract.")
        response = transport.request(url, method=method, body=body, headers=headers,
            byte_limit=bounds.parser_bytes, deadline_seconds=max(.001, deadline - monotonic()),
            allowed_origins=(HOST,), allow_redirects=False)
        requests += 1
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if response.url != url or len(response.content) > bounds.parser_bytes or monotonic() >= deadline:
            raise ValueError("The anonymous response left its exact endpoint or bounds.")
        _cookies(state["cookies"], response, url)
        if any(cookie.name.lower() == "auth_token" for cookie in state["cookies"]):
            raise ValueError("The response supplied an authenticated session outside this public contract.")
        return response.content

    try:
        while pages < bounds.max_pages and len(records) < bounds.max_records:
            if context.check_cancelled() or monotonic() >= deadline:
                break
            if state["content"] is None:
                listing_url = HOST + LIST + "?" + urlencode({"S": district})
                if parts.path.lower() == "/index.aspx":
                    landing = request(source.url).decode("utf-8", errors="strict")
                    if _literal(landing, "currUserId") != "":
                        raise ValueError("Only anonymous public menu navigation is supported.")
                    menu_url = HOST + "/CoreServices/api/Menu/GetMenu?" + urlencode({
                        "sct": _literal(landing, "sToken"), "sid": _literal(landing, "encrSiteId"),
                        "uid": "", "sessionid": _literal(landing, "sessionId")})
                    menu = json.loads(request(menu_url))
                    # Require the public menu to supply this exact route, never guess an archive URL.
                    def links(value):
                        if isinstance(value, dict):
                            return [v for k, v in value.items() if k.lower() == "url"] + [x for v in value.values() for x in links(v)]
                        return [x for v in value for x in links(v)] if isinstance(value, list) else []
                    if LIST + "?S=" + district not in links(menu):
                        raise ValueError("The anonymous menu has no verified district meeting-list route.")
                content = request(listing_url)
                rows, controls = _listing(content, district)
                state.update(content=content, controls=controls)
            elif state["pending"]:
                content = request(HOST + PAGER, method="POST", body=json.dumps({**state["controls"],
                    "RecordStart": state["start"]}, separators=(",", ":")).encode())
                rows = json.loads(content)
                _rows_bundle(source, namespace, content, rows, district, False)
                signature = canonical_hash(rows)
                if signature in state["signatures"] and rows:
                    raise ValueError("The public pager did not advance.")
                state.update(content=content, first=False, offset=0, pending=False)
            else:
                rows = _listing(state["content"], district)[0] if state["first"] else json.loads(state["content"])
            if len(state["content"]) > bounds.parser_bytes:
                raise ValueError("Continuation exceeds current parser bounds.")
            bundle = _rows_bundle(source, namespace, state["content"], rows, district, state["first"])
            signature = canonical_hash(rows)
            if signature not in state["signatures"]:
                state["signatures"].append(signature)
            selected = []
            pages += 1
            # Cursor positions refer to validated projected public rows, preserving every raw page separately.
            mapped = bundle["records"]
            for index in range(state["offset"], len(mapped)):
                if len(records) >= bounds.max_records or context.check_cancelled() or monotonic() >= deadline:
                    break
                row = mapped[index]
                key = source_identity_key(row["identity"])
                state["offset"] = index + 1
                if key in state["seen"]:
                    continue
                day = row["normalized"]["meeting_date"]
                state["seen"].add(key)
                if (bounds.date_from and day < bounds.date_from) or (bounds.date_to and day > bounds.date_to):
                    filtered += 1
                    continue
                records.append(row)
                selected.append(row)
            bundle["records"] = selected
            bundles.append(bundle)
            if state["offset"] == len(mapped):
                total = rows[0].get("MeetingsCount") if rows else None
                if len(rows) < 50 or (type(total) is int and state["start"] + len(rows) > total):
                    finished = True
                    break
                state.update(start=state["start"] + 50, pending=True)
            context.report(operation="discover", pages=pages, returned_records=len(records))
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "simbli_public_page_failed"
        detail = {"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {}
        failures.append({"page": pages + 1, "reason": code, **detail})
        errors.append(Error(code, "The anonymous Simbli page could not be retrieved or verified; private controls are not exposed.",
            retryable=True, source=source.url, details=detail))
    checkpoint = None
    if not finished and state["content"] is not None:
        try:
            checkpoint = cache.put(state, binding)
        except ValueError:
            errors.append(Error("simbli_continuation_capacity", "Continuation capacity reached; no active cursors were evicted.", source=source.url))
    coverage = dict(scope="observed anonymous public listing only; catalog completeness unverified", catalog_complete=False,
        source_complete=False, listing_exhausted=finished, snapshot_consistency="not_guaranteed",
        date_from=bounds.date_from, date_to=bounds.date_to, pages=pages, requests=requests,
        returned_records=len(records), filtered_records=filtered, failed_pages=failures, truncated=not finished,
        checkpoint=checkpoint, checkpoint_lifetime="15 minutes; current engine process only",
        deadline_exceeded=monotonic() >= deadline, available_text="listing_metadata_only")
    status = "cancelled" if context.check_cancelled() else "failed" if errors and not bundles else "partial"
    return OperationResult(status, {"source": source.public_dict(), "records": records, "bundles": bundles,
        "captures": [bundle["capture"] for bundle in bundles]}, tuple(errors), coverage, context.operation_id)
