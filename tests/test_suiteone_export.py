"""Ordinary HTML document preparation, not timed Liberty bookmarks or remote writes."""

import base64
from dataclasses import replace
from hashlib import sha256
from html.parser import HTMLParser

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import open_artifact
from quorumrelay.storage import SQLiteStorage

SOURCE = {"provider": "suiteone-media", "url": "https://vermilionoh.suiteonemedia.com/"}


def request():
    return {
        "source": SOURCE,
        "provider_specific": True,
        "format": "suiteone-bookmark-document",
        "title": "Conseil é & <agenda>",
        "paragraphs": ["Call to order", "<script>alert(1)</script>\nBudget & votes"],
    }


class Text(HTMLParser):
    def __init__(self, payload):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(payload.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        assert not any(k.startswith("on") or k in {"src", "href"} for k, _ in attrs)

    def handle_data(self, text):
        self.text.append(text)


def test_plain_document_escapes_markup_and_discloses_manual_timing():
    r = create_engine().execute("export", request())
    assert r.status == "completed", r.public_dict()
    raw = base64.b64decode(r.data["content_base64"])
    parsed = Text(raw)
    assert "script" not in parsed.tags and "<script>alert(1)</script>" in "".join(parsed.text)
    assert "Conseil é & <agenda>" in "".join(parsed.text)
    assert b"<br>Budget &amp; votes" in raw
    m = r.data["manifest"]
    assert sha256(raw).hexdigest() == m["sha256"] and len(raw) == m["byte_length"]
    assert m["filename"] == "bookmark-document.html"
    assert not m["vendor_transfer_performed"] and not m["vendor_import_accepted"]
    assert not m["automatic_bookmarks_created"] and "timestamps" in m["projection_losses"][1]
    assert "manually" in m["projection_losses"][2] and "Replace Existing" in m["projection_losses"][3]


def test_scoped_artifact_survives_reopen_and_policy_revocation(tmp_path):
    path = tmp_path / "store.sqlite"
    store = SQLiteStorage(path)
    owner, ctx = create_engine(storage=store), OperationContext(tenant="a")
    req = {**request(), "stream": True}
    r = owner.execute("export", req, context=ctx)
    assert r.status == "completed", r.public_dict()
    reopened = create_engine(storage=SQLiteStorage(path))
    _, file = open_artifact(reopened, r.data["artifact_id"], context=ctx)
    with file:
        raw = file.read()
    assert sha256(raw).hexdigest() == r.data["manifest"]["sha256"]
    again = owner.execute("export", request(), context=ctx)
    assert base64.b64decode(again.data["content_base64"]) == raw
    with pytest.raises(ValueError):
        open_artifact(reopened, r.data["artifact_id"], context=replace(ctx, tenant="b"))
    with pytest.raises(ValueError):
        open_artifact(reopened, r.data["artifact_id"], context=replace(ctx, allowed_namespaces=frozenset()))
    assert (
        owner.execute("export", req, context=replace(ctx, allowed_namespaces=frozenset())).status == "failed"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "bytes",
        "escape_expansion",
        "empty",
        "nontext",
        "control",
        "stream",
        "date",
        "checkpoint",
        "format",
    ],
)
def test_invalid_or_lossy_requests_are_rejected_before_output(mutation):
    req = request()
    if mutation == "count":
        req["bounds"] = {"max_records": 1}
    elif mutation == "bytes":
        req["bounds"] = {"transfer_bytes": 10}
    elif mutation == "escape_expansion":
        req.update(title="a", paragraphs=["<" * 100], bounds={"parser_bytes": 300})
    elif mutation == "empty":
        req["paragraphs"] = ["   "]
    elif mutation == "nontext":
        req["paragraphs"] = [{"text": "not plain text"}]
    elif mutation == "control":
        req["paragraphs"] = ["x\x00y"]
    elif mutation == "stream":
        req["stream"] = "true"
    elif mutation == "date":
        req["bounds"] = {"date_from": "2026-11-14"}
    elif mutation == "checkpoint":
        req["bounds"] = {"checkpoint": "not resumable"}
    else:
        req["format"] = "liberty-exported-bookmarks"
    r = create_engine().execute("export", req)
    assert r.status == "failed" and not r.data, r.public_dict()


def test_cancellation_is_terminal_without_a_document():
    ctx = OperationContext()
    ctx.cancellation.set()
    r = create_engine().execute("export", request(), context=ctx)
    assert r.status == "cancelled" and not r.data
