"""Cablecast (Tightrope "Reflect") public meeting video: shows, video links and caption tracks.

A city's public Cablecast site is ``https://{host}`` with a JSON API under ``/cablecastapi/v1``. This
provider reads, with plain public GETs:

* ``/cablecastapi/v1/shows`` - the shows (one per airing; a meeting can appear more than once)
* ``/cablecastapi/v1/shows/{id}`` and ``/cablecastapi/v1/vods/{id}`` - one show and its video file
* the video's HLS ``vod.m3u8`` and its ``SUBTITLES`` playlist (about 10 s WebVTT segments)

The watch page is ``/internetchannel/show/{id}``. Recordings and caption tracks are returned as
records and links only: no video or audio is downloaded or cut, no caption segment text is read and
nothing is transcribed. QuorumRelay does not handle audio.

Cablecast is not one of the fixed 31 baseline provider families, so it is registered as a built-in
typed connector (see ``extensions.Connector``) rather than a baseline roster row.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import date
from time import monotonic
from urllib.parse import urljoin, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import PublicTransport, RetrievalError
from .discovery import _checkpoint, _resume
from .identification import validate_url
from .native import make_bundle

PROVIDER = "cablecast"
SHOWS_FORMAT = "cablecast-shows-json"
SHOW_FORMAT = "cablecast-show-json"
PAGE_SIZE = 200
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9-]+)*\.cablecast\.tv")
_ID = re.compile(r"[1-9][0-9]{0,18}")
_SUBTITLES = re.compile(r"^#EXT-X-MEDIA:.*TYPE=SUBTITLES.*$", re.M)
_MONTHS = {name: number for number, names in enumerate(
    ("jan january", "feb february", "mar march", "apr april", "may", "jun june", "jul july",
     "aug august", "sep sept september", "oct october", "nov november", "dec december"), 1)
    for name in names.split()}
_NAMED_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
_NUMERIC_DAY = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)")
_ISO_DAY = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")


def _squash(value):
    return " ".join(str(value or "").split())


def host_of(url):
    validate_url(url)
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not _HOST.fullmatch(host):
        raise ValueError("Cablecast sources use an HTTPS https://{host}.cablecast.tv URL.")
    return host


def namespace_of(source):
    return "//" + host_of(source.url)


def watch_url(host, show_id):
    return f"https://{host}/internetchannel/show/{show_id}"


def title_day(title):
    """A calendar day the title names ("November 4, 2026", "Nov 10 2026", "11-10-2026"), else None."""
    def day(year, month, number):
        try:
            return date(year, month, number)
        except ValueError:
            return None
    for match in _NAMED_DAY.finditer(title):
        month = _MONTHS.get(match[1].casefold())
        if month and (found := day(int(match[3]), month, int(match[2]))):
            return found
    if match := _NUMERIC_DAY.search(title):
        if found := day(int(match[3]), int(match[1]), int(match[2])):
            return found
    if match := _ISO_DAY.search(title):
        return day(int(match[1]), int(match[2]), int(match[3]))
    return None


def show_row(source, raw):
    """One show row, or None when it has no video, title or readable day. Shows without a vod are
    listings of live or scheduled airings and carry no recording to link."""
    host = host_of(source.url)
    vods = raw.get("vods")
    title = _squash(raw.get("title"))
    if type(raw.get("id")) is not int or raw["id"] <= 0 or not title or not isinstance(vods, list) or not vods:
        return None
    if any(type(vod) is not int or vod <= 0 for vod in vods):
        return None
    event = str(raw.get("eventDate") or "")[:10]
    try:
        event_day = date.fromisoformat(event)
    except ValueError:
        event_day = None
    # The first ten characters of eventDate are the city's own day. A title that names one day wins:
    # a show is sometimes dated the day after its meeting.
    named = title_day(title)
    day = named or event_day
    if day is None:
        return None
    show_id = str(raw["id"])
    link = watch_url(host, show_id)
    normalized = {
        "external_id": show_id, "title": title, "meeting_date": day.isoformat(),
        "date_source": "title" if named else "event_date", "event_date": raw.get("eventDate"),
        "time_zone_status": "unknown", "url": link, "body": None,
        "vod_ids": [str(vod) for vod in vods],
        "documents": [], "agenda_items": [], "documents_availability": "not_supplied_by_show_listing",
        "agenda_items_availability": "not_supplied_by_show_listing",
        "recordings": [{"external_id": str(vod), "kind": "video_on_demand", "media_type": "video",
                        "url": link, "availability": "supplied_player_link"} for vod in vods],
        "captions_availability": "not_probed_by_listing",
        "source_status": {"has_captions_flag": raw.get("hasCaptions"),
                          "has_captions_flag_note": "Reported by the site; not used, copies of one meeting disagree."},
    }
    return normalized, deepcopy(raw), "meeting"


def shows_bundle(source, namespace, content, rows=None):
    payload = _json_object(content, "shows")
    shows = payload.get("shows")
    if not isinstance(shows, list):
        raise ValueError("The Cablecast shows response must contain a shows array.")
    if rows is None:
        rows = [row for item in shows if isinstance(item, dict) and (row := show_row(source, item))]
    return make_bundle(source, namespace, content, SHOWS_FORMAT, rows)


def _json_object(content, label):
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError):
        raise ValueError(f"The Cablecast {label} response was not valid JSON.") from None
    if not isinstance(payload, dict):
        raise ValueError(f"The Cablecast {label} response must be a JSON object.")
    return payload


def subtitles_track(master):
    """The caption playlist a ``vod.m3u8`` names (its ``SUBTITLES`` entry) as {uri, language, name}."""
    line = _SUBTITLES.search(master)
    if not line:
        return None
    attributes = line.group(0)
    uri = re.search(r'URI="([^"]+)"', attributes)
    if not uri:
        return None
    language, name = re.search(r'LANGUAGE="([^"]*)"', attributes), re.search(r'NAME="([^"]*)"', attributes)
    return {"uri": uri[1], "language": language[1] if language else None, "name": name[1] if name else None}


def _segments(playlist):
    return [line.strip() for line in playlist.splitlines() if line.strip() and not line.startswith("#")]


class _Reader:
    """Bounded same-origin GETs that count against max_pages and the deadline, and hash each read."""

    def __init__(self, transport, host, bounds, context):
        self.transport, self.host, self.bounds, self.context = transport, host, bounds, context
        self.origin = f"https://{host}"
        self.deadline = monotonic() + bounds.deadline_seconds
        self.pages = 0
        self.reads = []

    def has_budget(self, extra=1):
        return (self.pages + extra <= self.bounds.max_pages and monotonic() < self.deadline
                and not self.context.check_cancelled())

    def get(self, url):
        if urlsplit(url).scheme != "https" or urlsplit(url).hostname != self.host:
            raise RetrievalError("provider_response_outside_contract")
        self.pages += 1
        response = self.transport.request(url, byte_limit=self.bounds.parser_bytes,
                                          deadline_seconds=max(.001, self.deadline - monotonic()),
                                          allowed_origins=(self.origin,), allow_redirects=False)
        if monotonic() >= self.deadline:
            raise RetrievalError("provider_deadline_exceeded")
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if response.url != url or len(response.content) > self.bounds.parser_bytes:
            raise RetrievalError("provider_response_outside_contract", status=response.status)
        self.reads.append({"url": url, "sha256": hashlib.sha256(response.content).hexdigest(),
                           "byte_length": len(response.content)})
        return response

    def api(self, path):
        return self.get(f"{self.origin}/cablecastapi/v1/{path}")

    def vod(self, vod_id):
        """The vod object and the folder its HLS files live in (same host as the site)."""
        payload = _json_object(self.api(f"vods/{vod_id}").content, "vod").get("vod")
        url = payload.get("url") if isinstance(payload, dict) else None
        if not isinstance(url, str) or urlsplit(url).scheme != "https" or urlsplit(url).hostname != self.host:
            raise RetrievalError("vod_url_outside_contract")
        return payload, url.rsplit("/", 1)[0] + "/"

    def master(self, base):
        return self.get(base + "vod.m3u8").content.decode("utf-8", errors="replace")


def _caption_track(base, master, reader, *, read_playlist):
    track = subtitles_track(master)
    if track is None:
        return None
    playlist_url = urljoin(base, track["uri"])
    if urlsplit(playlist_url).scheme != "https" or urlsplit(playlist_url).hostname != reader.host:
        raise RetrievalError("caption_url_outside_contract")
    value = {"language": track["language"], "name": track["name"], "playlist_url": playlist_url,
             "format": "hls_subtitles_webvtt_segments", "text_availability": "not_read_playlist_link_only"}
    if read_playlist:
        segments = _segments(reader.get(playlist_url).content.decode("utf-8", errors="replace"))
        value["segment_count"] = len(segments)
    return value


def _enrich(normalized, vod, base, track):
    """Fill the recording link and caption track from a read vod; the listing row stays literal."""
    normalized["recordings"] = [{
        "external_id": str(vod["id"]) if type(vod.get("id")) is int else None, "kind": "video_on_demand",
        "media_type": "video", "url": vod["url"], "hls_playlist_url": base + "vod.m3u8",
        "watch_url": normalized["url"], "length_seconds": vod.get("length"),
        "vod_state": vod.get("vodState"), "is_watchable": vod.get("isWatchable"),
        "availability": "supplied_url"}]
    normalized["captions"] = [track] if track else []
    normalized["captions_availability"] = "caption_playlist_named" if track else "no_caption_playlist"


def _show_status(error):
    code = error.code if isinstance(error, RetrievalError) else "provider_page_failed"
    return code, ({"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {})


def discover_public(source, namespace, bounds, context, transport, *, record_types=None):
    host = host_of(source.url)
    if not context.allows("discover", namespace):
        return OperationResult("failed", errors=(Error(
            "permission_denied", "The source namespace is outside the caller's discovery grant."),))
    record_types = [] if record_types is None else record_types
    if not isinstance(record_types, list) or any(not isinstance(v, str) for v in record_types):
        raise ValueError("record_types must be a list of supported civic record types.")
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "body": source.body,
                              "dates": [bounds.date_from, bounds.date_to], "record_types": record_types,
                              "scope": context.scope, "semantics": "cablecast-shows/v1"})
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
    else:
        queue, seen = [{"page": 0}], set()
    reader = _Reader(transport, host, bounds, context)
    records, bundles, captures, errors, failures = [], [], [], [], []
    groups, filtered, collapsed, probes, unprobed = set(), 0, 0, 0, 0
    no_vod = unreadable = 0
    total_shows, read_ids = None, set()
    while queue and reader.has_budget() and len(records) < bounds.max_records:
        task = queue.pop(0)
        page, offset, expected = task.get("page"), task.get("offset", 0), task.get("sha256")
        if (type(page) is not int or not 0 <= page <= 10000 or type(offset) is not int or offset < 0
                or set(task) - {"page", "offset", "sha256"}):
            raise ValueError("The Cablecast continuation position is invalid.")
        suffix = f"&offset={page}" if page else ""
        try:
            response = reader.api(f"shows?page_size={PAGE_SIZE}&pageSize={PAGE_SIZE}{suffix}")
            digest = hashlib.sha256(response.content).hexdigest()
            if expected and expected != digest:
                raise ValueError("The resumed Cablecast page changed; restart discovery without its checkpoint.")
            payload = _json_object(response.content, "shows")
            meta, shows = payload.get("meta"), payload.get("shows")
            if (not isinstance(meta, dict) or type(meta.get("count")) is not int or not isinstance(shows, list)
                    or type(meta.get("pageSize")) is not int or meta["pageSize"] < 1
                    or (page and meta.get("offset") != page)):
                raise ValueError("The Cablecast shows response omitted its paging metadata.")
            total_shows = meta["count"]
            in_range = []
            page_ids = {item.get("id") for item in shows if isinstance(item, dict)}
            if page_ids & read_ids:
                raise RetrievalError("pagination_cycle")
            read_ids |= page_ids
            for item in shows:
                row = show_row(source, item) if isinstance(item, dict) else None
                if row is None:
                    if isinstance(item, dict) and not item.get("vods"):
                        no_vod += 1
                    else:
                        unreadable += 1
                    continue
                day = row[0]["meeting_date"]
                if (bounds.date_from and day < bounds.date_from) or (bounds.date_to and day > bounds.date_to):
                    filtered += 1
                    continue
                in_range.append(row)
            if offset > len(in_range):
                raise ValueError("The Cablecast continuation offset exceeds this page.")
            # Copies of one meeting (same title and day) are one record; prefer the copy with captions.
            ordered = {}
            for row in in_range:
                ordered.setdefault((row[0]["title"].casefold(), row[0]["meeting_date"]), []).append(row)
            chosen_rows, interrupted = [], False
            for index, (key, copies) in enumerate(list(ordered.items())[offset:], offset):
                if len(records) + len(chosen_rows) >= bounds.max_records or context.check_cancelled():
                    queue.insert(0, {"page": page, "offset": index, "sha256": digest})
                    interrupted = True
                    break
                if key in groups:
                    collapsed += len(copies)
                    continue
                pick, selection, probed = copies[0], "only_copy", None
                if len(copies) > 1:
                    selection, attempted = "first_listed_unprobed", False
                    for copy in copies:
                        if not reader.has_budget(2):
                            break
                        try:
                            vod, base = reader.vod(copy[0]["vod_ids"][0])
                            track = _caption_track(base, reader.master(base), reader, read_playlist=False)
                            probes += 1
                        except Exception as error:
                            failures.append({"page": reader.pages, "kind": "caption_probe",
                                             "show": copy[0]["external_id"], "reason": _show_status(error)[0]})
                            continue
                        attempted = True
                        if track is not None:
                            pick, selection, probed = copy, "copy_with_caption_playlist", (vod, base, track)
                            break
                    if attempted and selection == "first_listed_unprobed":
                        selection = "first_listed_no_caption_playlist_found"
                    unprobed += selection == "first_listed_unprobed"
                    if probed:
                        _enrich(pick[0], *probed)
                pick[0]["duplicate_show_ids"] = [row[0]["external_id"] for row in copies if row is not pick]
                pick[0]["copy_selection"] = selection
                collapsed += len(copies) - 1
                chosen_rows.append(pick)
                groups.add(key)
            bundle = shows_bundle(source, namespace, response.content, rows=chosen_rows)
            bundle["capture"]["retrieval_url"] = response.url
            fresh = [r for r in bundle["records"] if source_identity_key(r["identity"]) not in seen]
            if len(fresh) != len(bundle["records"]):
                raise RetrievalError("pagination_cycle")
            seen.update(source_identity_key(r["identity"]) for r in fresh)
            bundle["records"] = fresh
            records.extend(fresh)
            bundles.append(bundle)
            captures.append(bundle["capture"])
            if shows and (page + 1) * meta["pageSize"] < total_shows:
                queue.insert(1 if interrupted else 0, {"page": page + 1})
            context.report(operation="discover", pages=reader.pages, returned_records=len(records))
        except Exception as error:
            code, details = _show_status(error)
            errors.append(Error(code, "A Cablecast public page could not be retrieved or parsed.",
                                retryable=True, source=source.url, details=details))
            failures.append({"page": reader.pages, "kind": "shows", "reason": code, **details})
            queue.insert(0, task)
            break
    checkpoint = _checkpoint(binding, queue, seen) if queue else None
    cancelled = context.check_cancelled()
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace, "input_format": SHOWS_FORMAT}],
        "date_from": bounds.date_from, "date_to": bounds.date_to, "date_inclusivity": "both",
        "record_types": record_types, "body": source.body, "returned_records": len(records),
        "filtered_records": filtered, "pages": reader.pages, "failed_pages": failures, "failures": failures,
        "actual_dates": sorted({r["normalized"]["meeting_date"] for r in records}),
        "unknown_date_records": [],
        "unknown_body_records": [r["identity"]["external_id"] for r in records] if source.body else [],
        "body_filter_status": ("unknown_cablecast_shows_have_no_body_field" if source.body else "not_requested"),
        "shows_reported_by_site": total_shows, "shows_without_video_omitted": no_vod,
        "unreadable_shows_omitted": unreadable,
        "duplicate_copies_collapsed": collapsed, "caption_probes": probes,
        "duplicate_groups_unprobed": unprobed,
        "duplicate_scope": "copies seen in the pages read by this call; a copy on another page or call is not merged",
        "paging": "page_size and an offset page index, observed on one Cablecast site; not vendor-documented",
        "catalog_complete": False, "source_complete": False, "truncated": bool(queue),
        "deadline_exceeded": monotonic() >= reader.deadline, "checkpoint": checkpoint,
        "available_text": "titles_dates_and_links_only; caption text not read",
        "scope": ("bounded public show listing; recordings and caption tracks are links only, "
                  "nothing downloaded or transcribed; the site's full archive is not claimed"),
    }
    status = "cancelled" if cancelled else "failed" if failures and not captures else "partial"
    data = {"source": source.public_dict(), "records": records, "captures": captures, "bundles": bundles}
    return OperationResult(status, data, tuple(errors), coverage, context.operation_id)


def fetch_record(source, namespace, external_id, bounds, context, transport):
    """One show with its video link and caption playlist, read from the show, vod, vod.m3u8 and playlist."""
    host = host_of(source.url)
    if not isinstance(external_id, str) or not _ID.fullmatch(external_id):
        raise ValueError("Cablecast detail requires a positive decimal show ID string.")
    if bounds.checkpoint:
        raise ValueError("One Cablecast show does not accept catalog continuation.")
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "external_id": external_id,
                "scope": "one show, its video link and caption playlist link; no media or caption text read",
                "catalog_complete": False, "source_complete": False, "failures": []}
    if context.check_cancelled():
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    reader = _Reader(transport, host, bounds, context)
    try:
        response = reader.api(f"shows/{external_id}")
        raw = _json_object(response.content, "show").get("show")
        row = show_row(source, raw) if isinstance(raw, dict) else None
        if row is None or row[0]["external_id"] != external_id:
            raise ValueError("The show is missing, has no video, or does not match the requested ID.")
        status = "partial"
        normalized = row[0]
        if reader.has_budget(3):
            vod, base = reader.vod(normalized["vod_ids"][0])
            track = _caption_track(base, reader.master(base), reader, read_playlist=True)
            _enrich(normalized, vod, base, track)
        else:
            coverage["failures"].append("page_budget_before_vod_and_captions")
        bundle = make_bundle(source, namespace, response.content, SHOW_FORMAT, [row])
        bundle["capture"]["retrieval_url"] = response.url
    except (ValueError, OSError) as error:
        code, _ = _show_status(error)
        return OperationResult("failed", errors=(Error(
            "cablecast_show_unavailable", "The requested show could not be retrieved or validated.",
            source=f"https://{host}/cablecastapi/v1/shows/{external_id}",
            details={"reason": code if isinstance(error, RetrievalError) else "invalid_show"}),),
            coverage={**coverage, "pages": reader.pages}, operation_id=context.operation_id)
    return OperationResult(status, bundle, coverage={**coverage, "pages": reader.pages,
                                                     "reads": reader.reads}, operation_id=context.operation_id)


class CablecastConnector:
    """Built-in typed connector; it makes only public GETs and never writes."""

    provider = PROVIDER

    def __init__(self, transport=None):
        self.transport = transport

    def _transport(self):
        return self.transport or PublicTransport()

    def capabilities(self):
        reads = {"capability_status": "observed", "implementation_status": "implemented",
                 "acceptance_status": "fixture_passed"}
        none = {"capability_status": "unverified", "implementation_status": "not_implemented",
                "acceptance_status": "not_run"}
        return {
            "canonical_id": PROVIDER, "id": PROVIDER, "name": "Cablecast (Tightrope Reflect) meeting video",
            "aliases": [], "baseline_formats": [], "roster": "additive_typed_connector_outside_the_31_baseline_families",
            "operations": {
                "identify": {**reads, "details": "*.cablecast.tv host shape; no network request."},
                "discover": {**reads, "details": "Bounded public shows listing with date filter; recordings are "
                             "watch-page links; copies of one meeting collapse to the copy with a caption playlist."},
                "fetch": {**reads, "details": "One show by ID: video file, HLS and caption playlist links."},
                "parse": {**reads, "details": "Saved shows list JSON (cablecast-shows-json)."},
                "native_search": none, "local_search": {**reads, "details": "Shared local search over captured records."},
                "neutral_export": {**reads, "details": "Shared neutral export of captured records."},
                "vendor_file_export": none, "create": none, "update": none},
            "evidence_note": ("Saved public captures of reflect-cityofloveland-co.cablecast.tv; a bounded live "
                              "read is recorded in docs/ENGINE-COVERAGE.md only where it was run."),
            "restrictions": ["Public reads only; no media download, caption text read, transcription or write."],
        }

    def identify(self, url):
        try:
            host = host_of(url)
        except ValueError as error:
            return OperationResult("failed", errors=(Error("unrecognized_source", str(error)),))
        return OperationResult("completed", {"url": url, "provider": PROVIDER, "identified": True,
                                             "namespace": "//" + host,
                                             "evidence": "URL shape, not site API acceptance"})

    def _namespace(self, source):
        namespace = namespace_of(source)
        if source.namespace is not None and source.namespace != namespace:
            raise ValueError("The configured namespace does not match the Cablecast host.")
        return namespace

    def discover(self, source, bounds, context):
        namespace = self._namespace(source)
        return discover_public(source, namespace, bounds, context, self._transport(),
                               record_types=None)

    def fetch(self, source, request, bounds, context):
        namespace = self._namespace(source)
        if request.get("attachment") is not None:
            return OperationResult.unsupported("fetch_attachment", reason=(
                "Cablecast video and caption files are links only; QuorumRelay downloads no media."))
        if "caption_language" in request:
            return OperationResult.unsupported("fetch_captions", reason=(
                "Caption segment text is not read; the show record names the caption playlist link."))
        if "parent_id" in request or "record_type" in request:
            return OperationResult.unsupported("fetch_related", reason=(
                "No related-record mapping is registered for Cablecast."))
        if "external_id" in request:
            return fetch_record(source, namespace, request["external_id"], bounds, context, self._transport())
        return discover_public(source, namespace, bounds, context, self._transport(),
                               record_types=request.get("record_types"))

    def parse(self, source, content, input_format, bounds, context):
        namespace = self._namespace(source)
        if input_format not in {SHOWS_FORMAT, SHOW_FORMAT}:
            return OperationResult.unsupported("parse", reason="Unknown Cablecast input format.")
        if input_format == SHOW_FORMAT:
            raw = _json_object(content, "show").get("show")
            row = show_row(source, raw) if isinstance(raw, dict) else None
            if row is None:
                raise ValueError("The saved Cablecast show has no video, title or readable day.")
            bundle = make_bundle(source, namespace, content, SHOW_FORMAT, [row])
        else:
            bundle = shows_bundle(source, namespace, content)
        return OperationResult("completed", bundle, coverage={
            "sources": [{**source.public_dict(), "namespace": namespace, "input_format": input_format}],
            "scope": "saved capture; shows without a video are left out; copies of one meeting are not merged",
            "catalog_complete": False, "source_complete": False,
            "checkpoint": None, "failures": []}, operation_id=context.operation_id)

    def native_search(self, source, query, bounds, context):
        return OperationResult.unsupported("native_search", reason=(
            "No verified Cablecast native search; use local search over captured records."))

    def export(self, source, request, context):
        return OperationResult.unsupported("provider_export")

    def plan_write(self, source, request, context):
        return OperationResult.unsupported("plan_write", reason="Cablecast writes are not implemented.")

    def commit_write(self, source, request, context):
        return OperationResult.unsupported("commit_write", reason="Cablecast writes are not implemented.")
