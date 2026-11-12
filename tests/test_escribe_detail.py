import base64
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response

HTML = (Path(__file__).parent / "fixtures/escribe-agenda-minimized.html").read_bytes()
URL = "https://pub-oakville.escribemeetings.com/Meeting.aspx?Id=4162e72f-daa8-4252-bfd5-fd54f125ebe4&Agenda=Agenda&lang=English"
SOURCE = Source("escribe", URL, input_format="escribe-meeting-detail-html")


def test_saved_agenda_positions_are_not_native_ids_and_documents_keep_association():
    result = create_engine().normalize(SOURCE, HTML, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    meeting, first, second = result.data["records"]
    assert meeting["identity"]["external_id"] == "4162e72f-daa8-4252-bfd5-fd54f125ebe4"
    assert meeting["normalized"]["meeting_date"] == "2026-11-11"
    assert meeting["normalized"]["scheduled_at"] == "2026-11-11T19:00:00"
    assert meeting["normalized"]["time_zone_status"] == "unknown"
    assert meeting["normalized"]["location"] == "Virtual Meeting"
    assert first["normalized"]["agenda_number"] == "6."
    assert not first["normalized"]["documents"]
    assert second["normalized"]["agenda_number"] == "6.1"
    assert second["identity"]["derivation"] == "capture_local_display_position"
    assert second["normalized"]["native_item_id"] is None
    assert second["identity"]["parent"] == meeting["identity"]
    assert second["normalized"]["documents"][0]["external_id"] == "103635"
    assert base64.b64decode(result.data["capture"]["content_base64"]) == HTML
    changed = create_engine().normalize(SOURCE, HTML + b"<!-- changed capture -->", input_format=SOURCE.input_format)
    assert changed.data["records"][2]["identity"]["external_id"] != second["identity"]["external_id"]


def test_configured_detail_get_and_capture_verified_document_use_existing_engine():
    class Transport:
        def __init__(self):
            self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, HTML if url == URL else b"%PDF-1.7 synthetic", "text/html" if url == URL else "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.fetch(SOURCE)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record = result.data["records"][2]
    fetched = engine.fetch_attachment(SOURCE, record, capture=HTML)
    assert fetched.status == "completed", fetched.public_dict()
    assert len(transport.calls) == 2
    assert transport.calls[-1] == "https://pub-oakville.escribemeetings.com/filestream.ashx?DocumentId=103635"


@pytest.mark.parametrize("body", [HTML.replace(b"AgendaItem9", b"AgendaItem6"), b"<html>Shell only</html>"])
def test_ambiguous_positions_and_shell_do_not_claim_agenda_content(body):
    assert create_engine().normalize(SOURCE, body, input_format=SOURCE.input_format).status == "failed"


def test_foreign_document_is_not_mapped_or_fetched():
    body = HTML.replace(b"filestream.ashx?", b"https://other.example/filestream.ashx?")
    result = create_engine().normalize(SOURCE, body, input_format=SOURCE.input_format)
    assert result.status == "completed"
    assert not result.data["records"][2]["normalized"]["documents"]
