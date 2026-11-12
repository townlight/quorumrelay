from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response

SOURCE = Source(
    "digital-towpath", "https://digitaltowpath.digitaltowpath.net/government/meetings-and-minutes"
)
YEAR = "https://digitaltowpath.digitaltowpath.net/meetings/meetings/Town%20Board/2024"
ROOT = b"""<div class="dtp-meetings-list"><a title="Link to meeting details page" href="/meetings/detail/27">August 12, 2025: Regular Meeting</a>
<a title="Link to meeting details page" href="/meetings/july-special-meeting">July 8, 2025: Monthly Meeting</a></div>
<a class="dtp-meeting-year" href="https://digitaltowpath.digitaltowpath.net/meetings/meetings/Town Board/2024">2024</a>"""
OLDER = b'<div class="dtp-meetings-list"><a title="Link to meeting details page" href="/meetings/detail/14">December 10, 2024: December Meeting</a></div>'


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url in {SOURCE.url, YEAR}
        return Response(url, ROOT if url == SOURCE.url else OLDER, "text/html")


def test_towpath_listing_preserves_native_id_and_distinguishes_supplied_slug_identity():
    result = create_engine().execute("discover", {"source": SOURCE.public_dict()}, content=ROOT)
    records = result.data["records"]
    assert records[0]["identity"]["external_id"] == "27"
    assert records[0]["normalized"]["documents"] == []
    assert records[1]["identity"]["derivation"] == "supplied_detail_url"
    assert records[1]["identity"]["external_id"].endswith("/meetings/july-special-meeting")
    assert all(r["normalized"]["documents_availability"] == "detail_not_fetched" for r in records)


def test_towpath_published_other_year_resume_applies_dates_and_validates_root():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    bounds = {"max_pages": 1, "date_from": "2024-01-01", "date_to": "2024-12-31"}
    first = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": bounds})
    assert first.data["records"] == [] and first.coverage["checkpoint"]
    second = engine.execute(
        "discover",
        {
            "source": SOURCE.public_dict(),
            "bounds": {**bounds, "max_pages": 2, "checkpoint": first.coverage["checkpoint"]},
        },
    )
    assert [r["identity"]["external_id"] for r in second.data["records"]] == ["14"]
    assert second.status == "partial" and second.coverage["catalog_complete"] is False
    assert len(transport.calls) == 3


def test_towpath_empty_published_listing_is_not_an_invented_record():
    result = create_engine().execute(
        "discover",
        {"source": SOURCE.public_dict()},
        content=b'<div class="dtp-meetings-list">No meetings</div>',
    )
    assert result.status == "partial" and result.data["records"] == []


def test_towpath_single_numeric_detail_reuses_original_reader_and_preserves_id():
    detail=b'<h3 class="dtp-meeting-title">Regular Meeting</h3><time datetime="2025-08-12">August 12</time><a title="Download the minutes" href="/application/files/minutes.pdf">Minutes PDF</a>'
    class DetailTransport:
        def request(self,url,**kwargs):
            assert url=="https://digitaltowpath.digitaltowpath.net/meetings/detail/27"
            return Response(url,detail,"text/html")
    result=create_engine(provider_transport=DetailTransport()).fetch_record(SOURCE,"27")
    assert result.status=="partial" and result.data["records"][0]["identity"]["external_id"]=="27"
    assert result.data["records"][0]["normalized"]["documents"][0]["kind"]=="minutes"
