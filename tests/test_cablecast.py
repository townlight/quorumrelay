"""Cablecast shows, video links and caption tracks from saved public Loveland, CO captures; no live network."""
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.cablecast import title_day
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures" / "cablecast"
HOST = "reflect-cityofloveland-co.cablecast.tv"
ORIGIN = "https://" + HOST
SOURCE = Source("cablecast", ORIGIN + "/")


def fixture(name):
    return (FIXTURES / name).read_bytes()


SHOWS = fixture("shows.json")
# vod id -> (vod json, master playlist): vod 521 (show 732) names no caption playlist, vod 516 (show 726) does.
VODS = {530: ("vod-530.json", "vod.m3u8"), 516: ("vod-726.json", "vod-726.m3u8"), 521: ("vod-732.json", "vod-732.m3u8")}
SHOW_FILES = {746: "show-746.json", 726: "show-726.json", 732: "show-732.json"}
FOLDERS = {"store-3/746-cc-v2": 530, "store-3/726-PC-v3": 516, "store-3/732-Planning-Commission-August-24-2026-v2": 521}


class Transport:
    def __init__(self, shows=SHOWS, pages=None, fail=()):
        self.shows, self.pages, self.fail, self.calls = shows, pages or {}, tuple(fail), []

    def request(self, url, **kwargs):
        self.calls.append(url)
        parts = urlsplit(url)
        assert kwargs["allow_redirects"] is False and kwargs["allowed_origins"] == (ORIGIN,)
        assert parts.scheme + "://" + parts.hostname == ORIGIN
        assert not parts.path.endswith((".mp4", ".vtt")), "media and caption text must not be downloaded"
        if any(token in url for token in self.fail):
            return Response(url, b"", "text/plain", 404)
        if parts.path == "/cablecastapi/v1/shows":
            page = int(parse_qs(parts.query).get("offset", ["0"])[0])
            empty = b'{"meta": {"offset": %d, "pageSize": 200, "count": 751}, "shows": []}' % page
            return Response(url, self.pages.get(page, self.shows if page == 0 else empty), "application/json")
        tail = parts.path.rsplit("/", 2)
        if parts.path.startswith("/cablecastapi/v1/shows/"):
            return Response(url, fixture(SHOW_FILES[int(tail[-1])]), "application/json")
        if parts.path.startswith("/cablecastapi/v1/vods/"):
            return Response(url, fixture(VODS[int(tail[-1])][0]), "application/json")
        folder, name = parts.path.lstrip("/").rsplit("/", 1)
        if name == "vod.m3u8":
            return Response(url, fixture(VODS[FOLDERS[folder]][1]), "application/vnd.apple.mpegurl")
        assert name == "captions.en.m3u8" and FOLDERS[folder] in {516, 530}
        return Response(url, fixture("captions.en.m3u8"), "application/vnd.apple.mpegurl")


def discover(transport=None, source=SOURCE, request=None, **bounds):
    transport = transport or Transport()
    engine = create_engine(provider_transport=transport)
    bounds = {"date_from": "2026-08-01", "date_to": "2026-11-30", **bounds}
    result = engine.execute("discover", {"source": source.public_dict(), "bounds": bounds, **(request or {})})
    return result, transport


def by_id(result):
    return {r["identity"]["external_id"]: r for r in result.data["records"]}


def test_title_day_reads_the_day_a_show_title_names():
    assert title_day("City Council Meeting November 4, 2026") == date(2026, 11, 4)
    assert title_day("LURA Nov 10 2026") == date(2026, 11, 10)
    assert title_day("Council Study Session 11-10-2026") == date(2026, 11, 10)
    assert title_day("City Council - Oct 20 2026") == date(2026, 10, 20)
    assert title_day("Snow Ops team v8") is None and title_day("Meeting February 31, 2026") is None


def test_host_is_identified_and_foreign_hosts_are_not():
    engine = create_engine()
    found = engine.execute("identify", {"url": ORIGIN + "/internetchannel/show/746"})
    assert found.data["provider"] == "cablecast" and found.data["identified"] is True
    assert engine.execute("identify", {"url": "https://example.org/"}).data["provider"] is None
    plain = Source("cablecast", "http://" + HOST + "/")
    result = engine.execute("discover", {"source": plain.public_dict(), "bounds": {}})
    assert result.status == "failed"
    other = engine.execute("discover", {"source": Source("cablecast", "https://example.org/").public_dict(), "bounds": {}})
    assert other.status == "failed"


def test_cablecast_is_listed_beside_the_unchanged_31_baseline_families():
    rows = create_engine().providers().data["providers"]
    assert sum(1 for row in rows if row["formats"]) == 31
    extra = [row for row in rows if not row["formats"]]
    assert [row["provider"] for row in extra] == ["cablecast"]
    capabilities = extra[0]["capabilities"]
    assert capabilities["operations"]["discover"]["acceptance_status"] == "fixture_passed"
    assert capabilities["operations"]["create"]["implementation_status"] == "not_implemented"


def test_listing_returns_shows_with_video_titled_days_and_watch_links():
    result, transport = discover()
    assert result.status == "partial", result.public_dict()
    records = by_id(result)
    assert set(records) == {"750", "749", "748", "746", "744", "740", "737", "726"}
    council = records["746"]["normalized"]
    assert council["title"] == "City Council Meeting November 4, 2026" and council["meeting_date"] == "2026-11-04"
    assert council["url"] == ORIGIN + "/internetchannel/show/746"
    assert council["recordings"] == [{"external_id": "530", "kind": "video_on_demand", "media_type": "video",
                                      "url": ORIGIN + "/internetchannel/show/746", "availability": "supplied_player_link"}]
    assert council["captions_availability"] == "not_probed_by_listing" and council["body"] is None
    assert records["749"]["normalized"]["meeting_date"] == "2026-11-10"
    assert result.coverage["shows_without_video_omitted"] == 5 and result.coverage["shows_reported_by_site"] == 751
    assert result.coverage["catalog_complete"] is False
    first = parse_qs(urlsplit(transport.calls[0]).query)
    assert first["page_size"] == ["200"] and first["pageSize"] == ["200"]


def test_a_title_that_names_a_day_wins_over_the_event_date_and_dates_are_inclusive():
    result, _ = discover(date_from="2026-09-01", date_to="2026-09-30")
    # Show 732 is dated 2026-09-16 but its title names August 24; the title day is the meeting day.
    assert result.data["records"] == [] and result.coverage["filtered_records"] >= 2
    result, _ = discover(date_from="2026-08-24", date_to="2026-08-24")
    assert list(by_id(result)) == ["726"]
    assert result.data["records"][0]["normalized"]["date_source"] == "title"


def test_duplicate_shows_collapse_to_the_copy_with_a_caption_playlist():
    result, transport = discover(date_from="2026-08-24", date_to="2026-08-24")
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "726"
    value = record["normalized"]
    assert value["duplicate_show_ids"] == ["732"] and value["copy_selection"] == "copy_with_caption_playlist"
    assert value["captions_availability"] == "caption_playlist_named"
    assert value["captions"] == [{
        "language": "en", "name": "English", "playlist_url": ORIGIN + "/store-3/726-PC-v3/captions.en.m3u8",
        "format": "hls_subtitles_webvtt_segments", "text_availability": "not_read_playlist_link_only"}]
    recording = value["recordings"][0]
    assert recording["url"] == ORIGIN + "/store-3/726-PC-v3/vod.mp4" and recording["length_seconds"] == 6652
    assert recording["hls_playlist_url"] == ORIGIN + "/store-3/726-PC-v3/vod.m3u8"
    assert result.coverage["duplicate_copies_collapsed"] == 1 and result.coverage["caption_probes"] == 2
    # The list's own hasCaptions flag has the two copies the wrong way round and is not what picks one.
    assert value["source_status"]["has_captions_flag"] is False
    # Page one, the probes of the two copies (vod then vod.m3u8 each), then page two: the site reports 751 shows.
    assert [u.replace(ORIGIN, "").split("?")[0] for u in transport.calls] == [
        "/cablecastapi/v1/shows", "/cablecastapi/v1/vods/521", "/store-3/732-Planning-Commission-August-24-2026-v2/vod.m3u8",
        "/cablecastapi/v1/vods/516", "/store-3/726-PC-v3/vod.m3u8", "/cablecastapi/v1/shows"]


def test_duplicates_are_not_probed_beyond_the_page_budget_and_say_so():
    result, _ = discover(date_from="2026-08-24", date_to="2026-08-24", max_pages=2)
    value = result.data["records"][0]["normalized"]
    assert result.data["records"][0]["identity"]["external_id"] == "732"
    assert value["copy_selection"] == "first_listed_unprobed" and value["duplicate_show_ids"] == ["726"]
    assert result.coverage["duplicate_groups_unprobed"] == 1 and result.coverage["caption_probes"] == 0


def test_probe_failure_is_listed_and_the_first_copy_is_kept():
    result, _ = discover(Transport(fail=("/vods/",)), date_from="2026-08-24", date_to="2026-08-24")
    assert result.status == "partial" and result.data["records"][0]["identity"]["external_id"] == "732"
    assert [f["kind"] for f in result.coverage["failures"]] == ["caption_probe", "caption_probe"]


def test_provenance_ties_each_record_to_the_hashed_response():
    result, _ = discover()
    digest = hashlib.sha256(SHOWS).hexdigest()
    assert result.data["captures"][0]["sha256"] == digest and result.data["captures"][0]["input_format"] == "cablecast-shows-json"
    record = result.data["records"][0]
    assert record["capture_sha256"] == digest and record["identity"]["namespace"] == "//" + HOST
    assert record["identity"]["provider"] == "cablecast" and record["original"]["id"] == int(record["identity"]["external_id"])


def paged(count, per_page, ids):
    return lambda start: json.dumps({"meta": {"offset": start, "pageSize": per_page, "count": count}, "shows": [
        {"id": i, "title": f"City Council Meeting October {i - 100}, 2026", "eventDate": f"2026-10-{i - 100:02d}T00:00:00-06:00",
         "vods": [i], "hasCaptions": True} for i in ids]}).encode()


def test_paging_follows_the_offset_page_index_and_resumes_from_a_checkpoint():
    pages = {0: paged(4, 2, [102, 101])(0), 1: paged(4, 2, [104, 103])(1)}
    first, transport = discover(Transport(pages=pages), request=None, max_pages=1, date_from="2026-10-01", date_to="2026-10-31")
    assert sorted(by_id(first)) == ["101", "102"] and first.coverage["truncated"] is True
    second, again = discover(Transport(pages=pages), checkpoint=first.coverage["checkpoint"], date_from="2026-10-01", date_to="2026-10-31")
    assert sorted(by_id(second)) == ["103", "104"] and second.coverage["checkpoint"] is None
    assert parse_qs(urlsplit(again.calls[0]).query)["offset"] == ["1"] and len(again.calls) == 1


def test_a_repeated_page_is_reported_not_looped():
    page = paged(4, 2, [102, 101])
    result, _ = discover(Transport(pages={0: page(0), 1: page(1)}), date_from="2026-10-01", date_to="2026-10-31")
    assert result.status == "partial" and result.coverage["failures"][0]["reason"] == "pagination_cycle"
    assert sorted(by_id(result)) == ["101", "102"]


def test_page_without_paging_metadata_fails_cleanly():
    result, _ = discover(Transport(shows=b'{"shows": []}'))
    assert result.status == "failed" and result.errors[0].code == "provider_page_failed"


def test_fetch_one_show_links_video_and_the_caption_playlist_without_reading_text():
    engine = create_engine(provider_transport=Transport())
    result = engine.fetch_record(SOURCE, "746")
    assert result.status == "partial", result.public_dict()
    value = result.data["records"][0]["normalized"]
    assert value["recordings"][0]["url"] == ORIGIN + "/store-3/746-cc-v2/vod.mp4"
    assert value["recordings"][0]["length_seconds"] == 15694 and value["recordings"][0]["is_watchable"] is True
    track = value["captions"][0]
    assert track["playlist_url"] == ORIGIN + "/store-3/746-cc-v2/captions.en.m3u8" and track["segment_count"] == 5
    assert track["language"] == "en" and track["text_availability"] == "not_read_playlist_link_only"
    assert [r["url"].rsplit("/", 1)[1] for r in result.coverage["reads"]] == ["746", "530", "vod.m3u8", "captions.en.m3u8"]
    assert result.coverage["catalog_complete"] is False


def test_fetch_show_without_caption_playlist_says_so():
    engine = create_engine(provider_transport=Transport())
    value = engine.fetch_record(SOURCE, "732").data["records"][0]["normalized"]
    assert value["captions"] == [] and value["captions_availability"] == "no_caption_playlist"
    assert value["meeting_date"] == "2026-08-24" and value["recordings"][0]["url"].endswith("/vod.mp4")


def test_fetch_rejects_bad_ids_foreign_video_hosts_and_unsupported_downloads():
    engine = create_engine(provider_transport=Transport())
    assert engine.fetch_record(SOURCE, "../746").status == "failed"
    assert engine.fetch_record(SOURCE, "999").status == "failed"
    vod = json.loads(fixture("vod-530.json"))
    vod["vod"]["url"] = "https://media.example.org/746/vod.mp4"

    class Foreign(Transport):
        def request(self, url, **kwargs):
            if "/vods/" in url:
                return Response(url, json.dumps(vod).encode(), "application/json")
            return super().request(url, **kwargs)
    failed = create_engine(provider_transport=Foreign()).fetch_record(SOURCE, "746")
    assert failed.status == "failed" and failed.errors[0].details["reason"] == "vod_url_outside_contract"
    for request in ({"external_id": "746", "caption_language": "en"}, {"attachment": {"record_key": "x"}},
                    {"parent_id": "746", "record_type": "transcript"}):
        assert engine.fetch(SOURCE, request).status == "unsupported"


def test_fetch_stays_inside_a_small_page_budget():
    from quorumrelay import Bounds
    engine = create_engine(provider_transport=Transport())
    result = engine.fetch_record(SOURCE, "746", bounds=Bounds(max_pages=1))
    assert result.status == "partial" and result.coverage["failures"] == ["page_budget_before_vod_and_captions"]
    assert result.data["records"][0]["normalized"]["captions_availability"] == "not_probed_by_listing"


def test_saved_shows_and_show_parse_without_network_and_without_merging_copies():
    engine = create_engine()
    shows = engine.normalize(SOURCE, SHOWS, input_format="cablecast-shows-json")
    assert shows.status == "completed" and len(shows.data["records"]) == 10
    assert {"726", "732"} <= {r["identity"]["external_id"] for r in shows.data["records"]}
    one = engine.normalize(SOURCE, fixture("show-746.json"), input_format="cablecast-show-json")
    assert one.data["records"][0]["normalized"]["title"] == "City Council Meeting November 4, 2026"
    assert engine.normalize(SOURCE, b"[]", input_format="cablecast-shows-json").status == "failed"


def test_discover_honors_caller_namespace_policy_and_cancellation():
    engine = create_engine(provider_transport=Transport())
    request = {"source": SOURCE.public_dict(), "bounds": {}}
    denied = OperationContext(allowed_operations=frozenset({"discover"}), allowed_namespaces=frozenset({"//other.cablecast.tv"}))
    assert engine.execute("discover", {**request, "source": {**SOURCE.public_dict(), "namespace": "//other.cablecast.tv"}},
                          context=denied).status == "failed"
    cancelled = OperationContext()
    cancelled.cancellation.set()
    assert engine.execute("discover", request, context=cancelled).status == "cancelled"


def test_no_native_search_write_or_export_is_claimed():
    engine = create_engine(provider_transport=Transport())
    plan = engine.plan_write(SOURCE, {"changes": []})
    assert plan.status in {"unsupported", "failed"}
    search = engine.execute("search", {"native": True, "source": SOURCE.public_dict(), "query": {"terms": ["council"]}})
    assert search.status == "unsupported"
