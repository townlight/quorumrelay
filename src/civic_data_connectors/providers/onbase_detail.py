"""Captured Agenda Online meeting, accessible agenda and membership-bound item reads."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import re
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from ..engine import canonical_hash
from ..models import Error, OperationResult
from .contracts import _origin
from .escribe_detail import Page
from .native import make_bundle

FORMAT = "onbase-public-listing-html"


def _query(url):
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if len(dict(pairs)) != len(pairs):
        raise ValueError("OnBase detail queries must be unambiguous.")
    return dict(pairs)


def _positive(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None


def _context(source, endpoint, keys):
    from .identification import validate_url
    validate_url(source.url)
    parsed, values = urlsplit(source.url), _query(source.url)
    match = re.fullmatch(r"(/OnBaseAgendaOnline)/Meetings/" + endpoint, parsed.path, re.I)
    if parsed.scheme != "https" or match is None or set(values) != keys:
        raise ValueError("Use the exact supplied public OnBase detail context.")
    meeting = values.get("meetingId", values.get("id"))
    if not _positive(meeting):
        raise ValueError("The detail context needs a native meeting ID.")
    return match[1], meeting, values


def _page(content):
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    main = [node for node in page.root.walk() if node.tag == "section" and "main-content" in node.classes()]
    if len(main) != 1:
        raise ValueError("The public detail must supply one main content area.")
    return main[0]


def _parent(source, namespace, meeting):
    return {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
            "external_id": meeting, "parent": None}


def _text(record, text, field):
    record["text"] = [{"field": field, "text": text, "citation_url": record["source_url"],
        "completeness": "partial", "provenance": {"method": "onbase_supplied_rendered_html",
        "capture_sha256": record["capture_sha256"], "scope": "selected_rendered_content_only"}}]


def wrapper_bundle(source, namespace, content):
    prefix, meeting, values = _context(source, "ViewMeeting", {"id", "doctype"})
    if values["doctype"] != "1":
        raise ValueError("Only the observed Agenda view is mapped.")
    main = _page(content)
    if len([node for node in main.walk() if node.attrs.get("id") == "agenda-table"]) != 1:
        raise ValueError("The supplied page is not the observed meeting view.")
    literal = prefix + "/Meetings/ViewMeetingAgenda?meetingId=" + meeting + "&type=AGENDATYPEVALUE"
    text = content.decode("utf-8-sig")
    if "'" + literal + "'" not in text or not re.search(r"var\s+g_documentType\s*=\s*'1'\s*;", text):
        raise ValueError("The meeting view does not declare the exact selected accessible agenda.")
    documents, links = [], []
    for node in main.walk():
        if node.tag != "a" or not node.attrs.get("href"):
            continue
        links.append({"text": node.text(), "attributes": deepcopy(node.attrs)})
        target = urljoin(source.url, node.attrs["href"])
        parsed = urlsplit(target)
        if "/documents/downloadfile/" not in parsed.path.lower():
            continue
        query = _query(target)
        if (_origin(target) != _origin(source.url) or parsed.fragment or not parsed.path.startswith(prefix + "/")
                or query.get("meetingId") != meeting or query.get("documentType") not in {"1", "2", "3", "5", "6"}
                or set(query) - {"meetingId", "documentType", "isAttachment"}):
            raise ValueError("A supplied meeting document left its selected meeting scope.")
        documents.append({"url": target, "kind": {"1": "agenda", "2": "minutes", "3": "summary",
            "5": "packet", "6": "attachment"}[query["documentType"]], "title": node.text(),
            "availability": "supplied_locator_not_fetched"})
    agenda = _origin(source.url) + literal.replace("AGENDATYPEVALUE", "agenda")
    normalized = {"external_id": meeting, "title": None, "url": source.url, "documents": documents,
                  "accessible_agenda_url": agenda, "time_zone_status": "unknown",
                  "agenda_items_availability": "separate_declared_view"}
    return make_bundle(source, namespace, content, FORMAT,
                       [(normalized, {"links": links, "accessible_agenda_locator": literal}, "meeting")])


def agenda_bundle(source, namespace, content):
    prefix, meeting, values = _context(source, "ViewMeetingAgenda", {"meetingId", "type"})
    if values["type"] != "agenda":
        raise ValueError("Only the supplied accessible Agenda variant is mapped.")
    main = _page(content)
    headers = [node for node in main.walk() if node.tag == "h1" and "accessible-header" not in node.classes()]
    if len(headers) != 1:
        raise ValueError("The accessible agenda must supply a unique meeting header.")
    header = headers[0].text()
    parts = re.fullmatch(r"(.+?)\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} [AP]M)", header)
    if parts is None:
        raise ValueError("The supplied meeting title/time header is not mapped.")
    start = datetime.strptime(parts[2], "%m/%d/%Y %I:%M:%S %p")
    entries, sections, seen = [], {}, set()
    for link in main.walk():
        if link.tag != "a":
            continue
        action = link.attrs.get("onclick", "")
        match = re.fullmatch(r"loadAgenda(Section|Item)\(([1-9][0-9]{0,18})\);\s*return false;", action)
        if not match:
            if "loadAgenda" in action:
                raise ValueError("An agenda control has an unmapped supplied identity.")
            continue
        kind = "agenda_section" if match[1] == "Section" else "agenda_item"
        key = (kind, match[2])
        if key in seen:
            raise ValueError("The agenda repeats a native child identity.")
        seen.add(key)
        titles = [node.text() for node in link.walk() if node.tag == "span" and
                  ("accessible-header-text" if kind == "agenda_section" else "accessible-item-text") in node.classes()]
        if len(titles) != 1 or not titles[0]:
            raise ValueError("A supplied child has no unique rendered title.")
        container = link.parent
        while container and "accessible-section" not in container.classes():
            container = container.parent
        if kind == "agenda_section":
            if container is None or container in sections:
                raise ValueError("The section hierarchy is ambiguous.")
            sections[container] = match[2]
        entries.append((link, container, match[2], kind, titles[0]))
    if not entries:
        raise ValueError("No supplied agenda hierarchy was found; empty-page semantics are unverified.")
    detail = _origin(source.url) + prefix + "/Meetings/ViewMeeting?" + urlencode({"id": meeting, "doctype": 1})
    common = {"meeting_date": start.date().isoformat(), "time_zone_status": "unknown"}
    rows = [({"external_id": meeting, "title": parts[1], "source_start": start.isoformat(),
              "source_time_literal": parts[2], "url": detail, "documents": [],
              "agenda_items_availability": "supplied_rendered_hierarchy", **common},
             {"header": header}, "meeting")]
    for link, container, identity, kind, title in entries:
        ancestor = container.parent if kind == "agenda_section" else container
        while ancestor and ancestor not in sections:
            ancestor = ancestor.parent
        parent_section = sections.get(ancestor)
        rows.append(({"external_id": identity, "title": title, "url": source.url,
            "meeting_external_id": meeting, "parent_section_external_id": parent_section,
            "is_section": kind == "agenda_section", "display_label": link.text().removesuffix(title).strip(),
            "content_availability": "supplied_title_only", **common},
            {"attributes": deepcopy(link.attrs), "rendered_text": link.text()}, kind))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    parent = _parent(source, namespace, meeting)
    meeting_record = bundle["records"][0]
    meeting_record["normalized"].update(agenda_items=[], agenda_sections=[])
    for record in bundle["records"]:
        _text(record, main.text() if record["identity"]["record_type"] == "meeting" else record["normalized"]["title"],
              "agenda.rendered_text")
        if record["identity"]["record_type"] == "meeting":
            continue
        record["identity"]["parent"] = deepcopy(parent)
        field = "agenda_sections" if record["identity"]["record_type"] == "agenda_section" else "agenda_items"
        meeting_record["normalized"][field].append(deepcopy(record["normalized"]))
        meeting_record["relationships"].append({"relation": record["identity"]["record_type"],
                                                "identity": deepcopy(record["identity"])})
        record["relationships"].append({"relation": "meeting", "identity": deepcopy(parent)})
        section = record["normalized"]["parent_section_external_id"]
        if section:
            record["relationships"].append({"relation": "parent_agenda_section", "identity": {
                **parent, "record_type": "agenda_section", "external_id": section, "parent": deepcopy(parent)}})
    meeting_record["normalized_sha256"] = canonical_hash(meeting_record["normalized"])
    return bundle


def item_bundle(source, namespace, content):
    prefix, meeting, values = _context(source, "ViewMeetingAgendaItem", {"meetingId", "itemId", "isSection", "type"})
    item = values["itemId"]
    if not _positive(item) or values["isSection"] not in {"false", "true"} or values["type"] != "agenda":
        raise ValueError("Only the supplied agenda item/section variants are mapped.")
    section = values["isSection"] == "true"
    main = _page(content)
    titles = [node.text() for node in main.walk() if "item-view-title-text" in node.classes()]
    if len(titles) != 1 or not titles[0]:
        raise ValueError("The item must supply one rendered native-item title.")
    documents, links = [], []
    for link in main.walk():
        if link.tag != "a" or not link.attrs.get("id", "").startswith("lnkAttachment_"):
            continue
        if section:
            raise ValueError("Section attachment semantics are not established.")
        identity = link.attrs["id"].removeprefix("lnkAttachment_")
        target = urljoin(source.url, link.attrs.get("href", ""))
        parsed, query = urlsplit(target), _query(target)
        if (not _positive(identity) or _origin(target) != _origin(source.url) or parsed.fragment
                or not parsed.path.lower().startswith(prefix.lower() + "/documents/downloadfile/")
                or set(query) != {"meetingId", "itemId", "publishId", "documentType", "isSection", "isAttachment"}
                or query["meetingId"] != meeting or query["itemId"] != item or not _positive(query["publishId"])
                or query["documentType"] != "1" or query["isSection"].lower() != "false"
                or query["isAttachment"].lower() != "true"):
            raise ValueError("The attachment does not belong to the exact selected meeting/item.")
        if any(document["external_id"] == identity for document in documents):
            raise ValueError("Repeated item attachment identity.")
        documents.append({"external_id": identity, "title": link.text(), "url": target,
            "kind": "supporting_document", "meeting_external_id": meeting, "agenda_item_external_id": item,
            "publish_id": query["publishId"], "availability": "supplied_locator_not_fetched"})
        links.append({"attributes": deepcopy(link.attrs), "text": link.text()})
    bundle = make_bundle(source, namespace, content, FORMAT, [({"external_id": item, "title": titles[0],
        "url": source.url, "meeting_external_id": meeting, "documents": documents,
        "content_availability": "selected_rendered_section" if section else "selected_rendered_item",
        "time_zone_status": "unknown"},
        {"title": titles[0], "links": links}, "agenda_section" if section else "agenda_item")])
    record = bundle["records"][0]
    record["identity"]["parent"] = _parent(source, namespace, meeting)
    record["relationships"].append({"relation": "meeting", "identity": deepcopy(record["identity"]["parent"])})
    _text(record, main.text(), "section.rendered_text" if section else "item.rendered_text")
    return bundle


def parse_bundle(source, namespace, content):
    path = urlsplit(source.url).path.lower()
    if path.endswith("/viewmeetingagendaitem"):
        return item_bundle(source, namespace, content)
    if path.endswith("/viewmeetingagenda"):
        return agenda_bundle(source, namespace, content)
    return wrapper_bundle(source, namespace, content)


def fetch_detail(source, namespace, request, bounds, context, transport):
    related = "parent_id" in request
    meeting = request.get("parent_id") if related else request.get("external_id")
    kind, child = request.get("record_type"), request.get("external_id") if related else None
    if not _positive(meeting) or (child is not None and not _positive(child)):
        raise ValueError("OnBase detail requires supplied native meeting/item ID strings.")
    if related and kind not in {"agenda_item", "agenda_section"}:
        return OperationResult.unsupported("onbase_related_detail", reason="Only supplied agenda item/section detail is mapped.")
    if source.body or bounds.date_from or bounds.date_to or bounds.checkpoint:
        raise ValueError("Selected OnBase detail accepts no body/date/checkpoint filter.")
    parsed = urlsplit(source.url)
    if parsed.scheme != "https" or parsed.query or not re.fullmatch(r"/OnBaseAgendaOnline/?", parsed.path, re.I):
        raise ValueError("Configure the exact public OnBase root; detail membership is revalidated from its listing.")
    deadline, remaining = monotonic() + bounds.deadline_seconds, min(bounds.parser_bytes, bounds.transfer_bytes)
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "scope": "one current-listing meeting and supplied Agenda hierarchy/selected detail",
        "catalog_complete": False, "source_complete": False, "snapshot_consistency": "not_guaranteed",
        "pages": 0, "truncated": False, "failures": []}
    bundle, captures = None, []

    def read(url):
        nonlocal remaining
        if context.check_cancelled():
            raise InterruptedError()
        seconds = deadline - monotonic()
        if coverage["pages"] >= bounds.max_pages or remaining <= 0 or seconds <= 0:
            coverage["truncated"] = True
            raise ValueError("OnBase detail exhausted its page/byte/deadline bound.")
        limit, remaining = remaining, 0
        response = transport.request(url, headers={"Accept": "text/html"}, byte_limit=limit,
            deadline_seconds=seconds, allowed_origins=(_origin(source.url),), allow_redirects=False)
        coverage["pages"] += 1
        remaining = limit - min(limit, len(response.content))
        if context.check_cancelled():
            raise InterruptedError()
        if (response.status != 200 or response.url != url or len(response.content) > limit or monotonic() >= deadline
                or response.content_type.split(";", 1)[0].strip().lower() not in {"text/html", "application/xhtml+xml"}):
            raise ValueError("The selected detail did not satisfy its exact bounded HTML route.")
        return response.content

    def retain(data):
        captures.append(data["capture"])

    try:
        from .onbase import listing_rows
        content = read(source.url)
        listing = make_bundle(source, namespace, content, FORMAT, listing_rows(source, content))
        retain(listing)
        selected = next((record for record in listing["records"] if record["identity"]["external_id"] == meeting), None)
        if selected is None:
            raise ValueError("The selected meeting has no current supplied listing membership.")
        listing["records"] = [selected]
        bundle = listing
        target = selected["normalized"]["url"]
        wrapper_source = replace(source, url=target, input_format=FORMAT)
        prefix, identity, _ = _context(wrapper_source, "ViewMeeting", {"id", "doctype"})
        if identity != meeting or _origin(target) != _origin(source.url):
            raise ValueError("The supplied detail left its exact meeting/tenant.")
        wrapper_content = read(target)
        wrapper = wrapper_bundle(wrapper_source, namespace, wrapper_content)
        retain(wrapper)
        agenda_url = wrapper["records"][0]["normalized"]["accessible_agenda_url"]
        agenda_source = replace(source, url=agenda_url, input_format=FORMAT)
        agenda = agenda_bundle(agenda_source, namespace, read(agenda_url))
        retain(agenda)
        record = agenda["records"][0]
        record["normalized"] = {**deepcopy(selected["normalized"]), **record["normalized"]}
        documents = selected["normalized"].get("documents", []) + wrapper["records"][0]["normalized"]["documents"]
        record["normalized"]["documents"] = list({document["url"]: document for document in documents}.values())
        record["normalized_sha256"] = canonical_hash(record["normalized"])
        record["relationships"].extend({"relation": "document", "value": deepcopy(document)} for document in record["normalized"]["documents"])
        record["relationships"].extend(deepcopy(relation) for relation in selected["relationships"]
                                        if relation["relation"] == "recording")
        record["original"]["listing"] = selected["original"]
        record["original"]["meeting_view"] = wrapper["records"][0]["original"]
        record["citation_urls"] = list(dict.fromkeys([*record["citation_urls"], source.url, target]))
        bundle = agenda
        if related:
            bundle["records"] = [record for record in bundle["records"] if record["identity"]["record_type"] == kind
                                 and (child is None or record["identity"]["external_id"] == child)]
            if child and not bundle["records"]:
                raise ValueError("The selected item was not supplied by the current agenda.")
            if child:
                chosen = bundle["records"][0]
                template = prefix + "/Meetings/ViewMeetingAgendaItem?meetingId=" + meeting + "&itemId=ITEMIDVALUE&isSection=ISSECTIONVALUE&type=AGENDATYPEVALUE"
                if "'" + template + "'" not in wrapper_content.decode("utf-8-sig"):
                    raise ValueError("The meeting view does not declare this item route.")
                item_url = _origin(source.url) + template.replace("ITEMIDVALUE", child).replace("ISSECTIONVALUE", "true" if kind == "agenda_section" else "false").replace("AGENDATYPEVALUE", "agenda")
                detail = item_bundle(replace(source, url=item_url, input_format=FORMAT), namespace, read(item_url))
                current = detail["records"][0]
                if current["normalized"]["title"] != chosen["normalized"]["title"]:
                    raise ValueError("The selected item title disagreed with the current agenda.")
                retain(detail)
                current["normalized"] = {**chosen["normalized"], **current["normalized"]}
                current["normalized_sha256"] = canonical_hash(current["normalized"])
                current["relationships"].extend(relation for relation in chosen["relationships"]
                                                 if relation["relation"] == "parent_agenda_section")
                current["original"]["agenda"] = chosen["original"]
                bundle["records"] = [current]
    except InterruptedError:
        coverage["cancelled"] = True
    except Exception:
        coverage["failures"].append("onbase_detail_unavailable")
    if bundle:
        if related:
            bundle["records"] = [record for record in bundle["records"] if record["identity"]["record_type"] == kind
                                 and (child is None or record["identity"]["external_id"] == child)]
        bundle["captures"] = [capture for capture in captures if capture["sha256"] != bundle["capture"]["sha256"]]
        if len(bundle["records"]) > bounds.max_records:
            coverage["truncated"] = True
            bundle["records"] = bundle["records"][:bounds.max_records]
        bundle["compatibility"]["meetings"] = [deepcopy(record["normalized"]) for record in bundle["records"]
                                                if record["identity"]["record_type"] == "meeting"]
    errors = (Error("onbase_detail_unavailable", "Only verified supplied OnBase detail is returned; complete archive/detail coverage is not implied.",
                    source=source.url, retryable=True),) if coverage["failures"] else ()
    status = "cancelled" if coverage.get("cancelled") else "partial" if bundle and bundle["records"] else "failed"
    return OperationResult(status, bundle, errors, coverage, context.operation_id)
