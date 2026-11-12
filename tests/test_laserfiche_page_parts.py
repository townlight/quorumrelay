"""Independent vendor SDK contracts for paired page streams and JSON finalization."""
import base64
import hashlib
import json
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs

import pytest

from test_write_providers import DocumentedNetwork, make_engine, response, run
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors import Bounds, Source
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.write_adapters import WriteAdapter
from civic_data_connectors.writes import WriteChange


EVIDENCE = Path(__file__).parents[1] / "docs/capabilities/evidence/laserfiche-repository"


def test_pinned_vendor_sdk_wire_contracts():
    raw = (EVIDENCE / "index.ts").read_bytes()
    manifest = json.loads((EVIDENCE / "source.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]
    source = raw.decode("utf-8").split("export class EntriesClient", 1)[1]
    finalize = source.split("    startImportUploadedParts(args:", 1)[1].split(
        "    protected processStartImportUploadedParts", 1)[0]
    assert 'const content_ = JSON.stringify(request);' in finalize
    assert '"Content-Type": "application/json"' in finalize
    assert '/Folder/ImportUploadedParts' in finalize
    pages = source.split("    createPages(args:", 1)[1].split("    protected processCreatePages", 1)[0]
    assert 'const content_ = new FormData();' in pages
    assert 'content_.append("request", JSON.stringify(request))' in pages
    assert 'content_.append("imageFiles", item_.data' in pages
    assert 'pageNumber=' in pages
    assert "The number of pages created is max(imageFiles.Count, textPages.Count)" in raw.decode("utf-8")


class PairedPages(DocumentedNetwork):
    def __init__(self, *, incomplete=False, wrong_pair=False):
        super().__init__("laserfiche")
        self.streams = [{"text": "prior", "image": b"prior-image"}]
        self.rows["1"] = {"id": 1, "name": "minutes", "pageCount": 1}
        self.incomplete, self.wrong_pair = incomplete, wrong_pair

    def laserfiche(self, parsed, method, fields, files):
        path = parsed.path
        if path.endswith("/Document/Pages"):
            if method == "GET":
                value = [{"pageNumber": i, "hasImage": p["image"] is not None,
                          "hasText": p["text"] is not None} for i, p in enumerate(self.streams, 1)]
                return response({"value": value, **({"@odata.nextLink": "unread-page"}
                                                    if self.incomplete else {})})
            assert method in {"POST", "PUT"}
            assert all(p["part"] == "imageFiles" for p in files)
            texts = fields.get("textPages", [])
            new = [{"text": texts[i] if i < len(texts) else None,
                    "image": files[i]["content"] if i < len(files) else None}
                   for i in range(max(len(texts), len(files)))]
            if self.wrong_pair:
                new.reverse()
            if method == "PUT":
                self.streams = new
            else:
                offset = int(parse_qs(parsed.query).get("pageNumber", [len(self.streams) + 1])[0]) - 1
                self.streams[offset:offset] = new
            self.rows["1"]["pageCount"] = len(self.streams)
            return response(self.rows["1"])
        if "/Document/Pages/" in path:
            number, part = path.split("/Document/Pages/")[1].split("/")
            value = self.streams[int(number) - 1]
            if part == "Text":
                assert value["text"] is not None, "Absent text must not be read"
                return response({"text": value["text"]})
            assert value["image"] is not None, "Absent image must not be read"
            return WriteResponse(200, value["image"])
        return super().laserfiche(parsed, method, fields, files)


@pytest.mark.parametrize("texts,images,position", [
    (["paired", "text-only"], [b"image-one"], None),
    (["paired"], [b"image-one", b"image-only"], 1),
    ([], [b"image-only"], 2),
])
def test_actual_coordinator_retains_index_pairing_and_unmatched_parts(tmp_path, texts, images, position):
    network = PairedPages()
    engine, context, _, source = make_engine(tmp_path, "laserfiche", ["document_pages:create"], network)
    result, approval = run(engine, context, source, {
        "key": "paired", "entity": "document_pages", "operation": "create", "resource_id": 1,
        "meeting_id": "meeting1", "page_number": position, "fields": {"textPages": texts},
        "files": [{"part": "imageFiles", "filename": f"page-{i}.png", "content_type": "image/png",
                   "content_base64": base64.b64encode(image).decode()} for i, image in enumerate(images)]})
    assert result.status == "completed", result.public_dict()
    before = list(network.streams)
    replay = engine.execute("commit_write", approval, context=context)
    assert replay.status == "completed" and network.streams == before
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_incomplete_page_metadata_fails_before_mutation(tmp_path):
    network = PairedPages(incomplete=True)
    engine, context, _, source = make_engine(tmp_path, "laserfiche", ["document_pages:create"], network)
    result = engine.execute("plan_write", {"source": source, "changes": [{
        "key": "paired", "entity": "document_pages", "operation": "create", "resource_id": 1,
        "meeting_id": "meeting1", "fields": {"textPages": ["new"]}, "files": [{
            "part": "imageFiles", "filename": "page.png", "content_type": "image/png",
            "content_base64": base64.b64encode(b"image").decode()}]}]}, context=context)
    assert result.status != "completed"
    assert not any(method != "GET" for method, _ in network.calls)


def test_mispaired_readback_is_not_success(tmp_path):
    network = PairedPages(wrong_pair=True)
    engine, context, _, source = make_engine(tmp_path, "laserfiche", ["document_pages:create"], network)
    result, _ = run(engine, context, source, {
        "key": "paired", "entity": "document_pages", "operation": "create", "resource_id": 1,
        "meeting_id": "meeting1", "fields": {"textPages": ["one", "two"]}})
    assert result.status != "completed"


def test_prior_text_only_prepared_shape_still_applies(tmp_path):
    network = DocumentedNetwork("laserfiche")
    network.rows["1"] = {"id": 1, "name": "minutes", "pageCount": 1}
    network.pages["1"] = ["prior"]
    _, context, _, source = make_engine(tmp_path, "laserfiche", ["document_pages:create"], network)
    source = Source(**source)
    change = WriteChange.from_dict({"key": "old", "entity": "document_pages", "operation": "create",
        "resource_id": 1, "meeting_id": "meeting1", "fields": {"textPages": ["new"]}})
    adapter, bounds, deadline = WriteAdapter(source.provider, network), Bounds(), monotonic() + 30
    prepared = adapter.prepare(source, change, context, bounds, deadline)
    prepared.pop("page_parts_contract")
    prepared["before"] = adapter.read_before(source, change, prepared["read_url"], context, bounds,
                                             deadline, page_parts=False)
    prepared["before_fingerprint"] = canonical_hash(prepared["before"])
    result = adapter.apply(source, prepared, context, bounds, deadline)
    assert result["state"] == "succeeded"
    assert network.pages["1"] == ["prior", "new"]
