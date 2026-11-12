"""Only a capture-bound public viewer's declared original-file download is followed."""

import base64
import hashlib
import json
from dataclasses import replace

import pytest

from quorumrelay import create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response

SLUG = "4870d6-board-of-trustees-regular-meeting"
SOURCE = {"provider": "boardable", "url": "https://site.boardable.com/test-org/meetings/" + SLUG,
          "input_format": "boardable-public-meeting-html",
          "options": {"download_origins": ["https://app.boardable.com"]}}
VIEW = "https://app.boardable.com/test-org/public-site-data/meetings/" + SLUG + "/documents/7af1d8f8/view"
PDF = b"%PDF-1.7\nsynthetic captured file\n%%EOF"


def detail(url=VIEW):
    table = [{"agendaListFormat": 6, "meeting": 1},
             {"slug": 2, "title": 3, "id": 4, "date": 5}, SLUG, "Test meeting", 463085,
             "Nov 10, 2026", "numbered"]
    return ('<script id="__NUXT_DATA__">' + json.dumps(table) + '</script><a href="' + url +
            '">Supporting policy.pdf</a>').encode()


def viewer(root=VIEW.removesuffix("/view"), upload_type="computer"):
    attachment = {"attachable_id": 463085, "attached_type": upload_type, "title": "Supporting policy.pdf"}
    literal = json.dumps(attachment).replace('"', r'\u0022')
    return ("return_url: '" + root.replace("/", "\\/") + "', attachment: JSON.parse('" + literal +
            "'), downloadUrl() { return this.return_url + '/download'; }").encode()


class Transport:
    def __init__(self, page=None, file=PDF):
        self.page, self.file, self.calls = page or viewer(), file, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        assert "https://app.boardable.com" in kwargs["allowed_origins"]
        if url == VIEW:
            return Response(url, self.page, "text/html")
        assert url == VIEW.removesuffix("/view") + "/download"
        return Response(url, self.file, "application/octet-stream")


def fetch(transport, *, source=SOURCE, capture=None, bounds=None):
    engine = create_engine(provider_transport=transport)
    capture = capture or detail()
    parsed = engine.execute("fetch", {"source": source}, content=capture)
    key = source_identity_key(parsed.data["records"][0]["identity"])
    return engine.execute("fetch", {"source": source, "attachment": {"record_key": key, "index": 0},
                                     "bounds": bounds or {}}, content=capture)


def test_viewer_resolution_keeps_exact_capture_and_original_file_hash():
    transport = Transport()
    result = fetch(transport)
    assert result.status == "completed", result.public_dict()
    attachment = result.data["attachment"]
    assert attachment["citation_url"] == VIEW
    assert attachment["sha256"] == hashlib.sha256(PDF).hexdigest()
    captured = attachment["resolution"]["viewer_capture"]
    assert base64.b64decode(captured["content_base64"]) == viewer()
    assert captured["sha256"] == hashlib.sha256(viewer()).hexdigest()
    assert transport.calls[-1][1]["byte_limit"] == 209715200 - len(viewer())


@pytest.mark.parametrize("page,file", [(viewer(root="https://app.boardable.com/other"), PDF),
                                       (viewer(upload_type="google"), PDF),
                                       (viewer(), b"<!doctype html><title>Login or viewer</title>")])
def test_changed_identity_or_non_file_retains_record_as_partial(page, file):
    result = fetch(Transport(page, file))
    assert result.status == "partial"
    assert result.data["record"]["identity"]["external_id"] == "463085"
    assert result.data["attachment"] is None
    assert result.errors[0].code == "attachment_unavailable"


def test_cross_meeting_and_transfer_or_parser_overflow_are_denied():
    transport = Transport()
    result = fetch(transport, capture=detail(VIEW.replace(SLUG, "other-meeting")))
    assert result.status in {"partial", "failed"} and not transport.calls
    result = fetch(Transport(), bounds={"transfer_bytes": len(viewer()) + len(PDF) - 1})
    assert result.status == "partial"
    result = fetch(Transport(page=viewer() + b" " * 1000), bounds={"parser_bytes": 700})
    assert result.status == "partial"


def test_viewer_redirect_is_not_followed():
    class Redirect(Transport):
        def request(self, url, **kwargs):
            return replace(super().request(url, **kwargs), status=302)

    result = fetch(Redirect())
    assert result.status == "partial"
