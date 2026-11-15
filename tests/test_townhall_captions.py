"""Actual declared player requests; empty observations and synthetic HTML display replies."""

import base64
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage

FIXTURES = Path(__file__).parent / "fixtures/townhall-transcripts"
URL = "https://townhallstreams.com/stream.php?location_id=72&id=74003"
SOURCE = Source("town-hall-streams", URL, input_format="town-hall-streams-event-html")
PLAYER = (FIXTURES / "hollis-74003.html").read_bytes()
TARGET = "https://townhallstreams.com/stream.php?full=1&location_id=72&id=74003&action=get_transcriptions"


class Vendor:
    def __init__(self, context, *, source=SOURCE, player=PLAYER):
        self.source, self.player, self.context = source, player, context
        self.calls, self.reply, self.fault = [], b"", None

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False and options["deadline_seconds"] > 0
        assert options["allowed_origins"] == ("https://" + url.split("/")[2],)
        if url == self.source.url:
            assert "Cookie" not in options["headers"]
            if self.fault == "player":
                return Response(url, b"<html>Unavailable</html>", "text/html")
            return Response(url, self.player, "text/html", set_cookie_headers=(
                "PHPSESSID=public-fixture-session; Path=/; Secure; HttpOnly",))
        assert "full=1&location_id=" in url and url.endswith("&action=get_transcriptions")
        assert "speaker=" not in url
        assert options["headers"]["Cookie"] == "PHPSESSID=public-fixture-session"
        assert options["headers"]["Referer"] == self.source.url
        if self.fault == "cancel":
            self.context.cancellation.set()
        if self.fault == "timeout":
            raise TimeoutError()
        raw = self.reply if self.fault != "oversize" else b" " * (options["byte_limit"] + 1)
        return Response(url + ("/other" if self.fault == "redirect" else ""), raw,
            "application/json" if self.fault == "mime" else "text/html", 403 if self.fault == "denied" else 200)


def setup(tmp_path):
    context = OperationContext()
    vendor = Vendor(context)
    engine = create_engine(storage=SQLiteStorage(tmp_path / "owner.sqlite"), provider_transport=vendor)
    return engine, context, vendor


@pytest.mark.parametrize("source,player,event", [
    (SOURCE, PLAYER, "74003"),
    (Source("town-hall-streams", "https://www.townhallstreams.com/stream.php?location_id=31&id=77576",
            input_format="town-hall-streams-event-html"),
     (FIXTURES / "location31-77576.html").read_bytes(), "77576"),
])
def test_actual_empty_responses_preserve_meeting_and_raw_empty_capture(tmp_path, source, player, event):
    context = OperationContext()
    vendor = Vendor(context, source=source, player=player)
    engine = create_engine(provider_transport=vendor)
    result = engine.fetch_captions(source, event, context=context)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["external_id"] == event
    assert record["normalized"]["transcript_availability"] == "supplied_full_response_empty"
    assert not record["text"] and "transcript_text" not in record["normalized"]
    capture, = result.data["captures"]
    assert capture["byte_length"] == 0 and base64.b64decode(capture["content_base64"]) == b""
    assert len(vendor.calls) == 2 and result.coverage["generation_requested"] is False
    assert "public-fixture-session" not in json.dumps(result.public_dict())
    exported = engine.execute("export", {"bundle": result.data, "format": "zip"})
    assert exported.status == "completed", exported.public_dict()
    restored = create_engine().execute("import_bundle", {"format": "zip"},
        content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    assert restored.data["bundle"] == result.data


def test_synthetic_display_text_search_import_retry_reopen_and_zip(tmp_path):
    engine, context, vendor = setup(tmp_path)
    # Vendor client injects HTML into its display; this nonempty reply is synthetic,
    # not a claimed nonempty live transcript or a vendor timing/speaker schema.
    vendor.reply = b'<div>Budget &amp; roads<br>Approved discussion</div><script>secret</script><p hidden>private</p>'
    result = engine.fetch_captions(SOURCE, "74003", context=context)
    assert result.status == "partial" and not result.errors, result.public_dict()
    bundle = result.data
    record = bundle["records"][0]
    assert record["normalized"]["transcript_text"] == "Budget & roads Approved discussion"
    segment, = record["text"]
    assert segment["citation_url"] == URL and segment["provenance"]["retrieval_url"] == TARGET
    assert not {"timestamp", "start", "end", "speaker", "language"}.intersection(segment)
    assert base64.b64decode(bundle["captures"][0]["content_base64"]) == vendor.reply
    for _ in range(2):
        imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=context)
        assert imported.status == "completed", imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "owner.sqlite"))
    found = reopened.execute("search", {"query": {"phrases": ["Approved discussion"]}}, context=context)
    assert len(found.data["hits"]) == 1
    exported = reopened.execute("export", {"bundle": bundle, "format": "zip"}, context=context)
    assert exported.status == "completed", exported.public_dict()
    restored = create_engine().execute("import_bundle", {"format": "zip"}, context=context,
        content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    assert restored.data["bundle"] == bundle


@pytest.mark.parametrize("fault", ["denied", "redirect", "mime", "timeout", "oversize"])
def test_transcript_failure_retains_meeting_with_explicit_failure(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.fault = fault
    result = engine.fetch_captions(SOURCE, "74003", context=context)
    assert result.status == "partial" and result.errors
    assert result.data["records"][0]["identity"]["external_id"] == "74003"
    assert not result.data["records"][0]["text"]
    assert result.coverage["failures"] and len(vendor.calls) == 2


@pytest.mark.parametrize("reply", [b"1", b"<html><body>Error</body></html>", b"<form>Sign in</form>"])
def test_unrecognized_document_or_sentinel_is_not_transcript_text(tmp_path, reply):
    engine, context, vendor = setup(tmp_path)
    vendor.reply = reply
    result = engine.fetch_captions(SOURCE, "74003", context=context)
    assert result.status == "partial" and result.errors
    assert not result.data["records"][0]["text"]
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == reply


@pytest.mark.parametrize("before", [True, False])
def test_cancel_has_no_successful_transcript_claim(tmp_path, before):
    engine, context, vendor = setup(tmp_path)
    if before:
        context.cancellation.set()
    else:
        vendor.fault = "cancel"
    result = engine.fetch_captions(SOURCE, "74003", context=context)
    assert result.status == "cancelled"
    assert len(vendor.calls) == (0 if before else 2)
    if result.data:
        from civic_data_connectors.engine import canonical_hash
        record = result.data["records"][0]
        assert record["normalized_sha256"] == canonical_hash(record["normalized"])


def test_changed_player_binding_stops_before_transcript_get(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.player = PLAYER.replace(b'full=1&location_id=72&id=74003', b'full=1&location_id=72&id=74004')
    result = engine.fetch_captions(SOURCE, "74003", context=context)
    assert result.status == "failed" and len(vendor.calls) == 1


@pytest.mark.parametrize("fault", ["identity", "language", "pages", "transfer", "namespace"])
def test_scope_or_bounds_cannot_be_bypassed(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    kwargs = {}
    event = "other" if fault == "identity" else "74003"
    if fault == "language":
        kwargs["language"] = "en"
    if fault == "pages":
        kwargs["bounds"] = Bounds(max_pages=1)
    if fault == "transfer":
        kwargs["bounds"] = Bounds(transfer_bytes=1)
    if fault == "namespace":
        context = OperationContext(allowed_namespaces=frozenset({"other"}))
    result = engine.fetch_captions(SOURCE, event, context=context, **kwargs)
    assert result.status in {"failed", "unsupported"}, result.public_dict()
    assert len(vendor.calls) <= (1 if fault == "transfer" else 0)
