"""Bounded public iframe literal metadata/captions; never execute player scripts."""
from copy import deepcopy
from html.parser import HTMLParser
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from ..engine import canonical_hash
from ..models import Error, OperationResult
from .contracts import _origin
from .native import make_bundle, wistia_row

FORMAT = "wistia-public-embed-html"


def media_id(source):
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/embed/iframe/([A-Za-z0-9]{1,128})", parsed.path)
    if (source.provider != "wistia" or source.input_format != FORMAT or parsed.scheme != "https"
            or parsed.hostname not in {"fast.wistia.com", "fast.wistia.net"}
            or parsed.port not in {None, 443} or parsed.query or parsed.fragment or not match or source.options):
        raise ValueError("Use an exact public HTTPS Wistia iframe URL/format without options.")
    return match[1]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.current = []
        self.values = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = "src" not in dict(attrs)
            self.current = []

    def handle_data(self, value):
        if self.active:
            self.current.append(value)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.values.append("".join(self.current))
            self.active = False


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate native player JSON keys are ambiguous.")
        result[key] = value
    return result


def parse_bundle(source, namespace, content):
    identity = media_id(source)
    scripts = Scripts()
    scripts.feed(content.decode("utf-8-sig"))
    candidates = [(script, match.end()) for script in scripts.values
                  for match in re.finditer(r"\bW\.iframeInit\s*\(\s*", script)]
    if len(candidates) != 1:
        raise ValueError("One literal native iframe initialization is required.")
    script, offset = candidates[0]
    def invalid_constant(value):
        raise ValueError("Non-JSON player constant.")
    value, end = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=invalid_constant).raw_decode(
        script[offset:])
    if (not re.match(r"\s*,\s*\{\s*\}\s*\)\s*;", script[offset + end:])
            or not isinstance(value, dict) or value.get("hashedId") != identity):
        raise ValueError("The literal player does not match the exact requested media identity.")
    normalized, kind = wistia_row(source, {**value, "hashed_id": identity})
    normalized.update(native_fields=deepcopy(value), caption_timing="not_supplied_by_embedded_text")
    captions = value.get("captions", [])
    if not isinstance(captions, list):
        raise ValueError("Supplied captions must be an array.")
    normalized["captions_availability"] = ("supplied" if captions else
        "supplied_empty_array" if "captions" in value else "not_supplied")
    rows = [(normalized, value, kind)]
    seen = set()
    for caption in captions:
        if (not isinstance(caption, dict) or not isinstance(caption.get("language"), str)
                or not caption["language"] or not isinstance(caption.get("text"), str)):
            raise ValueError("Each embedded caption requires literal language and text fields.")
        language = caption["language"]
        if language in seen:
            raise ValueError("Duplicate caption language keys cannot be merged safely.")
        seen.add(language)
        rows.append(({"external_id": json.dumps({"media_id": identity, "language": language}, sort_keys=True),
            "title": "Supplied captions (" + language + ")", "url": source.url,
            "native_language_key": language, "language_code_interpretation": "not_inferred",
            "media_id": identity, "native_fields": deepcopy(caption), "documents": [], "recordings": [],
            "text_availability": "supplied_text" if caption["text"] else "empty_supplied_text",
            "caption_timing": "not_supplied_by_embedded_text", "time_zone_status": "not_supplied"},
            caption, "transcript"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"][1:]:
        record["identity"].update(derivation="native_media_id_and_caption_language_key",
            stability="Derived composite of supplied media identity and literal caption language key.")
        record["relationships"] = [{"relation": "recording", "identity": {
            "provider": source.provider, "namespace": namespace, "record_type": "recording", "external_id": identity}}]
        record["text"] = [{"field": "text", "text": record["original"]["text"], "citation_url": source.url,
            "completeness": "supplied_embedded_caption_text", "provenance": {
                "method": "wistia_literal_iframe_caption", "native_language_key": record["original"]["language"],
                "capture_sha256": bundle["capture"]["sha256"]}}]
        record["normalized_sha256"] = canonical_hash(record["normalized"])
    return bundle


def fetch(source, namespace, request, bounds, context, transport):
    identity = media_id(source)
    if ("related" in request or request.get("external_id", identity) != identity
            or request.get("caption_language") not in {None, "*"}
            or bounds.checkpoint or bounds.date_from or bounds.date_to or source.body):
        raise ValueError("Select the exact iframe and all supplied caption tracks; no meeting/date/page inference.")
    deadline = monotonic() + bounds.deadline_seconds
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    try:
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        response = transport.request(source.url, byte_limit=limit, deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(_origin(source.url),), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        mime = response.content_type.split(";", 1)[0].lower().strip()
        if (response.status != 200 or response.url != source.url or mime != "text/html"
                or len(response.content) > limit or monotonic() >= deadline):
            raise ValueError("The exact bounded public iframe was unavailable.")
        bundle = parse_bundle(source, namespace, response.content)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        if len(bundle["records"]) > bounds.max_records or monotonic() >= deadline:
            raise ValueError("The complete selected media/caption bundle exceeds bounds.")
        return OperationResult("partial", bundle, coverage={"scope": "one public iframe and supplied caption text",
            "source_complete": False, "catalog_complete": False, "caption_tracks": len(bundle["records"]) - 1,
            "timing": "not_supplied_by_embedded_text", "media_bytes_downloaded": False,
            "meeting_date": "not_inferred", "pages": 1}, operation_id=context.operation_id)
    except (ValueError, TypeError, KeyError, OSError):
        return OperationResult("failed", errors=(Error("wistia_embed_unverified",
            "The exact public iframe metadata/captions could not be verified.", source=source.url),),
            operation_id=context.operation_id)
