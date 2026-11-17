"""Minimized transcription of captured public BoardBook agenda attributes."""

import base64
import re

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response

URL = "https://meetings.boardbook.org/Public/Agenda/1807?meeting=775433"
SOURCE = Source("boardbook", URL, input_format="boardbook-public-agenda-html")
HTML = b'''<h1 id="MeetingHeader">November 10, 2026 at 5:30 PM - Council</h1>
<table><tr class="agenda-item-information agenda-item-children-of-0" data-agendaitemid="10">
<td><div class="form-check">1) <strong>Reports</strong></div></td></tr>
<tr class="agenda-item-information agenda-item-children-of-10" data-agendaitemid="11">
<td><div class="form-check">1)a. Update</div><div class="Description">Supplied discussion</div>
<div data-loadurl="/hidden/must-not-run"><a data-foragendaitem="11" data-documentid="99"
href="/Documents/FileViewerOrPublic/1807?file=99">Supporting paper</a></div></td></tr></table>'''


def test_saved_native_item_parents_documents_and_exact_capture():
    result = create_engine().normalize(SOURCE, HTML, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    meeting, parent, child = result.data["records"]
    assert meeting["identity"]["external_id"] == "775433"
    assert meeting["normalized"]["scheduled_start"] == "2026-11-10T17:30:00"
    assert child["identity"]["external_id"] == "11"
    assert parent["identity"]["parent"] == meeting["identity"]
    assert child["identity"]["parent"] == parent["identity"]
    assert child["normalized"]["source_fields"]["Description"] == ["Supplied discussion"]
    assert child["text"][0]["text"] == "Supplied discussion"
    assert child["text"][0]["provenance"]["capture_sha256"] == result.data["capture"]["sha256"]
    assert parent["text"] == []
    assert child["normalized"]["documents"][0]["external_id"] == "99"
    assert child["original"]["attributes"]["data-agendaitemid"] == "11"
    assert base64.b64decode(result.data["capture"]["content_base64"]) == HTML


def test_configured_engine_read_and_supplied_document_transfer_only():
    class Transport:
        def __init__(self):
            self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            assert "/hidden/" not in url
            return Response(url, HTML if url == URL else b"%PDF-1.7 synthetic",
                            "text/html" if url == URL else "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.fetch(SOURCE)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.coverage["catalog_complete"] is False
    attachment = engine.fetch_attachment(SOURCE, result.data["records"][2], capture=HTML)
    assert attachment.status == "completed", attachment.public_dict()
    assert transport.calls == [URL, "https://meetings.boardbook.org/Documents/FileViewerOrPublic/1807?file=99"]


@pytest.mark.parametrize("body", [HTML.replace(b"children-of-10", b"children-of-11"),
                                 HTML.replace(b'data-agendaitemid="11"', b'data-agendaitemid="10"'),
                                 b"<html>Shell only</html>"])
def test_missing_duplicate_or_cyclic_native_structure_fails(body):
    assert create_engine().normalize(SOURCE, body, input_format=SOURCE.input_format).status == "failed"


def test_foreign_or_mismatched_document_is_not_associated():
    for body in (HTML.replace(b"/Documents/FileViewerOrPublic/1807", b"https://other.example/Documents/FileViewerOrPublic/1807"),
                 HTML.replace(b'data-foragendaitem="11"', b'data-foragendaitem="10"')):
        result = create_engine().normalize(SOURCE, body, input_format=SOURCE.input_format)
        assert result.status == "completed", result.public_dict()
        assert not result.data["records"][2]["normalized"]["documents"]


def test_native_parent_identity_does_not_depend_on_rendered_row_order():
    rows = re.findall(rb"<tr\b.*?</tr>", HTML, re.S)
    reordered = HTML[:HTML.index(b"<table>")] + b"<table>" + b"".join(reversed(rows)) + b"</table>"
    engine = create_engine()
    first = engine.normalize(SOURCE, HTML, input_format=SOURCE.input_format)
    second = engine.normalize(SOURCE, reordered, input_format=SOURCE.input_format)
    assert second.status == "completed", second.public_dict()
    def identities(result):
        return {r["identity"]["external_id"]: r["identity"] for r in result.data["records"]}

    assert identities(first) == identities(second)
