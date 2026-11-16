"""Original past-date responses exercise the existing bounded archive readers."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response
from test_civicweb_listing import Transport, discover, ids

FIXTURES = Path(__file__).parent / "fixtures" / "task6-archives"


def test_onbase_past_quarter_uses_observed_date_search_and_preserves_twelve_meetings():
    content = (FIXTURES / "onbase-akron-2025-q1.html").read_bytes()
    source = Source("onbase", "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/")

    class ArchivedWindow:
        def request(self, url, **kwargs):
            assert urlsplit(url).path == "/OnBaseAgendaOnline/Meetings/Search"
            assert parse_qs(urlsplit(url).query) == {
                "dropid": ["11"], "dropsv": ["01/01/2025"], "dropev": ["03/31/2025"]}
            return Response(url, content, "text/html")

    result = create_engine(provider_transport=ArchivedWindow()).discover(source,
        bounds=Bounds(date_from="2025-01-01", date_to="2025-03-31", max_pages=1))
    assert not result.errors
    assert len(result.data["records"]) == 12
    assert {r["normalized"]["meeting_date"][:4] for r in result.data["records"]} == {"2025"}
    assert len({r["identity"]["external_id"] for r in result.data["records"]}) == 12
    assert all(r["identity"]["external_id"] == str(r["original"]["ID"])
               for r in result.data["records"])
    assert result.coverage["catalog_complete"] is False


def test_civicweb_past_quarter_resumes_without_losing_or_duplicating_published_meetings():
    content = (FIXTURES / "civicweb-loveland-2025-q1.json").read_bytes()
    checkpoint, collected = None, []
    for _ in range(5):
        result, _ = discover(Transport(meetings=content), date_from="2025-01-01",
            date_to="2025-03-31", max_records=20, checkpoint=checkpoint)
        assert not result.errors
        assert len(result.data["records"]) <= 20
        assert all("2025-01-01" <= r["normalized"]["meeting_date"] <= "2025-03-31"
                   for r in result.data["records"])
        collected.extend(ids(result))
        checkpoint = result.coverage["checkpoint"]
        if checkpoint is None:
            break
    assert checkpoint is None
    assert len(collected) == len(set(collected)) == 89
    assert result.coverage["catalog_complete"] is False
