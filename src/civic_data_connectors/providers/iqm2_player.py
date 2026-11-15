"""One public iQM2 split-view player; decode literal data without evaluating JavaScript."""
import json
import re
from copy import deepcopy
from time import monotonic
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .iqm2_detail import _query, _positive
from .identification import validate_url
from .native import make_bundle
from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin

FORMAT = "iqm2-public-player-html"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.current = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = [] if "src" not in dict(attrs) else None

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin, query = urlsplit(source.url), _query(source.url)
    meeting = query.get("MeetingID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".iqm2.com")
            or origin.path != "/Citizens/SplitView.aspx" or origin.fragment
            or set(query) != {"Mode", "MeetingID", "Format"}
            or query.get("Mode") != "Video" or query.get("Format") != "Agenda" or not _positive(meeting)):
        raise ValueError("Select the exact supplied iQM2 Video/Agenda split-view meeting URL.")
    html = content.decode("utf-8-sig", errors="strict")
    from .escribe_detail import Page
    page = Page()
    page.feed(html)
    panels = [n for n in page.root.walk() if n.attrs.get("id") == "OutlinePanelInner"]
    if len(panels) != 1:
        raise ValueError("The player requires one meeting-bound outline panel.")
    outline = urlsplit(urljoin(source.url, panels[0].attrs.get("src", "")))
    values = _query(outline.geturl())
    if (outline.netloc != origin.netloc or outline.scheme != "https" or outline.fragment
            or outline.path != "/Citizens/Detail_Meeting.aspx" or values.get("ID") != meeting
            or values.get("Mode") != "Video" or values.get("Target") != "Detail"):
        raise ValueError("The player outline does not bind the selected native meeting.")
    scripts = Scripts()
    scripts.feed(html)
    declarations = []
    # This observed form wraps plain JSON in a JS single-quoted literal and eval.
    # Only the no-backslash literal form is mapped; eval is never called.
    pattern = r"\s*SetupJWPlayer\(eval\('([^'\\]*)'\),'(True|False)','(True|False)'\);\s*"
    for script in scripts.scripts:
        match = re.fullmatch(pattern, script)
        if match:
            declarations.append(match.groups())
        elif re.search(r"\bSetupJWPlayer\s*\(", script):
            raise ValueError("Computed or additional player code is not mapped.")
    if len(declarations) != 1:
        raise ValueError("One exact literal player declaration is required; computed scripts are not evaluated.")
    literal, dvr, transcript = declarations[0]
    sources = json.loads(literal)
    if not isinstance(sources, list) or not 1 <= len(sources) <= 64 or not all(isinstance(x, dict) for x in sources):
        raise ValueError("The supplied media source list is invalid or exceeds its bound.")
    first = sources[0]
    media = first.get("file")
    if not isinstance(media, str):
        raise ValueError("The first player source has no declared file URL.")
    validate_url(media)
    path = urlsplit(media).path.lower()
    mime = "application/x-mpegURL" if path.endswith(".m3u8") else "video/mp4" if path.endswith(".mp4") else None
    if urlsplit(media).scheme != "https" or mime is None:
        raise ValueError("Only the declared HTTPS MP4/HLS player source is mapped.")
    tracks = first.get("tracks", [])
    if not isinstance(tracks, list) or len(tracks) > 64:
        raise ValueError("The supplied text-track list is invalid or exceeds its bound.")
    captions = []
    if mime == "video/mp4" and transcript == "True" and tracks:
        track = tracks[0]
        if not isinstance(track, dict) or not isinstance(track.get("file"), str):
            raise ValueError("The selected subtitle track is malformed.")
        validate_url(track["file"])
        if urlsplit(track["file"]).scheme != "https":
            raise ValueError("The selected subtitle track requires HTTPS.")
        captions.append({"url": track["file"], "label": track.get("label"),
                         "kind": "subtitles", "language": "en", "language_provenance": "player_hardcoded_srclang",
                         "availability": "supplied_locator_not_fetched"})
    recording = {"url": source.url, "playback_url": media, "playback_type": mime,
        "media_bytes_verified": False, "playback_verified": False,
        "caption_tracks": captions, "source_enable_dvr": dvr, "source_has_transcript": transcript,
        "captions_availability": "supplied_locator_not_fetched" if captions else "no_active_track_in_declared_player"}
    normalized = {"external_id": meeting, "title": "iQM2 meeting " + meeting,
        "title_availability": "native_id_label_only", "url": source.url, "documents": [],
        "recordings": [recording], "time_zone_status": "unknown", "date_availability": "not_supplied_in_player_mapping"}
    return make_bundle(source, namespace, content, FORMAT,
        [(normalized, {"player_sources": sources, "meeting_id": meeting,
                       "enable_dvr": dvr, "has_transcript": transcript}, "meeting")])


def fetch_captions(engine, source, namespace, request, bounds, context, transport):
    """Preserve the first active supplied WebVTT file, without cue/language inference."""
    from .retrieval import _download_origins
    if not context.allows("fetch", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source fetch is not authorized."),))
    if request.get("caption_language") != "*":
        return OperationResult.unsupported("fetch_captions_language", reason=(
            "The player hardcodes srclang; it does not establish selectable content languages."))
    if bounds.checkpoint is not None or bounds.max_pages < 2:
        raise ValueError("The player and supplied caption require two request pages and no checkpoint.")
    # Validate the exact configured player before any I/O, not only after its response.
    query = _query(source.url)
    parsed = urlsplit(source.url)
    if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".iqm2.com")
            or parsed.path != "/Citizens/SplitView.aspx" or parsed.fragment
            or set(query) != {"Mode", "MeetingID", "Format"} or query.get("Mode") != "Video"
            or query.get("Format") != "Agenda" or not _positive(query.get("MeetingID"))
            or request.get("external_id") != query["MeetingID"]):
        raise ValueError("Use the exact configured native Video/Agenda player meeting ID.")
    deadline, transferred = monotonic() + bounds.deadline_seconds, 0
    coverage = {"scope": "one selected player and first active supplied WebVTT file",
        "source_complete": False, "catalog_complete": False, "pages": 0,
        "generation_requested": False, "polling": False, "content_language": None,
        "cue_timing_interpretation": "not_performed"}
    bundle = None

    def get(url, origins, mime):
        nonlocal transferred
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        remaining = min(bounds.parser_bytes, bounds.transfer_bytes - transferred)
        seconds = deadline - monotonic()
        if remaining <= 0 or seconds <= 0:
            raise ValueError("The supplied-caption transfer exceeded its bounds.")
        response = transport.request(url, headers={"Accept": mime}, allowed_origins=origins,
            allow_redirects=False, byte_limit=remaining, deadline_seconds=seconds)
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if (response.status != 200 or response.url != url or not isinstance(response.content, bytes)
                or len(response.content) > remaining or monotonic() >= deadline
                or response.content_type.split(";", 1)[0].strip().lower() != mime):
            raise ValueError("The supplied caption/player left its exact bounded response contract.")
        transferred += len(response.content)
        coverage["pages"] += 1
        return response.content

    try:
        player = get(source.url, (_origin(source.url),), "text/html")
        bundle = parse_bundle(source, namespace, player)
        record = bundle["records"][0]
        tracks = record["normalized"]["recordings"][0]["caption_tracks"]
        if tracks:
            target = tracks[0]["url"]
            content = get(target, _download_origins(source, target), "text/vtt")
            text = content.decode("utf-8-sig", errors="strict")
            if re.match(r"\AWEBVTT(?:[ \t][^\r\n]*)?(?:\r?\n|\Z)", text) is None or "-->" in text.splitlines()[0]:
                raise ValueError("The supplied file lacks a WebVTT header; no text format is guessed.")
            capture = make_bundle(source, namespace, content, "iqm2-supplied-webvtt", [])["capture"]
            capture.update(source_url=target, retrieval_url=target)
            bundle["captures"] = [capture]
            record["normalized"].update(supplied_caption_text=text,
                supplied_caption_format="webvtt_source_text", content_language=None)
            tracks[0]["availability"] = "supplied_file_received"
            recording = record["normalized"]["recordings"][0]
            recording["captions_availability"] = "supplied_file_received"
            record["relationships"] = [{"relation": "recording", "value": deepcopy(recording)}]
            record["text"].append({"field": "supplied_caption_text", "text": text, "citation_url": target,
                "completeness": "supplied_file_only", "provenance": {"method": "player_declared_webvtt",
                    "capture_sha256": capture["sha256"], "player_capture_sha256": bundle["capture"]["sha256"],
                    "cue_timing_interpretation": "not_performed", "content_language": "not_verified"}})
            record["normalized_sha256"] = canonical_hash(record["normalized"])
            coverage["caption_file_received"] = True
        else:
            coverage["caption_file_received"] = False
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if monotonic() >= deadline:
            raise ValueError("Caption parsing exceeded its deadline.")
        return OperationResult("partial", bundle, coverage=coverage, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult("partial" if bundle else "failed", bundle,
            errors=(Error("supplied_caption_unavailable", "The exact declared WebVTT file could not be verified.",
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
