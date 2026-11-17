from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors import compat
from civic_data_connectors.providers.granicus import listing_rows


SOURCE = Source("peak", "https://douglascountynv.granicus.com/ViewPublisher.php?view_id=1")
VIEWER = "https://douglascountynv.granicus.com/AgendaViewer.php?view_id=1&clip_id=1897"
CAPTURE = b'''<table><tr><td headers="Name">Airport Advisory Committee</td>
<td headers="Date Airport-Advisory-Committee">October 6, 2026 - 4:00 PM</td>
<td><a href="//douglascountynv.granicus.com/AgendaViewer.php?view_id=1&amp;clip_id=1897">Agenda</a></td>
<td headers="VideoLink Airport-Advisory-Committee"><a href="javascript:void(0);"
onclick="window.open('//douglascountynv.granicus.com/MediaPlayer.php?view_id=1&amp;clip_id=1897','player')">Video</a></td>
</tr></table>'''


def test_actual_saved_peak_row_retains_unlabeled_supplied_agenda_and_legacy_output():
    capture = (Path(__file__).parent / "fixtures/baseline/peak.response").read_bytes()
    rows = listing_rows(SOURCE, capture)
    row, raw, _ = next(row for row in rows if row[0]["external_id"] == "1897")
    assert {"kind": "agenda", "url": VIEWER} in row["documents"]
    assert raw["unlabeled_viewer_links"] == [VIEWER.removeprefix("https:")]
    legacy = compat.ViewPublisherRows()
    legacy.feed(CAPTURE.decode())
    assert "agenda" not in legacy.rows[0]
    assert "unlabeled_viewer_links" not in legacy.rows[0]
    engine = create_engine()
    result = engine.execute("normalize", {"source": {
        **SOURCE.public_dict(), "input_format": "granicus-listing-html"}}, content=CAPTURE)
    assert result.status == "completed", result.public_dict()
    assert result.data["records"][0]["normalized"]["documents"] == [{"kind": "agenda", "url": VIEWER}]


def test_default_configured_peak_discovery_keeps_locator_without_claiming_file_bytes():
    class Transport:
        calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            assert url == SOURCE.url
            return Response(url, CAPTURE, "text/html")

    transport = Transport()
    result = create_engine(provider_transport=transport).execute("discover", {"source": SOURCE.public_dict()})
    assert result.status == "partial", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "1897"
    assert record["normalized"]["documents"] == [{"kind": "agenda", "url": VIEWER}]
    assert result.coverage["scope"] == "configured capture only; upstream catalog completeness is unverified"
    assert transport.calls == [SOURCE.url]


@pytest.mark.parametrize("replacement", [
    "https://other.granicus.com/AgendaViewer.php?view_id=1&clip_id=1897",
    VIEWER.replace("clip_id=1897", "clip_id=1898"),
    VIEWER.replace("view_id=1", "view_id=2"),
    VIEWER + "&clip_id=1897",
    VIEWER + "&token=untrusted",
    VIEWER + "#fragment",
    VIEWER.replace("https://", "https://user:secret@"),
])
def test_unlabeled_viewer_requires_exact_source_view_clip_and_no_extra_parameters(replacement):
    capture = CAPTURE.replace(VIEWER.removeprefix("https:").replace("&", "&amp;").encode(),
                              replacement.replace("&", "&amp;").encode(), 1)
    assert listing_rows(SOURCE, capture)[0][0]["documents"] == []


def test_unlabeled_viewer_without_same_row_player_is_not_associated():
    capture = CAPTURE.replace(b"MediaPlayer.php", b"OtherPlayer.php")
    assert listing_rows(SOURCE, capture)[0][0]["documents"] == []
