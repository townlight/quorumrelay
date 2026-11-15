"""Observed public TelVue player declarations and supplied WebVTT; no script execution."""
from copy import deepcopy
import json
import re
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlsplit

from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .identification import validate_url
from .iqm2_player import Scripts
from .native import make_bundle

FORMAT = "telvue-public-player-html"


def player_context(source):
    validate_url(source.url)
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/player/([A-Za-z0-9_-]+)(?:/playlists/[1-9][0-9]*)?/media/([1-9][0-9]{0,18})", parsed.path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (source.provider != "telvue" or parsed.scheme != "https" or parsed.hostname != "videoplayer.telvue.com"
            or parsed.port not in {None, 443} or parsed.fragment or not match
            or set(query) - {"fullscreen", "showtabssearch"}
            or any(len(v) != 1 or v[0] not in {"true", "false"} for v in query.values())):
        raise ValueError("Select an exact TelVue public native-media player URL.")
    return match[2]


def parse_bundle(source, namespace, content):
    identity = player_context(source)
    scripts = Scripts()
    scripts.feed(content.decode("utf-8-sig", errors="strict"))
    declarations = []
    for script in scripts.scripts:
        for match in re.finditer(r"Player\.setupData\['playlist'\]\s*=\s*", script):
            value, end = json.JSONDecoder().raw_decode(script[match.end():])
            if not script[match.end() + end:].lstrip().startswith(";"):
                raise ValueError("Only a literal JSON playlist assignment is accepted.")
            declarations.append(value)
    if (len(declarations) != 1 or not isinstance(declarations[0], list) or len(declarations[0]) != 1
            or not isinstance(declarations[0][0], dict)):
        raise ValueError("One literal JSON native-media playlist row is required.")
    row = declarations[0][0]
    if row.get("mediaid") != "medium/" + identity or not isinstance(row.get("title"), str) or not row["title"].strip():
        raise ValueError("The declared media identity does not match the configured player.")
    media = row.get("file")
    validate_url(media)
    if urlsplit(media).scheme != "https" or not urlsplit(media).path.endswith(".m3u8"):
        raise ValueError("The observed player requires a supplied HTTPS HLS locator.")
    tracks, values = [], row.get("tracks", [])
    if not isinstance(values, list):
        raise ValueError("Player tracks must be a supplied array.")
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("Player tracks must be supplied objects.")
        if item.get("kind") != "captions":
            continue
        target = urljoin(source.url, item.get("file", ""))
        validate_url(target)
        parsed = urlsplit(target)
        if (parsed.scheme != "https" or parsed.netloc != urlsplit(source.url).netloc
                or not re.fullmatch(r"/closed_captions/[A-Za-z0-9_-]+", parsed.path)
                or parsed.fragment or any(t["url"] == target for t in tracks)
                or not isinstance(item.get("label"), str) or not item["label"].strip()):
            raise ValueError("The observed caption must be an exact same-origin supplied locator and label.")
        # The source supplies display labels, not a language-code field.
        tracks.append({"url": target, "kind": "captions", "source_label": item["label"],
                       "availability": "supplied_locator_not_fetched"})
    normalized = {"external_id": identity, "title": row["title"], "url": source.url,
                  "time_zone_status": "unknown", "documents": [], "recordings": [{
                      "url": media, "player_url": source.url, "media_type": "application/vnd.apple.mpegurl",
                      "source_duration": deepcopy(row.get("duration")), "caption_tracks": tracks}]}
    return make_bundle(source, namespace, content, FORMAT,
                       [(normalized, deepcopy(row), "recording")])


def fetch_captions(engine, source, namespace, request, bounds, context, transport):
    from .retrieval import _download_origins
    if not context.allows("fetch", namespace):
        raise ValueError("The source namespace is not authorized for fetch.")
    if request.get("external_id") != player_context(source):
        raise ValueError("The requested native ID does not match the configured player.")
    if bounds.checkpoint is not None or bounds.max_pages < 2:
        raise ValueError("Player and supplied caption require two request pages and no checkpoint.")
    deadline, transferred, bundle = monotonic() + bounds.deadline_seconds, 0, None
    coverage = {"scope": "one selected TelVue player and one supplied WebVTT file",
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
        selected = tracks[:1] if language == "*" else [t for t in tracks if t["source_label"] == language]
        if len(selected) != 1:
            raise ValueError("No unique supplied track matches the requested language label.")
        track = selected[0]
        content = get(track["url"], _download_origins(source, track["url"]), ("text/vtt", "application/octet-stream"))
        text = content.decode("utf-8-sig", errors="strict")
        if re.match(r"\AWEBVTT(?:[ \t][^\r\n]*)?(?:\r?\n|\Z)", text) is None or "-->" in text.splitlines()[0]:
            raise ValueError("The supplied file has no recognizable WebVTT header.")
        capture = make_bundle(source, namespace, content, "telvue-supplied-webvtt", [])["capture"]
        capture.update(source_url=track["url"], retrieval_url=track["url"])
        bundle["captures"] = [capture]
        record["normalized"].update(supplied_caption_text=text, supplied_caption_format="webvtt_source_text")
        track["availability"] = "supplied_file_received"
        record["relationships"] = [{"relation": "recording", "value": deepcopy(recording)}]
        record["text"].append({"field": "supplied_caption_text", "text": text, "citation_url": track["url"],
            "completeness": "supplied_file_only", "provenance": {"method": "telvue_player_declared_webvtt",
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
            errors=(Error("supplied_caption_unavailable", "The exact declared TelVue caption could not be verified.",
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
