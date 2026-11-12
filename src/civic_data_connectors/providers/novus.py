"""Observed NovusAGENDA public form/listing mechanics, never staff actions."""
from __future__ import annotations

from datetime import datetime
import hashlib
from copy import deepcopy
from email.message import Message
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import RetrievalError, _origin
from .native import make_bundle

FORMAT = "novus-public-listing-html"
_SESSION_LOCK = Lock()


def _copy_state(state):
    # CookieJar owns an RLock and is not deepcopy/pickle compatible. Copy only
    # its cookie records into a new in-memory jar; never serialize it publicly.
    copied = deepcopy({key: value for key, value in state.items() if key != "cookies"})
    copied["cookies"] = CookieJar()
    for cookie in state["cookies"]:
        copied["cookies"].set_cookie(deepcopy(cookie))
    return copied


class _Sessions:
    """Opaque scoped continuations; anonymous cookies never leave this process."""

    def __init__(self):
        self.values = {}
        self.payloads = {}
        self.max_bytes = 32 * 1024**2
        self.lock = Lock()

    def _prune(self):
        for key, value in list(self.values.items()):
            if value["expires"] <= monotonic():
                del self.values[key]
        used = {value["digest"] for value in self.values.values()}
        self.payloads = {key: value for key, value in self.payloads.items() if key in used}

    def get(self, token, binding):
        with self.lock:
            self._prune()
            value = self.values.get(token)
            if value is None or value["binding"] != binding:
                raise ValueError("Novus continuation expired, belongs to another caller/source, or its engine restarted.")
            return {**_copy_state(value["state"]), "content": self.payloads[value["digest"]]}

    def put(self, state, binding):
        size = 1024 + 64 * len(state["seen"]) + sum(
            len(str(cookie)) for cookie in state["cookies"])
        digest = hashlib.sha256(state["content"]).hexdigest()
        private = {key: value for key, value in state.items() if key != "content"}
        fingerprint = canonical_hash({"binding": binding, "digest": digest,
            "offset": state["offset"], "grid_pages": state["grid_pages"], "seen": sorted(state["seen"]),
            "exhausted": sorted(state["exhausted"]), "pending": state["pending"],
            "cookies": sorted((cookie.domain, cookie.path, cookie.name, cookie.value) for cookie in state["cookies"])})
        with self.lock:
            self._prune()
            for token, value in self.values.items():
                if value["fingerprint"] == fingerprint:
                    return token  # Retry the same immutable cursor without consuming more capacity.
            payload_size = 0 if digest in self.payloads else len(state["content"])
            if (sum(v["size"] for v in self.values.values()) + size + payload_size +
                    sum(len(value) for value in self.payloads.values()) > self.max_bytes):
                raise ValueError("Novus continuation capacity reached; wait for expiry or use narrower bounds.")
            token = "novus:" + secrets.token_hex(24)
            self.payloads.setdefault(digest, state["content"])
            self.values[token] = {"binding": binding, "state": _copy_state(private), "digest": digest,
                                  "fingerprint": fingerprint, "size": size, "expires": monotonic() + 900}
            return token


def _sessions(engine):
    with _SESSION_LOCK:
        value = getattr(engine, "_novus_sessions", None)
        if value is None:
            value = engine._novus_sessions = _Sessions()
        return value


def _cookies(jar, response, url):
    message = Message()
    values = response.set_cookie_headers
    if len(values) > 32 or any(len(value) > 8192 or "\r" in value or "\n" in value for value in values):
        raise ValueError("The public session cookie headers exceed supported bounds.")
    for value in values:
        message.add_header("Set-Cookie", value)
    class CookieResponse:
        def info(self):
            return message
    jar.extract_cookies(CookieResponse(), Request(url))
    if len(jar) > 32:
        raise ValueError("The public session returned too many cookies.")


class Listing(HTMLParser):
    """Parse data/form controls without evaluating source JavaScript."""

    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.controls, self.rows, self.next_targets = {}, [], {}
        self.tables, self.row, self.cell, self.select, self.option = [], None, None, None, None
        self.form = False
        self.action = None
        self.current_pages, self.current_anchor, self.anchor_text = {}, None, []
        self.invalid_next = False
        self.feed(content.decode("utf-8-sig"))
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "aspnetForm":
            self.form, self.action = True, attrs.get("action")
        if self.form and tag == "input" and attrs.get("name") and "disabled" not in attrs:
            kind = attrs.get("type", "text").lower()
            if kind in {"hidden", "text", "search", "number"} or (
                    kind in {"checkbox", "radio"} and "checked" in attrs):
                self.controls[attrs["name"]] = attrs.get("value", "")
        if self.form and tag == "select" and attrs.get("name") and "disabled" not in attrs:
            self.select = {"name": attrs["name"], "options": []}
        if self.select is not None and tag == "option":
            self.option = {"value": attrs.get("value"), "selected": "selected" in attrs, "text": []}
        if tag == "table":
            identity = attrs.get("id", "")
            grid = ("meeting" if "radGridMeetings_ctl00" in identity else
                    "agenda_item" if "radGridItems_ctl00" in identity else
                    self.tables[-1] if self.tables else None)
            self.tables.append(grid)
        grid = self.tables[-1] if self.tables else None
        if tag == "tr" and grid and set(attrs.get("class", "").split()) & {"rgRow", "rgAltRow"}:
            self.row = {"kind": grid, "attributes": attrs, "cells": [], "links": []}
        if tag == "td" and self.row is not None:
            self.cell = []
        if tag == "a":
            if grid and "rgCurrentPage" in attrs.get("class", "").split():
                self.current_anchor, self.anchor_text = grid, []
            if self.row is not None:
                self.row["links"].append(attrs)
            target = re.fullmatch(r"javascript:__doPostBack\('([^']+)',''\)", attrs.get("href", ""))
            if grid and attrs.get("title", "").casefold() == "next page" and not target:
                self.invalid_next = True
            if grid and attrs.get("title", "").casefold() == "next page" and target:
                expected = "radGridMeetings" if grid == "meeting" else "radGridItems"
                if re.fullmatch(r"ctl00\$ContentPlaceHolder1\$SearchAgendasMeetings\$" + expected +
                                r"\$ctl\d+\$ctl\d+\$ctl\d+\$ctl\d+", target[1]):
                    self.next_targets[grid] = target[1]
                else:
                    self.invalid_next = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.current_anchor:
            self.anchor_text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.option is not None:
            self.option["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_anchor:
            text = "".join(self.anchor_text).strip()
            if text.isdecimal():
                self.current_pages[self.current_anchor] = int(text)
            self.current_anchor = None
        if tag == "option" and self.select is not None and self.option is not None:
            self.select["options"].append(self.option)
            self.option = None
        if tag == "select" and self.select is not None:
            choices = self.select["options"]
            if choices:
                selected = next((item for item in choices if item["selected"]), choices[0])
                self.controls[self.select["name"]] = selected["value"] or "".join(selected["text"])
            self.select = None
        if tag == "td" and self.row is not None and self.cell is not None:
            self.row["cells"].append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row, self.cell = None, None
        if tag == "table" and self.tables:
            self.tables.pop()
        if tag == "form":
            self.form = False

    def window(self):
        prefix = "ctl00$ContentPlaceHolder1$SearchAgendasMeetings$radCalendar"
        values = [self.controls.get(prefix + part) for part in ("From", "To")]
        try:
            return [datetime.strptime(value, "%Y-%m-%d").date().isoformat() for value in values]
        except (TypeError, ValueError):
            return [None, None]


def listing_bundle(source, namespace, content, *, page_number=1):
    parsed = Listing(content)
    if parsed.action is None or not any("radGrid" in key for key in parsed.controls):
        raise ValueError("Response is not the observed public Novus listing form.")
    rows = []
    positions = {"meeting": 0, "agenda_item": 0}
    for raw in parsed.rows:
        cells, kind = raw["cells"], raw["kind"]
        position = positions[kind]
        positions[kind] += 1
        grid_page = page_number.get(kind, 1) if isinstance(page_number, dict) else page_number
        if len(cells) < (3 if kind == "meeting" else 5):
            raise ValueError("The public listing row shape changed; retain its saved response for review.")
        day = None
        for fmt in ("%m/%d/%y", "%m/%d/%Y"):
            try:
                day = datetime.strptime(cells[0], fmt).date().isoformat()
                break
            except ValueError:
                pass
        links, provider_id, parent_id = [], None, None
        for link in raw["links"]:
            candidates = [link.get("href", "")]
            candidates.extend(re.findall(r"(?:Coversheet|MeetingView)\.aspx\?[^'\"\s)]+",
                                         link.get("onclick", ""), re.I))
            for candidate in candidates:
                if not candidate or candidate.startswith(("#", "javascript:")):
                    continue
                url = urljoin(source.url, candidate)
                parts = urlsplit(url)
                if (parts.scheme != "https" or parts.netloc != urlsplit(source.url).netloc
                        or not parts.path.lower().startswith("/agendapublic/")):
                    continue
                links.append(url)
                query = {key.casefold(): value for key, value in parse_qs(parts.query).items()}
                meeting = (query.get("meetingid") or [""])[0]
                item = (query.get("itemid") or [""])[0]
                if kind == "agenda_item" and item.isdecimal() and meeting.isdecimal():
                    provider_id, parent_id = item, meeting
                elif kind == "meeting" and meeting.isdecimal():
                    provider_id = meeting
        external_id = provider_id or "derived:" + canonical_hash(
            [source.url, kind, grid_page, position, cells])
        normalized = {"external_id": external_id, "meeting_date": day, "source_date": cells[0],
            "title": cells[1], "meeting_type": cells[1] if kind == "meeting" else cells[3],
            "location": cells[2] if kind == "meeting" else cells[4],
            "category": None if kind == "meeting" else cells[2],
            "url": next((link for link in links if "MeetingID=" in link), links[0] if links else source.url),
            "documents": [{"url": link, "kind": "linked_source"} for link in links
                          if "Boards.aspx" not in link],
            "agenda_items_availability": "separate_listing", "time_zone_status": "unknown",
            "source_position": {"page": grid_page, "row": position}}
        if parent_id:
            normalized["meeting_external_id"] = parent_id
        rows.append((normalized, raw, kind))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"]:
        if record["identity"]["external_id"].startswith("derived:"):
            record["identity"]["derivation"] = "capture_position_and_fields"
            record["identity"]["stability"] = (
                "No provider ID was supplied; identity changes if page order or displayed fields change.")
        if parent := record["normalized"].get("meeting_external_id"):
            identity = {"provider": source.provider, "namespace": namespace,
                        "record_type": "meeting", "external_id": parent, "parent": None}
            record["identity"]["parent"] = identity
            record["relationships"].append({"relation": "meeting", "identity": identity})
    bundle["extensions"]["observed_window"] = parsed.window()
    return bundle, parsed


def _source_url(source):
    parts = urlsplit(source.url)
    if (parts.scheme != "https" or not parts.hostname.endswith(".novusagenda.com")
            or parts.path.casefold() != "/agendapublic/" or parts.query or parts.fragment):
        raise ValueError("Novus public discovery requires an explicit HTTPS tenant /agendapublic/ source URL.")
    return source.url


def discover_public(engine, source, namespace, bounds, context, transport, *, saved=None, record_types=None):
    """Traverse only fresh public Next Page controls, with local explicit filters."""
    url = _source_url(source)
    types = record_types or []
    if not isinstance(types, list) or set(types) - {"meeting", "agenda_item"}:
        raise ValueError("Novus record_types must select meeting or agenda_item.")
    binding = canonical_hash({"source": source.public_dict(), "scope": context.scope,
        "date_from": bounds.date_from, "date_to": bounds.date_to, "record_types": types,
        "saved_sha256": hashlib.sha256(saved).hexdigest() if saved is not None else None})
    cache = _sessions(engine)
    state = cache.get(bounds.checkpoint, binding) if bounds.checkpoint else {
        "content": None, "cookies": CookieJar(), "offset": 0, "grid_pages": {"meeting": 1, "agenda_item": 1},
        "seen": set(), "exhausted": set(), "pending": None}
    deadline, records, bundles, errors, failures = monotonic() + bounds.deadline_seconds, [], [], [], []
    pages, filtered, unknown_dates, unknown_bodies = 0, 0, [], []
    observed_window, finished, previous_signature = [None, None], False, None
    try:
        while pages < bounds.max_pages and len(records) < bounds.max_records:
            if context.check_cancelled() or monotonic() >= deadline:
                break
            if state["content"] is None or state["pending"] is not None:
                if saved is not None:
                    if state["pending"] is not None:
                        break
                    content, response = saved, None
                else:
                    headers, body, method = {"Accept": "text/html"}, None, "GET"
                    if state["pending"] is not None:
                        current = Listing(state["content"])
                        kind = state["pending"]
                        target = current.next_targets.get(kind)
                        if target is None or urljoin(url, current.action or "") != url:
                            raise ValueError("The current public page has no validated next-page action.")
                        controls = {**current.controls, "__EVENTTARGET": target, "__EVENTARGUMENT": ""}
                        body, method = urlencode(controls).encode(), "POST"
                        if len(body) > bounds.parser_bytes:
                            raise ValueError("Public pager controls exceed parser bounds.")
                        headers["Content-Type"] = "application/x-www-form-urlencoded"
                        previous_signature = canonical_hash([row for row in current.rows if row["kind"] == kind])
                    cookie_request = Request(url)
                    state["cookies"].add_cookie_header(cookie_request)
                    if cookie_request.has_header("Cookie"):
                        headers["Cookie"] = cookie_request.get_header("Cookie")
                    response = transport.request(url, method=method, body=body, headers=headers,
                        byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                        allowed_origins=(_origin(url),))
                    if response.status != 200:
                        raise RetrievalError("provider_http_error", status=response.status)
                    if response.url != url:
                        raise ValueError("Public pager response left the exact configured endpoint.")
                    content = response.content
                if len(content) > bounds.parser_bytes or monotonic() >= deadline:
                    raise ValueError("The public listing exceeded parser/deadline bounds.")
                if context.check_cancelled():
                    break
                parsed = Listing(content)
                if urljoin(url, parsed.action or "") != url:
                    raise ValueError("Public form action left the configured endpoint.")
                if state["pending"] is not None:
                    kind = state["pending"]
                    next_page = state["grid_pages"][kind] + 1
                    actual = parsed.current_pages.get(kind)
                    if (actual is not None and actual != next_page) or (actual is None and
                            canonical_hash([row for row in parsed.rows if row["kind"] == kind]) == previous_signature):
                        raise ValueError("The public pager did not advance its selected grid.")
                    state["grid_pages"][kind] = next_page
                if response is not None:
                    _cookies(state["cookies"], response, url)
                state["content"], state["offset"], state["pending"] = content, 0, None
            if len(state["content"]) > bounds.parser_bytes:
                raise ValueError("The continued public listing exceeds current parser bounds.")
            bundle, parsed = listing_bundle(source, namespace, state["content"], page_number=state["grid_pages"])
            if parsed.invalid_next:
                raise ValueError("The public Next Page action has no verified safe mapping.")
            observed_window = parsed.window()
            rows, selected = bundle["records"], []
            pages += 1
            for index in range(state["offset"], len(rows)):
                if len(records) >= bounds.max_records or context.check_cancelled() or monotonic() >= deadline:
                    break
                state["offset"] = index + 1
                record = rows[index]
                key = source_identity_key(record["identity"])
                if key in state["seen"]:
                    continue
                state["seen"].add(key)
                day, body = record["normalized"].get("meeting_date"), record["normalized"].get("body")
                if ((day and ((bounds.date_from and day < bounds.date_from) or (bounds.date_to and day > bounds.date_to)))
                        or (types and record["identity"]["record_type"] not in types)
                        or (source.body and body and body.casefold() != source.body.casefold())):
                    filtered += 1
                    continue
                if not day and (bounds.date_from or bounds.date_to):
                    unknown_dates.append(record["identity"]["external_id"])
                if source.body and not body:
                    unknown_bodies.append(record["identity"]["external_id"])
                selected.append(record)
                records.append(record)
            bundle["records"] = selected
            bundles.append(bundle)
            if state["offset"] == len(rows):
                for kind in ("agenda_item", "meeting"):
                    if kind not in parsed.next_targets:
                        state["exhausted"].add(kind)
                state["pending"] = next((kind for kind in ("agenda_item", "meeting")
                    if kind not in state["exhausted"] and kind in parsed.next_targets), None)
                if state["pending"] is None:
                    finished = True
                    break
                if saved is not None:
                    break
            context.report(operation="discover", pages=pages, returned_records=len(records))
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "novus_public_page_failed"
        details = {"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {}
        failures.append({"page": pages + 1, "reason": code, **details})
        errors.append(Error(code, "A public Novus listing page could not be retrieved, verified or parsed. "
            "Retained continuation can retry under the same source and caller; it expires with this engine session.",
            retryable=True, source=url, details=details))
    checkpoint = None
    if not finished and state["content"] is not None:
        try:
            checkpoint = cache.put(state, binding)
        except ValueError:
            failures.append({"reason": "novus_continuation_capacity"})
            errors.append(Error("novus_continuation_capacity", "Continuation capacity is exhausted; "
                "no active sessions were evicted. Restart with broader per-call record bounds or wait for expiry.", source=url))
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace, "input_format": FORMAT}],
        "scope": "observed public listing window only; complete archive/search semantics unverified",
        "catalog_complete": False, "source_complete": False, "listing_exhausted": finished,
        "observed_window": observed_window, "date_from": bounds.date_from, "date_to": bounds.date_to,
        "body": source.body, "record_types": types, "pages": pages, "returned_records": len(records),
        "filtered_records": filtered, "unknown_date_records": unknown_dates, "unknown_body_records": unknown_bodies,
        "failures": failures, "failed_pages": failures, "truncated": not finished,
        "checkpoint": checkpoint, "checkpoint_lifetime": "15 minutes; current engine process only",
        "snapshot_consistency": "not_guaranteed", "deadline_exceeded": monotonic() >= deadline,
        "available_text": "displayed_metadata_and_links_only"}
    status = "cancelled" if context.check_cancelled() else "failed" if failures and not bundles else "partial"
    return OperationResult(status, {"source": source.public_dict(), "records": records, "bundles": bundles,
                                   "captures": [bundle["capture"] for bundle in bundles]}, tuple(errors), coverage,
                           context.operation_id)
