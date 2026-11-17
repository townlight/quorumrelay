"""Observed Swagit player and supplied source text; never execute its scripts."""

from copy import deepcopy
from datetime import datetime
import re
from time import monotonic
from urllib.parse import urljoin, urlsplit

from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .escribe_detail import Page
from .identification import validate_url
from .native import make_bundle

FORMAT = "swagit-public-player-html"


def player_context(source):
    validate_url(source.url)
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/videos/([1-9][0-9]{0,18})", parsed.path)
    if (source.provider != "swagit" or parsed.scheme != "https" or not match
            or not re.fullmatch(r"[a-z0-9-]+(?:\.new)?\.swagit\.com", parsed.hostname or "")
            or parsed.port not in {None, 443} or parsed.query or parsed.fragment):
        raise ValueError("Select an exact supplied Swagit public video URL and native ID.")
    return match[1]


def parse_bundle(source, namespace, content):
    identity = player_context(source)
    html = content.decode("utf-8-sig", errors="strict")
    page = Page()
    page.feed(html)
    nodes = list(page.root.walk())
    headings = [n.text() for n in nodes if n.tag == "h1" and n.text()]
    panels = [n for n in nodes if n.attrs.get("id") == "transcript"]
    players = [n for n in nodes if n.tag == "video-js" and n.attrs.get("id") == "vjs-player"]
    fragments = [n for n in nodes if n.attrs.get("id") == "transcript-fragments"]
    if len(headings) != 1 or len(panels) != 1 or len(players) != 1 or len(fragments) != 1:
        raise ValueError("The observed player/transcript structure is missing or ambiguous.")
    downloads = [urljoin(source.url, n.attrs["href"]) for n in panels[0].walk()
                 if n.tag == "a" and n.text() == "Download Transcript" and n.attrs.get("href")]
    if downloads != [source.url + "/transcript"] or fragments[0] not in list(panels[0].walk()):
        raise ValueError("The transcript download does not bind the selected native video.")
    match = re.fullmatch(r"([A-Z][a-z]{2} [0-9]{2}, [0-9]{4}) (.+)", headings[0])
    if not match:
        raise ValueError("The supplied player heading has no recognized date/title.")
    day = datetime.strptime(match[1], "%b %d, %Y").date().isoformat()
    tracks = []
    for node in players[0].walk():
        if node.tag != "track" or node.attrs.get("kind") != "captions":
            continue
        target = urljoin(source.url, node.attrs.get("src", ""))
        validate_url(target)
        parsed = urlsplit(target)
        if (parsed.scheme != "https" or parsed.port not in {None, 443} or parsed.fragment
                or not parsed.path.lower().endswith(".vtt") or any(t["url"] == target for t in tracks)):
            raise ValueError("The supplied caption track is invalid or duplicated.")
        tracks.append({"url": target, "kind": "captions", "source_language": node.attrs.get("srclang"),
                       "source_label": node.attrs.get("label"), "availability": "supplied_locator_not_fetched"})
    # One exact literal player.src declaration is metadata, never evaluated code.
    from .iqm2_player import Scripts
    scripts = Scripts()
    scripts.feed(html)
    declarations = [v for s in scripts.scripts for v in re.findall(
        r'player\.src\(\{type:\s*"application/x-mpegURL",\s*src:\s*"([^"\\]+)"\}\)', s)]
    if len(declarations) != 1:
        raise ValueError("The supplied HLS player declaration is missing or ambiguous.")
    media = declarations[0]
    validate_url(media)
    if urlsplit(media).scheme != "https" or not urlsplit(media).path.endswith(".m3u8"):
        raise ValueError("The player declaration is not a supplied HTTPS HLS locator.")
    text = fragments[0].text()
    normalized = {"external_id": identity, "title": match[2], "meeting_date": day,
                  "source_heading": headings[0], "source_date_literal": match[1],
                  "url": source.url, "time_zone_status": "unknown", "documents": [],
                  "recordings": [{"url": media, "media_type": "application/x-mpegURL",
                                  "player_url": source.url, "caption_tracks": tracks}],
                  "transcript_download_url": downloads[0], "supplied_transcript_text": text,
                  "transcript_availability": "supplied_rendered_text" if text else "empty_supplied_panel"}
    bundle = make_bundle(source, namespace, content, FORMAT,
                         [(normalized, {"source_heading": headings[0], "native_video_id": identity}, "meeting")])
    if text:
        record = bundle["records"][0]
        record["text"] = [{"field": "supplied_transcript_text", "text": text, "citation_url": source.url,
            "completeness": "supplied_rendered_panel_only", "provenance": {
                "method": "swagit_rendered_transcript", "capture_sha256": record["capture_sha256"],
                "cue_timing_interpretation": "not_performed", "content_language": "not_verified"}}]
    return bundle


def fetch_captions(engine, source, namespace, request, bounds, context, transport):
    from .retrieval import _download_origins
    if not context.allows("fetch", namespace):
        raise ValueError("The source namespace is not authorized for fetch.")
    if request.get("external_id") != player_context(source):
        raise ValueError("The requested native ID does not match the configured player.")
    if bounds.checkpoint is not None or bounds.max_pages < 2:
        raise ValueError("Player and supplied caption require two request pages and no checkpoint.")
    deadline, transferred, bundle = monotonic() + bounds.deadline_seconds, 0, None
    coverage = {"scope": "one selected Swagit player and one supplied WebVTT file",
                "source_complete": False, "catalog_complete": False, "pages": 0,
                "generation_requested": False, "polling": False, "playback_verified": False,
                "content_language": None, "cue_timing_interpretation": "not_performed"}

    def get(url, origins, mimes):
        nonlocal transferred
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        remaining = min(bounds.parser_bytes, bounds.transfer_bytes - transferred)
        seconds = deadline - monotonic()
        if remaining <= 0 or seconds <= 0:
            raise ValueError("The supplied caption transfer exceeded operation bounds.")
        response = transport.request(url, headers={"Accept": ", ".join(mimes)}, allowed_origins=origins,
            allow_redirects=False, byte_limit=remaining, deadline_seconds=seconds)
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if (response.status != 200 or response.url != url or len(response.content) > remaining
                or monotonic() >= deadline or response.content_type.split(";", 1)[0].strip().lower() not in mimes):
            raise ValueError("The exact bounded player/caption response was not returned.")
        transferred += len(response.content)
        coverage["pages"] += 1
        return response.content

    try:
        player = get(source.url, (_origin(source.url),), ("text/html",))
        bundle = parse_bundle(source, namespace, player)
        record = bundle["records"][0]
        recording = record["normalized"]["recordings"][0]
        tracks = recording["caption_tracks"]
        language = request.get("caption_language")
        selected = tracks[:1] if language == "*" else [t for t in tracks if t["source_language"] == language]
        if len(selected) != 1:
            raise ValueError("No unique supplied track matches the requested language label.")
        track = selected[0]
        content = get(track["url"], _download_origins(source, track["url"]), ("text/vtt", "application/octet-stream"))
        text = content.decode("utf-8-sig", errors="strict")
        if re.match(r"\AWEBVTT(?:[ \t][^\r\n]*)?(?:\r?\n|\Z)", text) is None or "-->" in text.splitlines()[0]:
            raise ValueError("The supplied file has no recognizable WebVTT header.")
        capture = make_bundle(source, namespace, content, "swagit-supplied-webvtt", [])["capture"]
        capture.update(source_url=track["url"], retrieval_url=track["url"])
        bundle["captures"] = [capture]
        record["normalized"].update(supplied_caption_text=text, supplied_caption_format="webvtt_source_text")
        track["availability"] = "supplied_file_received"
        record["relationships"] = [{"relation": "recording", "value": deepcopy(recording)}]
        record["text"].append({"field": "supplied_caption_text", "text": text, "citation_url": track["url"],
            "completeness": "supplied_file_only", "provenance": {"method": "swagit_player_declared_webvtt",
                "capture_sha256": capture["sha256"], "player_capture_sha256": bundle["capture"]["sha256"],
                "cue_timing_interpretation": "not_performed", "content_language": "not_verified"}})
        record["normalized_sha256"] = canonical_hash(record["normalized"])
        coverage["caption_file_received"] = True
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if monotonic() >= deadline:
            raise ValueError("The caption mapping exceeded its operation deadline.")
        return OperationResult("partial", bundle, coverage=coverage, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult("partial" if bundle else "failed", bundle,
            errors=(Error("supplied_caption_unavailable", "The exact declared Swagit caption could not be verified.",
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
