"""Bounded, provider-specific discovery with explicit saved-response coverage."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from .contracts import PublicTransport, RetrievalError, _origin
from .identification import FORMATS, configured_source, validate_source, validate_url
from .native import parse_native

NATIVE = {"legistar", "primegov", "civicplus-select", "escribe"}
SAVED_ONLY = {"novusagenda", "tyler-meeting-manager", "boarddocs"}
DEFAULT_FORMAT = {provider: formats[-1] for provider, formats in FORMATS.items()}
DEFAULT_FORMAT.update({"primegov": "primegov-portal-json", "granicus": "granicus-listing-html",
                       "swagit": "swagit-listing-html",
                       "onbase": "onbase-public-listing-html",
                       "peak": "granicus-listing-html",
                       "towncloud": "towncloud-agenda-html", "legistar": "legistar-events-json"})


def _decode_content(request, content):
    if content is not None:
        return content
    encoded = request.get("content_base64")
    if encoded is not None:
        if not isinstance(encoded, str):
            raise ValueError("content_base64 must be a base64 string.")
        return base64.b64decode(encoded, validate=True)
    return None


def _api_source(source):
    p = urlsplit(source.url)
    if source.provider == "civicplus-select":
        host = p.hostname
        if host.endswith(".portal.civicclerk.com"):
            host = host.removesuffix(".portal.civicclerk.com") + ".api.civicclerk.com"
        if not host.endswith(".api.civicclerk.com"):
            raise ValueError("CivicClerk discovery requires a configured portal or API tenant URL.")
        return f"https://{host}/v1/Events"
    if source.provider == "legistar":
        if p.hostname == "webapi.legistar.com":
            parts = p.path.strip("/").split("/")
            if len(parts) < 2 or parts[0].lower() != "v1":
                raise ValueError("A Legistar API source must name /v1/{client}.")
            tenant = parts[1]
        elif p.hostname.endswith(".legistar.com"):
            tenant = p.hostname.removesuffix(".legistar.com")
        else:
            raise ValueError("Legistar discovery requires a configured Legistar client URL.")
        if not tenant or not all(c.isalnum() or c in "-_" for c in tenant):
            raise ValueError("The Legistar client identifier is invalid.")
        return f"https://webapi.legistar.com/v1/{tenant}/Events"
    return source.url


def _binding(source, bounds, context, input_format):
    return canonical_hash({
        "source": source.public_dict(), "dates": [bounds.date_from, bounds.date_to],
        "scope": context.scope, "input_format": input_format,
        "semantics": "inclusive-source-calendar-date/v1",
    })


def _checkpoint(binding, queue, seen):
    raw = json.dumps({"v": 1, "binding": binding, "queue": queue,
                      "seen": sorted(seen)}, separators=(",", ":")).encode()
    if len(raw) > 192 * 1024:
        raise ValueError("The checkpoint exceeds its bounded size; use narrower discovery date ranges.")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _resume(token, binding):
    if not isinstance(token, str) or len(token) > 256 * 1024:
        raise ValueError("The checkpoint is invalid or too large.")
    try:
        state = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError):
        raise ValueError("The checkpoint is not valid encoded JSON.") from None
    if not isinstance(state, dict) or state.get("v") != 1 or state.get("binding") != binding:
        raise ValueError("The checkpoint belongs to different source, filters, dates, or caller scope.")
    queue, seen = state.get("queue"), state.get("seen")
    if (not isinstance(queue, list) or len(queue) > 10000 or
            any(not isinstance(task, dict) for task in queue) or not isinstance(seen, list) or
            any(not isinstance(key, str) or len(key) != 64 for key in seen)):
        raise ValueError("The checkpoint state is invalid.")
    return queue, set(seen)


def _initial(source, bounds, input_format, saved):
    if saved:
        return [{"kind": "saved", "offset": 0}]
    provider = source.provider
    if input_format in {"meeting-export", "legistar-event-json", "wistia-media-detail-json", "wistia-caption-json"}:
        return []
    if provider in NATIVE:
        if not bounds.date_from or not bounds.date_to:
            raise ValueError("Automatic discovery requires explicit inclusive date_from and date_to.")
        if provider == "primegov":
            return [{"kind": "primegov", "upcoming": True}] + [
                {"kind": "primegov", "year": year}
                for year in range(int(bounds.date_from[:4]), int(bounds.date_to[:4]) + 1)
            ]
        return [{"kind": provider, "after": 0}] if provider == "legistar" else [{"kind": provider}]
    if provider == "wistia" and input_format == "wistia-api-media-json":
        return [{"kind": "wistia", "page": 1}]
    if provider == "champ":
        return [{"kind": "champ"}]
    if provider == "tyler-meeting-manager" and source.options.get("calendar_api_base"):
        if not bounds.date_from or not bounds.date_to:
            raise ValueError("Tyler calendar retrieval requires explicit inclusive date bounds.")
        return [{"kind": "tyler-calendar"}]
    if (provider in SAVED_ONLY and not (provider == "boarddocs" and
            urlsplit(source.url).path.lower().endswith(".pdf"))) or input_format == "meeting-export" or (
            provider == "towncloud" and input_format == "towncloud-table-json"):
        return []
    return [{"kind": "static"}]


def _page_size(source):
    value = source.options.get("page_size", 100)
    maximum = 1000 if source.provider == "legistar" else 100
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"page_size must be an integer between 1 and {maximum}.")
    return value


def _request_spec(source, bounds, task, context):
    kind = task.get("kind")
    offset = task.get("offset", 0)
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid checkpoint record offset.")
    headers, body, method = {}, None, "GET"
    p = urlsplit(source.url)
    next_day = ((date.fromisoformat(bounds.date_to) + timedelta(days=1)).isoformat()
                if bounds.date_to else None)
    size = _page_size(source)
    if kind == "static":
        url = source.url
    elif kind == "suiteone-group" and source.provider == "suiteone-media":
        if p.scheme != "https" or p.path not in {"", "/"} or p.query:
            raise ValueError("SuiteOne older groups require the configured public HTTPS root.")
        from .suiteone import form_body
        url = _origin(source.url) + "/Home/GetRecentEventsGroup"
        method, body = "POST", form_body(task.get("fields"))
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    elif kind == "agendacenter-year" and source.provider == "civicplus-agenda-center":
        if p.scheme != "https" or p.path.lower().rstrip("/") != "/agendacenter" or p.query:
            raise ValueError("Agenda Center year traversal requires its configured HTTPS root.")
        from .agendacenter import form_body
        url = _origin(source.url) + "/AgendaCenter/UpdateCategoryList"
        method, body = "POST", form_body(task.get("fields"))
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    elif kind == "towpath-year" and source.provider == "digital-towpath":
        fields = task.get("fields")
        if not isinstance(fields, dict) or set(fields) != {"url", "year"}:
            raise ValueError("Invalid Digital Towpath public year control.")
        url = fields["url"]
        validate_url(url)
        parts = urlsplit(url)
        if (_origin(url) != _origin(source.url) or parts.query or parts.scheme != "https"
                or re.fullmatch(r"/meetings/meetings/[^/]+/20[0-9]{2}", parts.path) is None
                or parts.path.rsplit("/", 1)[-1] != fields["year"]):
            raise ValueError("The Digital Towpath year control left its supplied public route.")
    elif kind == "champ" and source.provider == kind:
        event = re.fullmatch(r"/([A-Za-z0-9_-]+)/event/([0-9]+)/?", p.path)
        if p.hostname != "play.champds.com" or event is None:
            raise ValueError("CHAMP retrieval requires a configured public tenant event URL.")
        url = f"https://playapi.champds.com/{event[1]}/event/{event[2]}"
    elif kind == "tyler-calendar" and source.provider == "tyler-meeting-manager":
        base = source.options.get("calendar_api_base")
        if not isinstance(base, str):
            raise ValueError("Configure the calendar API base observed for this exact Tyler tenant.")
        validate_url(base)
        target = urlsplit(base)
        if (target.scheme != "https" or not target.hostname.endswith(".meetingmanager.tylerapp.com")
                or target.hostname != p.hostname
                or re.fullmatch(r"/tylermmcalendar[A-Za-z0-9]+/?", target.path) is None
                or target.query or target.fragment):
            raise ValueError("The configured Tyler calendar API base is not an evidenced endpoint shape.")
        url = base.rstrip("/") + "/meetingInformation/getMeetingInformationByDate"
        body = json.dumps({"startDate": date.fromisoformat(bounds.date_from).strftime("%m/%d/%Y"),
                           "endDate": date.fromisoformat(bounds.date_to).strftime("%m/%d/%Y"),
                           "meetingTypeIds": [-1]}, separators=(",", ":")).encode()
        method, headers = "POST", {"Content-Type": "application/json", "Accept": "application/json"}
    elif kind == "legistar" and source.provider == kind:
        after = task.get("after", 0)
        if type(after) is not int or after < 0:
            raise ValueError("Invalid Legistar checkpoint identifier.")
        filters = [f"EventId gt {after}"]
        if bounds.date_from:
            filters.append(f"EventDate ge datetime'{bounds.date_from}'")
        if next_day:
            filters.append(f"EventDate lt datetime'{next_day}'")
        url = _api_source(source) + "?" + urlencode({
            "$orderby": "EventId asc", "$top": size, "$filter": " and ".join(filters)})
        token = context.credentials.get("legistar_token")
        if token is not None:
            if not isinstance(token, str):
                raise ValueError("The configured Legistar credential is invalid.")
            url += "&" + urlencode({"token": token})
    elif kind == "primegov" and source.provider == kind:
        base = _origin(source.url) + "/api/v2/PublicPortal/"
        if task.get("upcoming") is True:
            url = base + "ListUpcomingMeetings"
        else:
            year = task.get("year")
            if (type(year) is not int or not bounds.date_from or not bounds.date_to or
                    not int(bounds.date_from[:4]) <= year <= int(bounds.date_to[:4])):
                raise ValueError("Invalid PrimeGov archive checkpoint year.")
            url = base + "ListArchivedMeetings?" + urlencode({"year": year})
    elif kind == "civicplus-select" and source.provider == kind:
        base = _api_source(source)
        url = task.get("next")
        if url is None:
            filters = []
            if bounds.date_from:
                filters.append(f"startDateTime ge {bounds.date_from}T00:00:00Z")
            if next_day:
                filters.append(f"startDateTime lt {next_day}T00:00:00Z")
            url = base + "?" + urlencode({
                # OData $top limits the TOTAL collection, not the server page.
                # Captured nextLinks decrement it (200 -> 185 -> 170). Omitting
                # it lets server-driven paging cover the requested date range.
                "$orderby": "startDateTime desc", "$filter": " and ".join(filters)})
        else:
            validate_url(url)
            target = urlsplit(url)
            if _origin(url) != _origin(base) or target.path.casefold() != "/v1/events":
                raise ValueError("CivicClerk pagination left the configured tenant Events collection.")
    elif kind == "escribe" and source.provider == kind:
        url = _origin(source.url) + "/MeetingsCalendarView.aspx/GetCalendarMeetings"
        body = json.dumps({"calendarStartDate": bounds.date_from,
                           "calendarEndDate": next_day}, separators=(",", ":")).encode()
        method, headers = "POST", {"Content-Type": "application/json"}
    elif kind == "wistia" and source.provider == kind:
        if p.hostname != "api.wistia.com" or p.path.rstrip("/") != "/modern/medias":
            raise ValueError("Account discovery requires the documented https://api.wistia.com/modern/medias source.")
        page = task.get("page")
        if type(page) is not int or page < 1:
            raise ValueError("Invalid Wistia page checkpoint.")
        token = context.credentials.get("wistia_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Wistia account discovery requires a server-side read token.")
        headers = {"Authorization": f"Bearer {token}", "X-Wistia-API-Version": "2026-09"}
        query = {"page": page, "per_page": size, "sort_by": "created", "sort_direction": 1}
        folder = source.options.get("folder_id")
        if folder is not None:
            if not isinstance(folder, str) or not folder.isalnum():
                raise ValueError("Wistia folder_id must be the provider hashed identifier.")
            query["folder_id"] = folder
        url = "https://api.wistia.com/modern/medias?" + urlencode(query)
    else:
        raise ValueError("The checkpoint task does not belong to this configured provider.")
    return url, method, body, headers, size


def _next(source, task, payload, size):
    kind = task["kind"]
    if kind == "civicplus-select":
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise ValueError("CivicClerk Events must return an OData value array.")
        link = payload.get("@odata.nextLink")
        if link is not None:
            if not isinstance(link, str) or not link:
                raise ValueError("CivicClerk returned an invalid next-page link.")
            base = _api_source(source)
            link = urljoin(base, link)
            validate_url(link)
            if _origin(link) != _origin(base) or urlsplit(link).path.casefold() != "/v1/events":
                raise ValueError("CivicClerk pagination left the configured tenant Events collection.")
            return {"kind": kind, "next": link}
    elif kind == "legistar":
        if not isinstance(payload, list):
            raise ValueError("Legistar Events must return a JSON array.")
        if len(payload) >= size:
            ids = [row.get("EventId") for row in payload if isinstance(row, dict)]
            if not ids or any(type(value) is not int for value in ids):
                raise ValueError("Legistar pagination requires provider-issued numeric EventId values.")
            after = max(ids)
            if after <= task.get("after", 0):
                raise ValueError("Legistar returned a non-advancing page.")
            return {"kind": kind, "after": after}
    elif kind == "wistia":
        if not isinstance(payload, list):
            raise ValueError("Wistia List Media must return a JSON array.")
        if len(payload) >= size:
            return {"kind": kind, "page": task["page"] + 1}
    return None


def _enrich(bundle, provider):
    if provider == "champ":
        from .champ_media import enrich_bundle
        bundle.update(enrich_bundle(bundle))
        return
    for record in bundle["records"]:
        raw = record.get("original")
        if not isinstance(raw, dict):
            continue
        normalized = record["normalized"]
        if provider == "civicplus-select":
            normalized["body"] = raw.get("categoryName")
            # CivicClerk may publish a direct HTTPS video in mediaStreamPath
            # while the unchanged compatibility reader only maps
            # externalMediaUrl. Keep this enrichment discovery-only: relative
            # storage paths are not expanded into guessed CDN URLs, and the
            # fetch path still requires an explicit download-origin grant.
            media_url = raw.get("mediaStreamPath")
            if isinstance(media_url, str):
                try:
                    media_parts = urlsplit(media_url)
                    validate_url(media_url)
                except ValueError:
                    media_parts = None
                if media_parts is not None and media_parts.scheme == "https" and media_parts.netloc:
                    recordings = normalized.setdefault("recordings", [])
                    if isinstance(recordings, list):
                        recording = next((item for item in recordings
                                          if isinstance(item, dict) and item.get("url") == media_url), None)
                        if recording is None:
                            recording = {"url": media_url}
                            recordings.append(recording)
                            relationships = list(record.get("relationships") or ())
                            relationships.append({"relation": "recording", "value": recording})
                            record["relationships"] = relationships
                        if media_parts.path.lower().endswith(".mp4"):
                            recording["video_url"] = media_url
                            for relationship in record.get("relationships") or ():
                                value = relationship.get("value")
                                if (relationship.get("relation") == "recording" and isinstance(value, dict)
                                        and value.get("url") == media_url):
                                    value["video_url"] = media_url
                        citations = list(record.get("citation_urls") or ())
                        record["citation_urls"] = list(dict.fromkeys([*citations, media_url]))
            # The provider's public payload writes local wall time with Z for
            # observed tenants. Preserve Z but never assert its UTC interpretation.
            normalized["time_zone_status"] = "source_literal_unverified"
            normalized["source_status"] = {key: raw[key] for key in (
                "isPublished", "isDeleted", "eventName") if key in raw}
        elif provider == "escribe":
            name = raw.get("MeetingType") or raw.get("MeetingName")
            if isinstance(name, str):
                normalized["body"] = re.sub(
                    r"\s+-\s+(?:regular|special|study|joint|work)?\s*(?:meeting|session|hearing)\s*$",
                    "", name, flags=re.I)
            # The public calendar explicitly labels Video/Audio links. Preserve
            # them as player citations, never infer direct media download bytes.
            for item in raw.get("MeetingDocumentLink") or []:
                if not isinstance(item, dict) or str(item.get("Type", "")).casefold() not in {"video", "audio"}:
                    continue
                value = item.get("Url")
                if not isinstance(value, str) or not value:
                    continue
                url = urljoin(bundle["source"]["url"], value)
                try:
                    validate_url(url)
                except ValueError:
                    continue
                recording = {"url": url, "title": item.get("Title"),
                    "media_type": item["Type"].casefold(), "availability": "supplied_player_link",
                    "source_fields": deepcopy(item)}
                recordings = normalized.setdefault("recordings", [])
                if any(existing.get("url") == url for existing in recordings):
                    continue
                recordings.append(recording)
                record["relationships"] = [*record.get("relationships", []),
                    {"relation": "recording", "value": deepcopy(recording)}]
            normalized["source_status"] = {key: raw[key] for key in (
                "HasAgenda", "HasVideo", "HasLiveVideo", "HasVideoLivePassed", "MeetingPassed") if key in raw}
        elif provider == "primegov":
            if raw.get("committeeName"):
                normalized["body"] = raw["committeeName"]
        record["normalized_sha256"] = canonical_hash(normalized)


def parse_page(engine, source, namespace, content, input_format, bounds, context):
    if len(content) > bounds.parser_bytes:
        raise ValueError("The provider listing exceeds the configured parser byte limit.")
    if input_format in {"legistar-events-json", "legistar-event-json", "wistia-api-media-json",
                        "wistia-media-detail-json", "wistia-caption-json", "granicus-listing-html",
                        "civicweb-detail-html", "swagit-listing-html", "onbase-public-listing-html",
                        "digital-towpath-listing-html", "towncloud-public-listing-json"}:
        return parse_native(source, namespace, content, input_format), ()
    result = engine.normalize(replace(source, body=None), content, input_format=input_format,
                              bounds=replace(bounds, date_from=None, date_to=None,
                                             max_records=2**31 - 1, checkpoint=None),
                              context=context)
    if result.status in {"failed", "unsupported"}:
        raise ValueError("The provider response could not be normalized using its configured format.")
    bundle = deepcopy(result.data)
    bundle["source"] = {**source.public_dict(), "namespace": namespace, "input_format": input_format}
    _enrich(bundle, source.provider)
    return bundle, result.errors


def record_day(record):
    normalized = record["normalized"]
    return (normalized.get("meeting_date") or
            (normalized.get("scheduled_start") or normalized.get("source_start") or "")[:10])


def discover(engine, request, content, context, *, transport=None, browser=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context, content)
    bounds = Bounds(**request.get("bounds", {}))
    input_format = source.input_format or DEFAULT_FORMAT[source.provider]
    if (source.provider == "digital-towpath" and source.input_format is None
            and re.fullmatch(r"/meetings/detail/[0-9]+/?", urlsplit(source.url).path) is None):
        input_format = "digital-towpath-listing-html"
    if source.provider == "towncloud" and source.input_format is None:
        parts = urlsplit(source.url)
        if (parts.path.rstrip("/") == "/agendas" or (parts.hostname == "towncloud.io" and
                re.fullmatch(r"/go/[A-Za-z0-9_-]+/published_agendas\.json", parts.path))):
            input_format = "towncloud-public-listing-json"
    saved = _decode_content(request, content)
    if saved is not None and len(saved) > bounds.parser_bytes:
        raise ValueError("The saved response exceeds the configured parser byte limit.")
    if source.provider == "simbli" and saved is None and urlsplit(source.url).path.lower() in {
            "/index.aspx", "/sb_meetings/sb_meetinglisting.aspx"}:
        from .simbli import discover_public
        return discover_public(engine, source, namespace, bounds, context, transport or PublicTransport(),
                               record_types=request.get("record_types"))
    if source.provider == "boardable" and saved is None:
        path = urlsplit(source.url).path.strip("/").split("/")
        if len(path) == 1 or (len(path) == 2 and path[1] == "meetings"):
            from .boardable import discover_public
            return discover_public(engine, source, namespace, bounds, context, transport or PublicTransport(),
                                   record_types=request.get("record_types"))
    if source.provider == "novusagenda" and (source.input_format == "novus-public-listing-html" or
                                            (saved is None and source.input_format is None)):
        from .novus import discover_public
        return discover_public(engine, source, namespace, bounds, context, transport or PublicTransport(),
                               saved=saved, record_types=request.get("record_types"))
    if source.provider == "laserfiche-weblink" and urlsplit(source.url).hostname == "api.laserfiche.com":
        from .repository import discover_children
        return discover_children(source, namespace, bounds, context, transport or PublicTransport(),
                                 saved=saved, record_types=request.get("record_types"))
    if source.provider == "laserfiche-weblink" and saved is None and browser is not None:
        from .laserfiche import discover_folders
        return discover_folders(engine, source, namespace, bounds, context, browser,
                                record_types=request.get("record_types"))
    types = request.get("record_types") or []
    if not isinstance(types, list) or any(value not in {"meeting", "recording", "document", "agenda_item", "transcript"}
                                          for value in types):
        raise ValueError("record_types must be a list of supported civic record types.")
    binding = canonical_hash([_binding(source, bounds, context, input_format), types])
    queue, seen = (_resume(bounds.checkpoint, binding) if bounds.checkpoint else
                   (_initial(source, bounds, input_format, saved is not None), set()))
    if not queue:
        return OperationResult("unsupported", errors=(Error(
            "saved_capture_required",
            "Automatic retrieval is not verified for this configured format. Supply its saved response; "
            "this does not establish that the provider lacks discovery.",
            source=source.url),), coverage={"sources": [source.public_dict()],
            "scope": "saved-capture fallback required"}, operation_id=context.operation_id)
    if any(task.get("kind") == "saved" for task in queue) and saved is None:
        raise ValueError("Resuming a saved capture requires the same content bytes.")
    deadline = monotonic() + bounds.deadline_seconds
    transport = transport or PublicTransport()
    records, bundles, captures, failures, errors, retry = [], [], [], [], [], []
    pages = filtered = 0
    unknown_dates, unknown_bodies, visited = [], [], set()
    public_controls = None
    while queue and pages < bounds.max_pages and len(records) < bounds.max_records:
        if context.check_cancelled() or monotonic() >= deadline:
            break
        task = queue.pop(0)
        task_key = canonical_hash(task)
        if task_key in visited:
            errors.append(Error("pagination_cycle", "The provider repeated a pagination checkpoint.", source=source.url))
            failures.append({"page": pages + 1, "reason": "pagination_cycle"})
            retry.append(task)
            break
        visited.add(task_key)
        pages += 1
        try:
            if task.get("kind") == "saved":
                page_content = saved
                following = None
            else:
                if task.get("kind") in {"suiteone-group", "agendacenter-year", "towpath-year"}:
                    if source.provider == "suiteone-media" and task["kind"] == "suiteone-group":
                        from .suiteone import controls
                    elif source.provider == "civicplus-agenda-center" and task["kind"] == "agendacenter-year":
                        from .agendacenter import controls
                    elif source.provider == "digital-towpath" and task["kind"] == "towpath-year":
                        from .towpath import controls
                    else:
                        raise ValueError("The public control does not belong to this provider.")
                    # Continuations contain public control values, never trust a
                    # caller-modified group absent from the current root page.
                    if public_controls is None:
                        root = transport.request(source.url, byte_limit=bounds.parser_bytes,
                            deadline_seconds=max(.001, deadline - monotonic()),
                            allowed_origins=(_origin(source.url),), allow_redirects=False)
                        if (root.status != 200 or root.url != source.url
                                or len(root.content) > bounds.parser_bytes):
                            raise ValueError("The public control page is unavailable.")
                        public_controls = controls(root.content)
                    if task.get("fields") not in public_controls:
                        raise ValueError("The requested value is not a current public root control.")
                    if context.check_cancelled() or monotonic() >= deadline:
                        raise RetrievalError("provider_deadline_or_cancellation")
                url, method, body, headers, size = _request_spec(source, bounds, task, context)
                origin = _origin(url)
                response = transport.request(
                    url, method=method, body=body, headers=headers or None,
                    byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                    allowed_origins=(origin,),
                    **({"allow_redirects": False} if task.get("kind") in {
                        "suiteone-group", "agendacenter-year", "towpath-year"} else {}),
                )
                if _origin(response.url) != origin:
                    raise ValueError("Provider retrieval left its configured origin.")
                if response.status != 200:
                    raise RetrievalError("provider_http_error", status=response.status)
                page_content = response.content
                if len(page_content) > bounds.parser_bytes:
                    raise ValueError("The provider listing exceeds its parser byte limit.")
                try:
                    payload = json.loads(page_content)
                except (ValueError, UnicodeError):
                    payload = None
                following = None
            digest = hashlib.sha256(page_content).hexdigest()
            if task.get("sha256") is not None and task["sha256"] != digest:
                raise ValueError("The resumed page changed; restart discovery to review its new revision.")
            bundle, parse_errors = parse_page(
                engine, source, namespace, page_content, input_format, bounds, context)
            errors.extend(parse_errors)
            rows = bundle["records"]
            offset = task.get("offset", 0)
            if type(offset) is not int or not 0 <= offset <= len(rows):
                raise ValueError("The checkpoint record offset is outside the captured page.")
            selected = []
            for index in range(offset, len(rows)):
                if (context.check_cancelled() or monotonic() >= deadline or
                        len(records) >= bounds.max_records):
                    queue.insert(0, {**task, "offset": index, "sha256": digest})
                    break
                record = rows[index]
                key = source_identity_key(record["identity"])
                if key in seen:
                    continue
                normalized = record["normalized"]
                day = record_day(record)
                if day and ((bounds.date_from and day < bounds.date_from) or
                            (bounds.date_to and day > bounds.date_to)):
                    filtered += 1
                    continue
                if types and record["identity"]["record_type"] not in types:
                    filtered += 1
                    continue
                body = normalized.get("body")
                if source.body and body and body.casefold() != source.body.casefold():
                    filtered += 1
                    continue
                if not day and (bounds.date_from or bounds.date_to):
                    unknown_dates.append(record["identity"]["external_id"])
                if source.body and not body:
                    unknown_bodies.append(record["identity"]["external_id"])
                seen.add(key)
                selected.append(record)
                records.append(record)
            else:
                if following:
                    queue.insert(0, following)
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            if task.get("kind") != "saved" and not any(
                    queued.get("sha256") == digest for queued in queue):
                following = _next(source, task, payload, size)
                if following:
                    queue.insert(0, following)
                if (source.provider == "suiteone-media" and task.get("kind") == "static"
                        and urlsplit(source.url).path in {"", "/"}):
                    from .suiteone import controls
                    public_controls = controls(page_content)
                    queue.extend({"kind": "suiteone-group", "fields": values}
                                 for values in public_controls)
                elif (source.provider == "civicplus-agenda-center" and task.get("kind") == "static"
                        and urlsplit(source.url).path.lower().rstrip("/") == "/agendacenter"):
                    from .agendacenter import controls
                    public_controls = controls(page_content)
                    queue.extend({"kind": "agendacenter-year", "fields": values}
                                 for values in public_controls
                                 if (not bounds.date_from or values["year"] >= bounds.date_from[:4])
                                 and (not bounds.date_to or values["year"] <= bounds.date_to[:4]))
                elif (source.provider == "digital-towpath" and task.get("kind") == "static"
                        and input_format == "digital-towpath-listing-html"):
                    from .towpath import controls
                    public_controls = controls(page_content)
                    queue.extend({"kind": "towpath-year", "fields": values}
                                 for values in public_controls
                                 if (not bounds.date_from or values["year"] >= bounds.date_from[:4])
                                 and (not bounds.date_to or values["year"] <= bounds.date_to[:4]))
        except Exception as error:
            # Provider/network exceptions may contain request URLs or credentials.
            # Never expose arbitrary exception text through public errors.
            code = error.code if isinstance(error, RetrievalError) else "provider_page_failed"
            details = ({"http_status": error.status} if isinstance(error, RetrievalError) and
                       error.status is not None else {})
            failures.append({"page": pages, "kind": task.get("kind"), "reason": code, **details})
            errors.append(Error(code, "A provider page could not be retrieved or parsed. "
                                "Check access, configured format, bounds, or use a saved response.",
                                retryable=True, source=source.url, details=details))
            retry.append(task)
        context.report(operation="discover", pages=pages, returned_records=len(records))
    queue.extend(retry)
    cancelled = context.check_cancelled()
    timed_out = monotonic() >= deadline
    partial = bool(queue or failures or unknown_dates or unknown_bodies or saved is not None or
                   source.provider not in NATIVE)
    status = "cancelled" if cancelled else (
        "failed" if failures and not captures else "partial" if partial else "completed")
    checkpoint = _checkpoint(binding, queue, seen) if queue else None
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace, "input_format": input_format}],
        "date_from": bounds.date_from, "date_to": bounds.date_to, "date_inclusivity": "both",
        "record_types": types, "body": source.body, "actual_dates": sorted({
            record_day(row) for row in records if record_day(row)}),
        "returned_records": len(records), "filtered_records": filtered, "pages": pages,
        "failed_pages": failures, "failures": failures, "unknown_date_records": unknown_dates,
        "unknown_body_records": unknown_bodies, "truncated": bool(queue), "deadline_exceeded": timed_out,
        "checkpoint": checkpoint, "unavailable_attachments": [],
        "scope": "one saved capture, not a complete upstream catalog" if saved is not None else (
            "bounded provider listing" if source.provider in NATIVE else
            "configured capture only; upstream catalog completeness is unverified"),
        "available_text": "metadata_and_supplied_text_only",
    }
    if source.provider == "suiteone-media" and saved is None:
        coverage.update({"catalog_complete": False, "source_complete": False,
            "scope": "configured public root and its supplied Older Meetings groups; catalog extent unverified",
            "older_groups": len(public_controls or []),
            "control_validation": "current public root revalidated before resumed group POST"})
    elif source.provider == "civicplus-agenda-center" and saved is None:
        coverage.update({"catalog_complete": False, "source_complete": False,
            "scope": "configured Agenda Center root and its supplied year/category controls; archive extent unverified",
            "year_category_controls": len(public_controls or []),
            "control_validation": "current public root revalidated before resumed year POST"})
    elif source.provider == "digital-towpath" and input_format == "digital-towpath-listing-html":
        coverage.update({"catalog_complete": False, "source_complete": False,
            "scope": "supplied dated meeting links and public Other Years links; detail documents not fetched",
            "control_validation": "current configured listing revalidated before resumed year GET"})
    return OperationResult(status, {"source": source.public_dict(), "records": records,
                                   "captures": captures, "bundles": bundles},
                           tuple(errors), coverage, context.operation_id)
