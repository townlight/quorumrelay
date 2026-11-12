"""Observed public eSCRIBE DataTables search; metadata/excerpts are not full text."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import json
import re
from time import monotonic
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from ..compat import _table_rows
from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source, validate_url
from .native import make_bundle


class Languages(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.enabled, self.values = False, []
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag != "input":
            return
        if fields.get("id") == "hdnIsLanguageFilterOn":
            self.enabled = fields.get("value") == "true"
        if "chkLanguage" in fields.get("class", "").split():
            value = fields.get("value", "")
            if not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})(?:,(?:0|[1-9][0-9]{0,5}))*", value):
                raise ValueError("The public language control has an unknown shape.")
            self.values.append((value, "checked" in fields))

    def parameter(self):
        values = [value for value, checked in self.values if checked or not self.enabled]
        if not 1 <= len(values) <= 32 or len(set(values)) != len(values):
            raise ValueError("The current anonymous page does not establish its public language filter.")
        return ",".join(values) + ","


def _rows(payload, source):
    if (not isinstance(payload, dict) or type(payload.get("iTotalDisplayRecords")) is not int
            or payload["iTotalDisplayRecords"] < 0 or not isinstance(payload.get("aaData"), list)
            or len(payload["aaData"]) > 10):
        raise ValueError("The public grouped search response has an unknown count/page schema.")
    mapped, omitted = [], 0
    origin = _origin(source.url)
    for group in payload["aaData"]:
        if not isinstance(group, str):
            raise ValueError("Expected the public search's supplied grouped HTML rows.")
        table = _table_rows(group.encode())
        if not table or len(table[0]) < 2:
            raise ValueError("The search group lacks its supplied meeting heading/date.")
        heading = " ".join(table[0][0]["text"].split())
        day = datetime.strptime(" ".join(table[0][1]["text"].split()), "%B %d, %Y").date().isoformat()
        for cells in table[1:]:
            for cell in cells:
                for link in cell["links"]:
                    url = urljoin(source.url, link["url"])
                    try:
                        validate_url(url)
                    except ValueError:
                        omitted += 1
                        continue
                    parts = urlsplit(url)
                    query = parse_qs(parts.query, keep_blank_values=True)
                    if _origin(url) != origin:
                        omitted += 1
                        continue
                    parent, derived = None, False
                    if (parts.path.lower() == "/filestream.ashx" and set(query) == {"DocumentId"}
                            and len(query["DocumentId"]) == 1 and re.fullmatch(r"[0-9]+", query["DocumentId"][0])):
                        identifier, kind = query["DocumentId"][0], "document"
                    elif (parts.path.lower() == "/meeting.aspx" and len(query.get("Id", [])) == 1
                            and re.fullmatch(r"[a-fA-F0-9-]{36}", query["Id"][0])
                            and len(query.get("Item", [])) == 1 and re.fullmatch(r"[0-9]+", query["Item"][0])
                            and set(query) <= {"Id", "Item", "Tab"}):
                        parent, kind, derived = query["Id"][0], "agenda_item", True
                        identifier = "url:" + hashlib.sha256(url.encode()).hexdigest()
                    else:
                        omitted += 1
                        continue
                    text = " ".join(cell["text"].split())
                    normalized = {"external_id": identifier, "title": link["text"].strip(), "url": url,
                        "meeting_title": heading, "meeting_date": day, "time_zone_status": "unknown",
                        "search_excerpt": text}
                    if kind == "document":
                        normalized["documents"] = [{"url": url, "title": normalized["title"], "kind": "search_result"}]
                    raw = {"group_html": group, "link": deepcopy(link), "parent_meeting_id": parent,
                           "identity_from_url": derived}
                    mapped.append((normalized, raw, kind))
    return mapped, omitted


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    parts = urlsplit(source.url)
    if (parts.scheme != "https" or parts.path.lower() != "/meetingscalendarview.aspx"
            or set(parse_qs(parts.query, keep_blank_values=True)) - {"Expanded"}):
        raise ValueError("eSCRIBE native search requires the configured public MeetingsCalendarView.aspx source.")
    if content is not None or any(key in request for key in ("records", "bundle", "result")):
        raise ValueError("Native search retrieves provider candidates; saved captures use native=false.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions or any(not text.strip() for text in expressions):
        raise ValueError("Public native search requires a nonempty term or phrase.")
    if source.body or query.body:
        raise ValueError("Search group headings do not establish a governing-body filter.")
    if len(expressions[0].encode()) > min(1024, bounds.parser_bytes):
        raise ValueError("The public search expression exceeds its bound.")
    binding = canonical_hash([source.public_dict(), asdict(query), context.scope, "escribe-public-search/v1"])
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"start": 0, "offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"start", "offset", "sha256", "total", "languages", "previous_sha256"}
            or type(queue[0].get("start")) is not int or not 0 <= queue[0]["start"] <= 1000000
            or queue[0]["start"] % 10 or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 100
            or (queue[0]["offset"] > 0 and not queue[0].get("sha256"))
            or any(value is not None and (not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None)
                   for value in (queue[0].get("sha256"), queue[0].get("previous_sha256")))
            or (queue[0].get("total") is not None and (type(queue[0]["total"]) is not int or queue[0]["total"] < 0))):
        raise ValueError("Invalid public search continuation.")
    task = queue[0]
    records, bundles, errors, failures = [], [], [], []
    pages, omitted, duplicates, finished = 0, 0, 0, False
    deadline = monotonic() + bounds.deadline_seconds
    origin = _origin(source.url)
    url = origin + "/GetSearchData.asmx/GetSearchMeetingData" + ("?" + parts.query if parts.query else "")
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "scope": "public grouped provider candidates; exact local metadata and supplied excerpt matching",
        "provider_query_semantics": "provider-defined first expression; exact local AND",
        "full_document_text_searched": False, "catalog_complete": False, "source_complete": False,
        "server_date_filter": "not_applied; explicit date bounds checked locally", "snapshot_consistency": "not_guaranteed"}

    def stopped():
        return operation_cancelled(engine.storage, context) or monotonic() >= deadline

    def retrieve(target, **kwargs):
        response = (transport or PublicTransport()).request(target, byte_limit=bounds.parser_bytes,
            deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(origin,), allow_redirects=False, **kwargs)
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if response.url != target or len(response.content) > bounds.parser_bytes or monotonic() >= deadline:
            raise ValueError("Search response left its route or bounds.")
        return response.content

    try:
        if not stopped():
            language = Languages(retrieve(source.url)).parameter()
            if task.get("languages") and task["languages"] != language:
                raise ValueError("Public search language visibility changed; restart the search.")
            task["languages"] = language
        while not stopped() and pages < bounds.max_pages and len(records) < min(bounds.max_records, query.limit):
            fields = {"sEcho": "1", "iDisplayStart": str(task["start"]), "iDisplayLength": "10", "iColumns": "1",
                "sColumns": "", "mDataProp_0": "[object Object]", "sSearch": "", "bRegex": "false",
                "sSearch_0": "", "bRegex_0": "false", "bSearchable_0": "true", "bSortable_0": "true", "iSortingCols": "0",
                "searchText": expressions[0], "filterbyMeetingTypeIds": "", "filterbyMeetingTypeNames": "",
                "filterByDate": "", "filterByMeetingDocumentTypes": "", "filterByExtensions": "",
                "filterByLanguage": language, "includeConflicts": "false", "includeComments": "false"}
            raw = retrieve(url, method="POST", body=urlencode(fields).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json"})
            if stopped():
                break
            payload = json.loads(raw)
            mapped, skipped = _rows(payload, source)
            digest, total = hashlib.sha256(raw).hexdigest(), payload["iTotalDisplayRecords"]
            if ((task.get("sha256") and task["sha256"] != digest)
                    or (task.get("total") is not None and task["total"] != total)):
                raise ValueError("The resumed public search changed; restart without its checkpoint.")
            if digest == task.get("previous_sha256") and payload["aaData"]:
                raise ValueError("The public search pager repeated its previous page.")
            task.update(total=total, sha256=digest)
            if task["offset"] > len(mapped):
                raise ValueError("The public search cursor exceeds its page.")
            omitted += skipped
            bundle = make_bundle(source, namespace, raw, "escribe-search-json", mapped)
            bundle["capture"]["retrieval_url"] = url
            selected = []
            for index in range(task["offset"], len(mapped)):
                if stopped() or len(records) >= min(bounds.max_records, query.limit):
                    break
                record = bundle["records"][index]
                task["offset"] = index + 1
                if parent := record["original"]["parent_meeting_id"]:
                    identity = {"provider": source.provider, "namespace": namespace, "record_type": "meeting", "external_id": parent}
                    record["identity"]["parent"] = identity
                    record["relationships"].append({"relation": "meeting", "identity": identity})
                if record["original"]["identity_from_url"]:
                    record["identity"].update(derivation="supplied_url", stability="Local URL key; item position/query changes may change identity. No native item ID was supplied.")
                key = source_identity_key(record["identity"])
                if key not in seen:
                    selected.append(record)
                    records.append(record)
                    seen.add(key)
                else:
                    duplicates += 1
            bundle["records"] = selected
            bundles.append(bundle)
            pages += 1
            if task["offset"] == len(mapped):
                if task["start"] + 10 >= total:
                    finished = True
                    break
                if not payload["aaData"]:
                    raise ValueError("Public search returned an empty page before its declared end.")
                task = {"start": task["start"] + 10, "offset": 0, "total": total, "languages": language,
                        "previous_sha256": digest}
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        failures.append({"page": pages + 1, "reason": code})
        errors.append(Error(code, "The public eSCRIBE search page could not be retrieved or verified; restart if its result set changed.",
            retryable=True, source=source.url))
    coverage.update(pages=pages, provider_candidates=len(records), unmapped_links_omitted=omitted,
        duplicate_records_skipped=duplicates, failed_pages=failures,
        truncated=not finished, checkpoint=_checkpoint(binding, [task], seen) if not finished else None)
    matched = search_records(deepcopy(records), query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
        inherited_coverage=coverage, context=context, storage=engine.storage)
    status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if failures and not bundles else "partial"
    return OperationResult(status, {**(matched.data or {}), "bundles": bundles}, tuple(errors) + matched.errors,
                           {**matched.coverage, **coverage}, context.operation_id)
