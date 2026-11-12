"""Synthetic CloudCast MRSS based on the vendor's feed contract and observed namespaces."""
import hashlib
import json
from pathlib import Path

import pytest

from civic_data_connectors import Engine, Source, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.telvue_mrss import FORMAT, listing_rows
from civic_data_connectors.providers import register
from civic_data_connectors.providers.account_api import is_account_api

URL = "https://connect.telvue.com/mrss/synthetic-player?recent=1"
XML = b'''<?xml version="1.0"?><rss version="2.0"
 xmlns:media="http://search.yahoo.com/mrss/"
 xmlns:cloudcast="http://cloudcast.telvue.com/mrss_cloudcast/">
 <channel><title>Synthetic meeting player</title><item>
 <title>Council recording</title>
 <link>https://videoplayer.telvue.com/player/synthetic-player/media/42</link>
 <pubDate>Thu, 12 Nov 2026 08:37:40 -0500</pubDate>
 <media:category>City Council</media:category><media:description>Supplied description</media:description>
 <media:group><media:content duration="2803" lang="en" type="application/vnd.apple.mpegurl"
 url="https://media.example.org/42/master.m3u8"/></media:group>
 <cloudcast:id>42</cloudcast:id><cloudcast:program>Council</cloudcast:program>
 <cloudcast:episode>Supplied episode</cloudcast:episode><cloudcast:summary>Summary</cloudcast:summary>
 <cloudcast:future-field>unknown preserved</cloudcast:future-field>
 </item></channel></rss>'''


def test_pinned_vendor_document_and_public_sample_are_independent_oracles():
    root = Path(__file__).parents[1]
    evidence = root / "docs/capabilities/evidence/telvue-cloudcast"
    manifest = json.loads((evidence / "source.json").read_bytes())
    documentation = (evidence / "cloudcast-mrss.html").read_bytes()
    assert hashlib.sha256(documentation).hexdigest() == manifest["sha256"]
    assert b"recent=10" in documentation and b"media:group" in documentation
    sample = manifest["public_sample"]
    raw = (root / sample["fixture"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == sample["sha256"]
    row, _, kind = listing_rows(Source("telvue", sample["url"]), raw)[0]
    assert kind == "recording" and row["external_id"] == "1068038"
    assert row["recordings"][0]["duration_seconds"] == 2803
    assert row["recordings"][0]["language"] == "en"
    assert "meeting_date" not in row


def test_vendor_feed_preserves_media_fields_without_inferred_meeting():
    row, raw, kind = listing_rows(Source("telvue", URL), XML)[0]
    assert kind == "recording" and row["external_id"] == "42"
    assert row["recordings"] == [{"url": "https://media.example.org/42/master.m3u8", "language": "en",
                                  "type": "application/vnd.apple.mpegurl", "duration_seconds": 2803}]
    assert row["published_at"] == "2026-11-12T08:37:40-05:00"
    assert "meeting_date" not in row and "body" not in row
    assert "unknown preserved" in raw["item_xml"]


@pytest.mark.parametrize("replacement", [
    (b"/media/42</link>", b"/media/43</link>"),
    (b"synthetic-player/media/42", b"other-player/media/42"),
    (b"https://media.example.org", b"https://127.0.0.1"),
    (b"https://media.example.org", b"http://media.example.org"),
    (b'duration="2803"', b'duration="-1"'),
])
def test_identity_and_unsafe_media_fail_closed(replacement):
    with pytest.raises(ValueError):
        listing_rows(Source("telvue", URL), XML.replace(*replacement))


def test_entity_and_source_bounds():
    with pytest.raises(ValueError):
        listing_rows(Source("telvue", URL), b'<!DOCTYPE rss [<!ENTITY x "bad">]>' + XML)
    with pytest.raises(ValueError):
        listing_rows(Source("telvue", URL + "&recent=2"), XML)
    with pytest.raises(ValueError):
        listing_rows(Source("telvue", URL.replace("connect.telvue.com", "other.example.org")), XML)
    assert listing_rows(Source("telvue", URL), b'<rss version="2.0"><channel/></rss>') == []


def test_public_feed_exemption_never_exempts_an_account_api_route():
    assert not is_account_api(Source("telvue", URL, input_format=FORMAT))
    assert is_account_api(Source("telvue", "https://connect.telvue.com/api/v2/media", input_format=FORMAT))
    assert is_account_api(Source("telvue", "https://connect.telvue.com/mrss/synthetic-player"))
    engine = create_engine()
    denied = engine.normalize(Source("telvue", "https://connect.telvue.com/api/v2/media", input_format=FORMAT),
                              XML, input_format=FORMAT)
    assert denied.status == "failed"


def test_registered_saved_and_synthetic_discovery_preserve_exact_capture():
    engine = create_engine()
    source = Source("telvue", URL, input_format=FORMAT)
    saved = engine.normalize(source, XML, input_format=FORMAT)
    assert saved.status == "completed", saved.public_dict()
    assert saved.data["capture"]["sha256"] == hashlib.sha256(XML).hexdigest()
    assert saved.data["records"][0]["identity"]["record_type"] == "recording"

    class Network:
        def request(self, url, **kwargs):
            assert url == URL and kwargs.get("method", "GET") == "GET"
            assert len(XML) <= kwargs["byte_limit"] and kwargs["deadline_seconds"] > 0
            return Response(url=url, content=XML, content_type="application/rss+xml", status=200)

    network_engine = Engine()
    register(network_engine, transport=Network())
    discovered = network_engine.execute("discover", {"source": source.public_dict(), "bounds": {"max_pages": 1}})
    assert discovered.status == "partial", discovered.public_dict()
    assert discovered.data["records"][0]["identity"] == saved.data["records"][0]["identity"]
    assert discovered.coverage["catalog_complete"] is False
