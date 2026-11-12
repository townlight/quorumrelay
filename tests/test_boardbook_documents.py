import base64
import hashlib

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response

SOURCE = Source("boardbook", "https://meetings.boardbook.org/public/organization/1807")
AGENDA = "https://meetings.boardbook.org/Public/Agenda/1807?meeting=775433"
DOWNLOAD = AGENDA.replace("/Agenda/", "/DownloadAgenda/")
LISTING = b'<table><tr><td>November 10, 2026 at 5:30 PM - Regular Business Meeting</td><td><a href="/Public/Agenda/1807?meeting=775433">Agenda</a></td></tr></table>'
HTML = b'<a href="/Public/DownloadAgenda/1807?meeting=775433">Download</a>'
PDF = b"%PDF-1.7\n" + b"synthetic document bytes" * 200


class Transport:
    def __init__(self, page=HTML):
        self.calls, self.page = [], page

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == AGENDA:
            assert kwargs["byte_limit"] == 1024 and kwargs["allow_redirects"] is False
            return Response(url, self.page, "text/html")
        assert url == DOWNLOAD
        assert kwargs["byte_limit"] == 10000
        return Response(url, PDF, "application/pdf")


def fetch(transport, *, bounds=None):
    engine = create_engine(provider_transport=transport)
    result = engine.execute("discover", {"source": SOURCE.public_dict()}, content=LISTING)
    assert result.data["records"]
    return engine.fetch_attachment(SOURCE, result.data["records"][0], capture=LISTING,
        bounds=bounds or Bounds(parser_bytes=1024, transfer_bytes=10000))


def test_supplied_download_link_keeps_citation_and_separate_transfer_limit():
    transport = Transport()
    result = fetch(transport)
    assert result.status == "completed", result.public_dict()
    document = result.data["attachment"]
    assert document["citation_url"] == AGENDA
    assert base64.b64decode(document["content_base64"]) == PDF
    assert document["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert document["resolution"]["page_sha256"] == hashlib.sha256(HTML).hexdigest()
    assert len(PDF) > 1024 and len(transport.calls) == 2


def test_forged_ambiguous_missing_and_oversized_page_fail_without_downloading():
    for page in [b'<a href="https://other.example/Public/DownloadAgenda/1807?meeting=775433">Download</a>',
                 b'<a href="/Public/DownloadAgenda/1808?meeting=775433">Download</a>',
                 b'<a href="/Public/DownloadAgenda/1807?meeting=999">Download</a>',
                 b'<a href="/Public/DownloadAgenda/1807?meeting=775433#fragment">Download</a>',
                 b'<a href="/Public/DownloadAgenda/1807?meeting=775433&other=">Download</a>',
                 b'No download supplied', b'x' * 1025]:
        transport = Transport(page)
        result = fetch(transport)
        assert result.status == "partial" and result.data["record"]
        assert result.errors[0].code == "attachment_unavailable" and len(transport.calls) == 1


def test_invalid_pdf_response_is_reported_unavailable():
    class BadDownload(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            return Response(url, b"unavailable", "text/html", 403) if url == DOWNLOAD else response
    assert fetch(BadDownload()).status == "partial"
    class WrongBody(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            return Response(url, b"login page", "text/html", 200) if url == DOWNLOAD else response
    assert fetch(WrongBody()).status == "partial"
