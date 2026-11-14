"""Third-party-observed BoardDocs public listing and printable agenda reader.

The request mapping is from the pinned LlamaIndex reader source and example,
not a BoardDocs vendor contract. Responses are guarded and remain partial.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from ..engine import canonical_hash
from .native import make_bundle

LISTING_FORMAT = "boarddocs-public-meetings-json"
DETAIL_FORMAT = "boarddocs-print-agenda-html"
_COMMITTEE = re.compile(r"[A-Za-z0-9_-]{1,80}")
_MEETING_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_RECORD_TYPES = {"meeting", "recording", "document", "agenda_item", "transcript"}


def _configured_source(source):
    parts = urlsplit(source.url)
    match = re.fullmatch(r"/([A-Za-z0-9_-]{1,80}(?:/[A-Za-z0-9_-]{1,80}){0,2})/Board\.nsf/Public", parts.path)
    committee = source.options.get("boarddocs_committee_id")
    if (source.provider != "boarddocs" or parts.scheme != "https" or
            parts.hostname != "go.boarddocs.com" or parts.port not in {None, 443} or
            parts.username is not None or parts.password is not None or parts.query or parts.fragment or
            match is None):
        raise ValueError("BoardDocs discovery requires the exact HTTPS /{site}/Board.nsf/Public source.")
    if (set(source.options) - {"boarddocs_committee_id", "download_origins"} or not isinstance(committee, str) or
            not _COMMITTEE.fullmatch(committee)):
        raise ValueError("Configure only an explicit safe boarddocs_committee_id for this public source.")
    return parts, match[1], committee


def _meeting_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def parse_listing(source, content: bytes, *, parser_bytes: int | None = None) -> list[dict]:
    """Parse the reader-observed JSON array into its supplied ID/date/unid rows."""
    _configured_source(source)
    if not isinstance(content, bytes) or (parser_bytes is not None and len(content) > parser_bytes):
        raise ValueError("The BoardDocs listing exceeds its configured parser byte limit.")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        raise ValueError("The BoardDocs public meeting list was not valid JSON.") from None
    if not isinstance(payload, list):
        raise ValueError("The BoardDocs public meeting list must be a JSON array.")
    rows, seen = [], set()
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("A BoardDocs meeting list row was not an object.")
        # The pinned saved public listing ends with an empty object. It has no
        # record identity; retain it in the capture instead of fabricating one.
        if not raw:
            continue
        value = raw.get("unique")
        if type(value) is int and value > 0:
            identifier = str(value)
        elif isinstance(value, str) and _MEETING_ID.fullmatch(value):
            identifier = value
        else:
            raise ValueError("A BoardDocs meeting row omitted its provider-issued unique ID.")
        if identifier in seen:
            raise ValueError("The BoardDocs public meeting list repeated a meeting ID.")
        seen.add(identifier)
        rows.append({"meeting_id": identifier, "numberdate": raw.get("numberdate"),
                     "unid": raw.get("unid"), "original": raw})
    return rows


class _PrintAgenda(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []
        self.title = []
        self.meeting_date = []
        self.files = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        classes = set((fields.get("class") or "").split())
        roles = set()
        if any(marker in value.casefold() for value in classes
               for marker in ("private", "admin", "executive")):
            roles.add("excluded_file")
        if tag.lower() == "div":
            if "print-meeting-name" in classes:
                roles.add("title")
            if "print-meeting-date" in classes:
                roles.add("date")
        if tag.lower() in {"div", "a"} and "public-file" in classes:
            roles.add("file")
        if tag.lower() in {"script", "style", "template"}:
            self.suppressed += 1
        self.stack.append((tag.lower(), roles))
        active = set().union(*(role for _, role in self.stack))
        if (tag.lower() == "a" and fields.get("href") and "file" in active
                and "excluded_file" not in active and not self.suppressed):
            self.files.append(fields["href"])

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            open_tag, _ = self.stack[index]
            if open_tag == tag:
                removed = self.stack[index:]
                del self.stack[index:]
                self.suppressed = max(0, self.suppressed - sum(
                    1 for item, _ in removed if item in {"script", "style", "template"}))
                break

    def handle_data(self, data):
        if self.suppressed:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.text.append(clean)
        roles = set().union(*(role for _, role in self.stack)) if self.stack else set()
        if "title" in roles:
            self.title.append(clean)
        if "date" in roles:
            self.meeting_date.append(clean)


def _parse_detail(content: bytes, parser_bytes: int | None = None) -> dict:
    if not isinstance(content, bytes) or (parser_bytes is not None and len(content) > parser_bytes):
        raise ValueError("The BoardDocs printable agenda exceeds its configured parser byte limit.")
    try:
        parser = _PrintAgenda()
        parser.feed(content.decode("utf-8-sig"))
        parser.close()
    except (UnicodeError, ValueError):
        raise ValueError("The BoardDocs printable agenda was not valid UTF-8 HTML.") from None
    title = " ".join(parser.title).strip()
    meeting_date = " ".join(parser.meeting_date).strip()
    if not title or not meeting_date:
        raise ValueError("The BoardDocs printable agenda omitted its declared title or date fields.")
    return {"title": title, "meeting_date": meeting_date,
            "normalized_date": _meeting_date(meeting_date),
            "text": " ".join(parser.text), "public_file_links": list(dict.fromkeys(parser.files))}


def _listing_normalized(source, row):
    raw_date = row.get("numberdate")
    raw_date = raw_date if isinstance(raw_date, str) else None
    return {
        "external_id": row["meeting_id"], "title": row["original"].get("name"),
        "meeting_date": _meeting_date(raw_date), "source_date": raw_date,
        "source_unid": row.get("unid"), "url": source.url,
        "documents": [], "recordings": [], "agenda_items": [],
        "agenda_html_availability": "not_fetched",
        "documents_availability": "not_requested_by_observed_reader",
        "agenda_items_availability": "not_mapped_by_observed_reader",
        "time_zone_status": "unknown",
    }


def listing_bundle(source, namespace, content: bytes, rows: list[dict]) -> dict:
    """Retain one listing response and selected, title-incomplete meeting records."""
    mapped = [(_listing_normalized(source, row), row["original"], "meeting") for row in rows]
    bundle = make_bundle(source, namespace, content, LISTING_FORMAT, mapped)
    bundle["extensions"]["boarddocs_listing"] = {
        "empty_placeholder_rows": sum(row == {} for row in json.loads(content.decode("utf-8-sig"))),
        "catalog_complete": False,
    }
    return bundle


def detail_bundle(source, namespace, content: bytes, meeting_id: str, listing_row: dict | None = None,
                  *, parser_bytes: int | None = None) -> dict:
    """Map one selected PRINT-AgendaDetailed response to its listing-issued meeting ID."""
    if not isinstance(meeting_id, str) or not _MEETING_ID.fullmatch(meeting_id):
        raise ValueError("A BoardDocs detail response requires a selected listing-issued meeting ID.")
    parsed = _parse_detail(content, parser_bytes)
    raw_listing = (listing_row or {}).get("original", {})
    listing_date = raw_listing.get("numberdate") if isinstance(raw_listing.get("numberdate"), str) else None
    if (parsed['normalized_date'] and _meeting_date(listing_date)
            and parsed['normalized_date'] != _meeting_date(listing_date)):
        raise ValueError('BoardDocs detail date does not match the selected listing.')
    normalized = {
        "external_id": meeting_id, "title": parsed["title"],
        "meeting_date": parsed["normalized_date"] or _meeting_date(listing_date),
        "source_date": parsed["meeting_date"], "listing_date": listing_date,
        "source_unid": raw_listing.get("unid"), "url": source.url,
        "documents": [], "source_public_file_links": parsed["public_file_links"],
        "recordings": [], "agenda_items": [],
        "agenda_html_availability": "rendered_text_only",
        "documents_availability": "supplied_href_strings_only_not_fetched",
        "agenda_items_availability": "not_mapped_by_observed_reader",
        "time_zone_status": "unknown",
    }
    raw = {"listing_row": raw_listing, "detail_title": parsed["title"],
           "detail_date": parsed["meeting_date"], "public_file_links": parsed["public_file_links"]}
    bundle = make_bundle(source, namespace, content, DETAIL_FORMAT, [(normalized, raw, "meeting")])
    bundle["records"][0]["text"] = [{
        "field": "print_agenda_rendered_text", "text": parsed["text"],
        "citation_url": source.url, "completeness": "third_party_reader_rendered_text_partial",
        "provenance": {"method": "pinned_llama_index_boarddocs_reader_mapping",
                       "capture_sha256": bundle["capture"]["sha256"]},
    }] if parsed["text"] else []
    bundle["records"][0]["normalized_sha256"] = canonical_hash(normalized)
    bundle["capture"]["content_type_hint"] = "text/html"
    return bundle


def parse_bundle(source, namespace, content: bytes, input_format: str) -> dict:
    """Saved-capture parser; detail HTML needs its listing ID and is capture-only here."""
    if input_format == LISTING_FORMAT:
        return listing_bundle(source, namespace, content, parse_listing(source, content))
    if input_format == DETAIL_FORMAT:
        parsed = _parse_detail(content)
        bundle = make_bundle(source, namespace, content, DETAIL_FORMAT, [])
        bundle["capture"]["content_type_hint"] = "text/html"
        bundle["extensions"]["detail_parse"] = {
            "title": parsed["title"], "date": parsed["meeting_date"],
            "public_file_links": parsed["public_file_links"],
            "record_identity_status": "unavailable_without_the_selected_listing_meeting_id",
        }
        return bundle
    raise ValueError("The BoardDocs saved input format is not recognized.")



def request_specs(source, meeting_id: str | None = None) -> dict:
    """Return the literal guarded POST specs established by the pinned reader.

    The caller supplies transport byte/deadline bounds and must disable redirects.
    No browser user-agent or challenge workaround is included.
    """
    parts, site, committee = _configured_source(source)
    origin = f"{parts.scheme}://{parts.netloc}"
    headers = {"Accept": "application/json, text/javascript, */*; q=0.01",
               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
               "X-Requested-With": "XMLHttpRequest"}
    specs = {"listing": {"url": f"{origin}/{site}/Board.nsf/BD-GetMeetingsList?open",
                          "method": "POST",
                          "body": urlencode({"current_committee_id": committee}).encode("ascii"),
                          "headers": dict(headers), "allowed_origins": (origin,),
                          "allow_redirects": False}}
    if meeting_id is not None:
        if not isinstance(meeting_id, str) or not _MEETING_ID.fullmatch(meeting_id):
            raise ValueError("A BoardDocs detail request requires a safe listing-issued meeting ID.")
        specs["detail"] = {"url": f"{origin}/{site}/Board.nsf/PRINT-AgendaDetailed",
                            "method": "POST",
                            "body": urlencode({"id": meeting_id,
                                               "current_committee_id": committee}).encode("ascii"),
                            "headers": dict(headers), "allowed_origins": (origin,),
                            "allow_redirects": False}
    return specs


def fetch_detail(engine, source, namespace, external_id, bounds, context, transport):
    """Explicit printable read bound to a meeting already captured in this scope."""
    from time import monotonic

    from ..engine import source_identity_key
    from ..models import Error, OperationResult
    from ..storage import operation_cancelled

    spec = request_specs(source, external_id)['detail']
    identity = {'provider': source.provider, 'namespace': namespace,
                'record_type': 'meeting', 'external_id': external_id}
    stored = (engine.storage.get('records', source_identity_key(identity), scope=context.scope)
              if engine.storage else None)
    record = stored.value if stored else None
    if isinstance(record, dict) and 'record' in record:
        record = record['record']
    original = record.get('original') if isinstance(record, dict) else None
    raw = original.get('listing_row', original) if isinstance(original, dict) else None
    if (not isinstance(raw, dict) or str(raw.get('unique')) != external_id
            or record.get('source_url') != source.url):
        raise ValueError('BoardDocs detail requires a captured meeting from the configured public source.')
    if bounds.checkpoint:
        raise ValueError('A selected BoardDocs detail does not accept discovery continuation.')
    coverage = {'scope': 'one selected third-party-source-backed printable agenda',
                'catalog_complete': False, 'source_complete': False,
                'provider_contract': 'undocumented; no live vendor acceptance',
                'files': 'supplied href strings only, not downloaded'}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    retained = None
    try:
        response = transport.request(**spec, byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes),
                                     deadline_seconds=bounds.deadline_seconds)
        if (response.status != 200 or response.url != spec['url']
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError('The printable response was denied, redirected or exceeded bounds.')
        retained = make_bundle(source, namespace, response.content, DETAIL_FORMAT, [])
        retained['capture']['retrieval_url'] = spec['url']
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', retained, coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError('The printable response exceeded its deadline.')
        bundle = detail_bundle(source, namespace, response.content, external_id,
                               {'original': raw}, parser_bytes=bounds.parser_bytes)
        bundle['capture']['retrieval_url'] = spec['url']
        return OperationResult('partial', bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult('partial' if retained else 'failed', retained,
            errors=(Error('provider_detail_unavailable',
                'The selected printable agenda could not be retrieved or validated.', source=source.url),),
            coverage=coverage, operation_id=context.operation_id)
