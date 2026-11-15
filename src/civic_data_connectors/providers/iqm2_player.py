"""One public iQM2 split-view player; decode literal data without evaluating JavaScript."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .iqm2_detail import _query, _positive
from .identification import validate_url
from .native import make_bundle

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
