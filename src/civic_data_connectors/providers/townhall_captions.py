"""One-shot reads of the player-declared full transcript display, never generation."""

from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
from time import monotonic
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import Request

from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .escribe_detail import VOID
from .native import make_bundle
from .novus import _cookies
from .townhall_detail import parse_bundle


class _DisplayText(HTMLParser):
    """Static fragment text; no script/CSS execution or inferred speaker/timestamps."""

    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.stack, self.parts, self.document = [], [], False
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"html", "head", "body", "form"}:
            self.document = True
        style = values.get("style", "").replace(" ", "").lower()
        hidden = (tag in {"script", "style", "template", "noscript", "iframe", "object", "svg"}
                  or "hidden" in values or values.get("aria-hidden", "").lower() == "true"
                  or "display:none" in style or "visibility:hidden" in style
                  or bool(self.stack and self.stack[-1][1]))
        if len(self.stack) >= 256:
            raise ValueError("Transcript fragment nesting exceeds its bound.")
        if tag not in VOID:
            self.stack.append((tag, hidden))
        self.parts.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.parts.append(data)


def _destination(source, content, location, event):
    text = content.decode("utf-8-sig")
    declarations = set(re.findall(
        r'var\s+url\s*=\s*"stream\.php\?"\s*\+\s*speaker\s*\+\s*"'
        r'(full=1&location_id=[0-9]+&id=[0-9]+&action=get_transcriptions)"\s*;', text))
    expected = f"full=1&location_id={location}&id={event}&action=get_transcriptions"
    if (declarations != {expected} or "function changeView(useSpeaker)" not in text
            or not re.search(r"type:\s*'GET'", text)
            or not re.search(r'\$\("#autocc"\)\.html\(response\)', text)):
        raise ValueError("The location-bound full transcript display declaration changed.")
    return urljoin(source.url, "stream.php?" + expected)


def fetch_captions(engine, source, namespace, request, bounds, context, transport):
    parts = urlsplit(source.url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    values = dict(pairs)
    if (parts.scheme != "https" or parts.hostname not in {"townhallstreams.com", "www.townhallstreams.com"}
            or parts.path != "/stream.php" or parts.fragment or parts.port not in {None, 443}
            or len(pairs) != 2 or set(values) != {"location_id", "id"}
            or any(re.fullmatch(r"[1-9][0-9]{0,18}", v) is None for v in values.values())
            or request["external_id"] != values["id"]):
        raise ValueError("Transcript retrieval requires the exact configured location/event player and native ID.")
    if request.get("caption_language") != "*":
        return OperationResult.unsupported("fetch_captions_language", reason=(
            "The observed display has no language-selection contract; only the supplied display is mapped."))
    if bounds.checkpoint or bounds.max_pages < 2:
        raise ValueError("One player plus one transcript read needs two request pages and no checkpoint.")
    deadline, transferred = monotonic() + bounds.deadline_seconds, 0
    cookies = CookieJar()
    bundle, errors = None, []
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "pages": 0,
        "scope": "one player-declared full transcript display snapshot", "catalog_complete": False,
        "source_complete": False, "generation_requested": False, "polling": False,
        "language": None, "timing_mapping": "unverified; no timestamp or speaker inference", "failures": []}

    def get(url):
        nonlocal transferred
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        limit = min(bounds.parser_bytes, bounds.transfer_bytes - transferred)
        seconds = deadline - monotonic()
        if seconds <= 0 or limit <= 0:
            raise ValueError("The transcript request exceeded time or transfer bounds.")
        request_headers = {"Accept": "text/html"}
        if url != source.url:
            request_headers["Referer"] = source.url
        cookie_request = Request(url)
        cookies.add_cookie_header(cookie_request)
        if cookie_request.has_header("Cookie"):
            request_headers["Cookie"] = cookie_request.get_header("Cookie")
        result = transport.request(url, headers=request_headers, byte_limit=limit,
            deadline_seconds=seconds, allowed_origins=(_origin(source.url),), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if (monotonic() >= deadline or result.status != 200 or result.url != url
                or not isinstance(result.content, bytes) or len(result.content) > limit
                or result.content_type.split(";", 1)[0].strip().lower() != "text/html"):
            raise ValueError("The transcript response left its exact bounded HTML contract.")
        transferred += len(result.content)
        _cookies(cookies, result, url)
        coverage["pages"] += 1
        return result

    try:
        player = get(source.url)
        bundle = parse_bundle(source, namespace, player.content)
        destination = _destination(source, player.content, values["location_id"], values["id"])
        record = bundle["records"][0]
        normalized = record["normalized"]
        normalized["recordings"][0]["captions_availability"] = "declared_display_not_retrieved"
        response = get(destination)
        captured = make_bundle(source, namespace, response.content, "town-hall-streams-transcript-display-html", [])
        captured["capture"]["retrieval_url"] = destination
        bundle["captures"] = [captured["capture"]]
        normalized["recordings"][0]["captions_availability"] = "display_received_not_recognized"
        parsed = _DisplayText(response.content)
        text = " ".join("".join(parsed.parts).split())
        if parsed.document or (response.content.strip() and (not text or text == "1")):
            raise ValueError("The transcript display returned an unrecognized document or sentinel.")
        if monotonic() >= deadline:
            raise ValueError("Transcript parsing exceeded its deadline.")
        normalized["transcript_availability"] = "supplied_display_text" if text else "supplied_full_response_empty"
        normalized["recordings"][0]["captions_availability"] = normalized["transcript_availability"]
        record["extensions"]["transcript_capture_sha256"] = captured["capture"]["sha256"]
        if text:
            normalized["transcript_text"] = text
            record["text"].append({"field": "transcript_text", "text": text, "citation_url": source.url,
                "completeness": "partial", "provenance": {"method": "provider_transcript_display_html",
                    "capture_sha256": captured["capture"]["sha256"], "retrieval_url": destination,
                    "timing_and_speaker_mapping": "not_inferred"}})
        coverage.update(transcript_text_available=bool(text), available_text="supplied_static_display_only")
        context.report(operation="fetch", pages=2, returned_records=1)
    except InterruptedError:
        if bundle:
            record = bundle["records"][0]
            record["normalized_sha256"] = canonical_hash(record["normalized"])
        return OperationResult("cancelled", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        coverage["failures"].append({"reason": "supplied_transcript_unavailable"})
        errors.append(Error("supplied_transcript_unavailable",
            "The declared transcript could not be retrieved or recognized; retained meeting data is partial.",
            source=source.url, retryable=True))
    if bundle:
        record = bundle["records"][0]
        record["normalized_sha256"] = canonical_hash(record["normalized"])
    return OperationResult("partial" if bundle else "failed", bundle, tuple(errors), coverage, context.operation_id)
