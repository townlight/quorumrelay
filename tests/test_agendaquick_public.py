import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.agendaquick import controls, listing_rows, search_rows

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = Source("destiny-agendaquick", "https://public.destinyhosted.com/agenda_publish.cfm?id=98622")


def test_actual_calendar_preserves_native_ids_supplied_documents_and_player():
    rows = listing_rows(SOURCE, (FIXTURES / "agendaquick-calendar.html").read_bytes())
    assert [row[0]["external_id"] for row in rows] == ["1737"]
    record = rows[0][0]
    assert record["meeting_date"] == "2026-11-02"
    assert record["documents"][0]["kind"] == "agenda"
    assert any(d["kind"] == "minutes" for d in record["documents"])
    assert record["recordings"][0]["url"] == "https://play.champds.com/yumacoaz/event/657"
    assert "body" not in record


def test_actual_item_search_retains_kind_unknown_parent_and_empty_results():
    rows = search_rows(SOURCE, (FIXTURES / "agendaquick-search.html").read_bytes())
    assert [row[0]["external_id"] for row in rows] == ["13632", "13638", "13971"]
    assert all(row[2] == "agenda_item" and "parent" not in row[0] for row in rows)
    assert "sstr=Council" in rows[2][0]["url"]
    assert "sstr=Council" not in rows[2][0]["description"]
    assert not rows[2][0]["description"].endswith("View Agenda Item")
    assert search_rows(SOURCE, (FIXTURES / "agendaquick-empty.html").read_bytes()) == []


class Transport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        query = parse_qs(urlsplit(url).query)
        assert query["id"] == ["98622"]
        month = query.get("get_month")
        assert month in (None, ["10"])
        name = "agendaquick-previous.html" if month else "agendaquick-calendar.html"
        return Response(url, (FIXTURES / name).read_bytes(), "text/html")


def test_calendar_resumes_only_current_advertised_month_and_filters_dates():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    bounds = {"date_from": "2026-10-01", "date_to": "2026-10-31", "max_pages": 1}
    first = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": bounds})
    assert first.data["records"] == [] and first.coverage["checkpoint"]
    second = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": {
        **bounds, "max_pages": 2, "checkpoint": first.coverage["checkpoint"]}})
    assert [r["identity"]["external_id"] for r in second.data["records"]] == ["1735", "1734"]
    assert second.status == "partial" and second.coverage["catalog_complete"] is False
    assert len(transport.calls) == 3


def test_forged_month_control_fails_before_request():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    bounds = {"date_from": "2026-10-01", "date_to": "2026-10-31", "max_pages": 1}
    first = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": bounds})
    state = json.loads(base64.urlsafe_b64decode(first.coverage["checkpoint"]))
    state["queue"][0]["fields"]["mt"] = "staff-only"
    token = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    result = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": {
        **bounds, "max_pages": 2, "checkpoint": token}})
    assert result.errors and len(transport.calls) == 2
    assert result.data["records"] == []


def test_calendar_controls_are_bounded_and_tenant_bound():
    values = controls((FIXTURES / "agendaquick-calendar.html").read_bytes())
    assert values and all(v["id"] == "98622" and v["term"] == "N" for v in values)
