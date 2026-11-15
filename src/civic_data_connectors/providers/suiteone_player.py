"""Selected SuiteOne event transcript and literal player locators; no generated text."""
from copy import deepcopy
import re
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .escribe_detail import Page, Node
from .identification import validate_url
from .iqm2_player import Scripts
from .native import make_bundle

FORMAT = "suiteone-public-event-html"


def player_context(source):
    validate_url(source.url)
    parsed = urlsplit(source.url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    values = query.get("id", [])
    if (source.provider != "suiteone-media" or parsed.scheme != "https"
            or not re.fullmatch(r"[a-z0-9-]+\.suiteonemedia\.com", parsed.hostname or "")
            or parsed.port not in {None, 443} or parsed.path != "/event/" or parsed.fragment
            or set(query) != {"id"} or len(values) != 1
            or not re.fullmatch(r"[1-9][0-9]{0,18}", values[0])):
        raise ValueError("Select an exact supplied SuiteOne native event URL.")
    return values[0]


def parse_bundle(source, namespace, content):
    identity = player_context(source)
    html = content.decode("utf-8-sig", errors="strict")
    page = Page()
    page.feed(html)
    nodes = list(page.root.walk())
    titles = [n.text() for n in nodes if n.tag == "h1" and "ev-header" in n.classes()]
    shares = [n for n in nodes if n.tag == "input" and n.attrs.get("id") == "shareEventUrl"]
    panels = [n for n in nodes if n.attrs.get("id") == "transcriptPlayer" and n.attrs.get("role") == "tabpanel"]
    if (len(titles) != 1 or not titles[0] or len(shares) != 1 or len(panels) != 1
            or shares[0].attrs.get("data-eventid") != identity
            or shares[0].attrs.get("value") != "/event/?id=" + identity + "&ts=0"):
        raise ValueError("The selected public transcript must bind its native event/share context.")
    tables = [n for n in panels[0].walk() if n.tag == "table" and "transcriptTable" in n.classes()]
    if len(tables) != 1:
        raise ValueError("One player transcript table is required; duplicate display tables are not combined.")
    rows = []
    for row in tables[0].walk():
        if row.tag != "tr":
            continue
        cells = [n for n in row.children if isinstance(n, Node) and n.tag == "td"]
        if not cells:
            continue
        if (len(cells) != 3 or "bkm-row" not in cells[0].classes()
                or cells[1].attrs.get("aria-label") != "transcript text"
                or cells[2].attrs.get("aria-label") != "timestamp"):
            raise ValueError("The supplied transcript row layout is unrecognized.")
        rows.append({"text": cells[1].text(), "source_start": cells[0].attrs.get("data-time"),
                     "source_end": cells[0].attrs.get("data-time_end"),
                     "source_timestamp_literal": cells[2].text()})
    scripts = Scripts()
    scripts.feed(html)
    media = [value for script in scripts.scripts for value in re.findall(r"var src = '([^'\\]+)';", script)]
    captions = [value for script in scripts.scripts for value in re.findall(
        r"file:\s*'([^']*/Event/GetCaptions/\?eventId=[0-9]+)'\s*,\s*kind:\s*'captions'\s*,\s*'default':\s*true\s*,\s*label:\s*'English'", script)]
    expected_caption = _origin(source.url) + "/Event/GetCaptions/?eventId=" + identity
    if len(media) != 1 or captions != [expected_caption]:
        raise ValueError("One literal player and native-event caption declaration is required.")
    validate_url(media[0])
    if urlsplit(media[0]).scheme != "https" or not urlsplit(media[0]).path.endswith(".mp4"):
        raise ValueError("The observed selected player requires a supplied HTTPS MP4 locator.")
    text = "\n".join(row["text"] for row in rows)
    normalized = {"external_id": identity, "title": titles[0], "url": source.url,
        "time_zone_status": "unknown", "date_availability": "not_supplied_in_player_mapping",
        "documents": [], "recordings": [{"url": media[0], "player_url": source.url,
            "media_type": "video/mp4", "caption_tracks": [{"url": expected_caption,
                "kind": "captions", "source_label": "English", "availability": "supplied_locator_not_fetched"}]}],
        "supplied_transcript_text": text, "transcript_rows": rows,
        "transcript_availability": "supplied_rendered_table" if rows else "empty_supplied_table"}
    bundle = make_bundle(source, namespace, content, FORMAT,
        [(normalized, {"native_event_id": identity, "source_title": titles[0], "transcript_rows": deepcopy(rows)}, "meeting")])
    if text:
        bundle["records"][0]["text"] = [{"field": "supplied_transcript_text", "text": text,
            "citation_url": source.url, "completeness": "supplied_player_table_only", "provenance": {
                "method": "suiteone_rendered_transcript", "capture_sha256": bundle["capture"]["sha256"],
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
    coverage = {"scope": "one selected SuiteOne player and one supplied WebVTT file",
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
        capture = make_bundle(source, namespace, content, "suiteone-supplied-webvtt", [])["capture"]
        capture.update(source_url=track["url"], retrieval_url=track["url"])
        bundle["captures"] = [capture]
        record["normalized"].update(supplied_caption_text=text, supplied_caption_format="webvtt_source_text")
        track["availability"] = "supplied_file_received"
        record["relationships"] = [{"relation": "recording", "value": deepcopy(recording)}]
        record["text"].append({"field": "supplied_caption_text", "text": text, "citation_url": track["url"],
            "completeness": "supplied_file_only", "provenance": {"method": "suiteone_player_declared_webvtt",
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
            errors=(Error("supplied_caption_unavailable", "The exact declared SuiteOne caption could not be verified.",
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
