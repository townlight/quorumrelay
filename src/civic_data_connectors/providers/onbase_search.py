"""Observed Fitchburg public search destination; capped candidates, local matching."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from html.parser import HTMLParser
import re
from time import monotonic
from urllib.parse import urlencode, urlsplit

from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport
from .escribe_detail import Page
from .identification import configured_source, validate_source
from .native import make_bundle
from .onbase import FORMAT, listing_rows

_ROOT = "https://agendas.fitchburgwi.gov/OnBaseAgendaOnline"


def _rows(source, content):
    """Keep fileless meetings using the literal agreeing row/native-ID attributes."""
    page = Page()
    page.feed(content.decode("utf-8-sig"))
    try:
        mapped = {row[0]["external_id"]: row for row in listing_rows(source, content)}
    except ValueError as error:
        if str(error) != "No dated public OnBase rows with supplied meeting identities were found.":
            raise
        mapped = {}
    result, seen = [], set()
    for node in page.root.walk():
        if node.tag != "tr" or "meeting-row" not in node.classes():
            continue
        identity = node.attrs.get("data-meeting-id", "")
        if (not re.fullmatch(r"[1-9][0-9]{0,18}", identity)
                or node.attrs.get("id") != "meeting-" + identity + "-row" or identity in seen):
            raise ValueError("The native result row identities disagree or repeat.")
        seen.add(identity)
        cells = {n.attrs["data-sortable-type"]: n.text() for n in node.walk()
                 if n.tag == "td" and "data-sortable-type" in n.attrs}
        title, time = cells.get("mtgName"), cells.get("mtgTime")
        if not title or not time:
            raise ValueError("A native search result lacks its title/date.")
        start = datetime.strptime(time, "%m/%d/%Y %I:%M:%S %p")
        if identity in mapped:
            row = mapped[identity]
            if row[0]["title"] != title or row[0]["source_start"] != start.isoformat():
                raise ValueError("Native search row metadata disagrees with its linked identity.")
        else:
            # No detail/document URL is invented for a row without supplied links.
            if any(n.tag == "a" for n in node.walk()):
                raise ValueError("A linked search row could not be mapped safely.")
            normalized = {"external_id": identity, "title": title,
                "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
                "time_zone_status": "unknown", "url": source.url, "documents": [], "recordings": [],
                "agenda_items_availability": "unverified"}
            row = (normalized, {"row_attributes": node.attrs, "cells": cells}, "meeting")
        result.append(row)
    if not seen or set(mapped) - seen:
        raise ValueError("The observed native search result rows are missing or ambiguous.")
    return result


class _SearchControls(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.keywords, self.labels = [], []
        self.selected_ranges = []
        self.date_select = False
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "Keywords":
            self.keywords.append(attrs.get("value"))
        if tag == "select":
            self.date_select = attrs.get("name") == "DateRangeOptionID"
        if tag == "option" and self.date_select and "selected" in attrs:
            self.selected_ranges.append(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.date_select = False

    def handle_data(self, value):
        self.labels.append(value)

    def validate(self, expression):
        text = " ".join(" ".join(self.labels).split())
        if (self.keywords != [expression] or self.selected_ranges != ["7"]
                or "Meeting Search Results" not in text):
            raise ValueError("The observed search result controls changed.")
        return "The Search Limit has been reached" in text


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        raise ValueError("The OnBase source namespace is outside the caller's search grant.")
    if (source.url.rstrip("/") not in {_ROOT, _ROOT + "/Meetings"}
            or source.provider != "onbase"):
        return OperationResult.unsupported("native_search", reason=(
            "Only the observed Fitchburg Agenda Online public search destination is mapped."))
    if request.get("native") is not True or content is not None or any(k in request for k in (
            "content_base64", "records", "bundle", "result")):
        raise ValueError("Native search retrieves provider candidates; saved captures use local search.")
    bounds = Bounds(**request.get("bounds", {}))
    query = _query(request.get("query", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from,
                    date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if (not expressions or not expressions[0].strip()
            or len(expressions[0].encode()) > min(4096, bounds.parser_bytes)
            or any(ord(c) < 32 or ord(c) == 127 for c in expressions[0])):
        raise ValueError("OnBase candidate search needs a bounded first term or phrase.")
    if bounds.checkpoint:
        raise ValueError("No OnBase native-search paging or continuation contract is established.")
    if source.body or query.body or (query.record_types and set(query.record_types) != {"meeting"}):
        raise ValueError("Only meeting metadata is mapped; no governing-body inference is made.")
    if ((query.providers and source.provider not in query.providers)
            or (query.namespaces and namespace not in query.namespaces)):
        raise ValueError("Query provider/namespace filters must select the configured source.")
    url = _ROOT + "/Meetings/Search?" + urlencode({"dropid": "7", "searchTerm": expressions[0]})
    deadline = monotonic() + bounds.deadline_seconds
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "catalog_complete": False, "source_complete": False, "pages": 0, "checkpoint": None,
        "provider_query_semantics": "first expression supplies candidates; provider text matching is unverified",
        "date_scope": "provider This Year option 7; server year/time zone unverified; exact dates checked locally",
        "local_match_fields": ["title", "meeting_date"], "full_document_text_searched": False,
        "pagination": "no continuation, total or terminal completeness inferred", "failures": []}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    try:
        response = (transport or PublicTransport()).request(url, headers={"Accept": "text/html"},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes),
            deadline_seconds=max(.001, deadline - monotonic()),
            allowed_origins=("https://" + urlsplit(_ROOT).netloc,), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if (monotonic() >= deadline or response.status != 200 or response.url != url
                or not isinstance(response.content, bytes)
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or response.content_type.split(";", 1)[0].strip().lower() != "text/html"):
            raise ValueError("The public search response left its exact bounded HTML contract.")
        capped = _SearchControls(response.content).validate(expressions[0])
        rows = _rows(source, response.content)
        bundle = make_bundle(source, namespace, response.content, FORMAT, rows[:bounds.max_records])
        bundle["capture"]["retrieval_url"] = url
        coverage.update(pages=1, provider_candidates=len(rows), provider_limit_reached=capped,
                        truncated=capped or len(rows) > bounds.max_records)
        context.report(operation="search", pages=1, returned_records=len(bundle["records"]))
        if capped:
            coverage["failures"].append({"reason": "provider_search_limit_reached"})
        local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k)
                  for k in ("title", "meeting_date")}} for r in bundle["records"]]
        searched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
            deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
            inherited_coverage=coverage, context=context, storage=engine.storage)
        if searched.status == "cancelled":
            return searched
        originals = {r["identity"]["external_id"]: r for r in bundle["records"]}
        data = searched.data or {}
        for hit in data.get("hits", []):
            hit["record"] = originals[hit["identity"]["external_id"]]
        data["records"] = [h["record"] for h in data.get("hits", [])]
        data["bundle"] = bundle
        return OperationResult("partial", data, searched.errors,
            {**searched.coverage, **coverage,
             "truncated": bool(coverage["truncated"] or searched.coverage.get("truncated"))}, context.operation_id)
    except Exception:
        coverage["failures"].append({"reason": "provider_search_failed"})
        return OperationResult("failed", errors=(Error("provider_search_failed",
            "The observed OnBase search could not be retrieved or mapped.", source=source.url, retryable=True),),
            coverage=coverage, operation_id=context.operation_id)
