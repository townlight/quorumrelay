"""Explicit native chunk capture, without invented range units or file assembly."""
import base64
from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.contracts import Response
from test_escribe_publishing import SOURCE, response, sample

METHOD = "DocumentGetContentChunk"
REQUEST = {"api_method": METHOD, "api_parameters": {"Id": 23, "offset": 2, "length": 3}}


class Chunks:
    def __init__(self):
        self.metadata = sample("Document")
        self.chunk = b"supplied opaque chunk"
        self.calls, self.payloads = [], []
        self.after = lambda method: None
        self.invalid = False

    def request(self, url, **options):
        assert url == SOURCE.url and options["method"] == "POST"
        assert options["allow_redirects"] is False
        request = ET.fromstring(options["body"])
        node = request.find("{" + soap.SOAP + "}Body")[0]
        method = node.tag.split("}")[1]
        self.calls.append(method)
        relation = request.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
        if method == "DocumentGetById":
            assert [(n.tag.split("}")[1], n.text) for n in node] == [("Id", "23")]
            value = self.metadata
        else:
            assert method == METHOD
            assert [(n.tag.split("}")[1], n.text) for n in node] == [("Id", "23"), ("offset", "2"), ("length", "3")]
            value = "bad base64!" if self.invalid else base64.b64encode(self.chunk).decode()
        payload = response(method, value, relation=relation)
        self.payloads.append(payload)
        self.after(method)
        return Response(url, payload, "application/soap+xml")


@pytest.mark.parametrize("content", [b"supplied opaque chunk", b""])
def test_explicit_native_chunk_preserves_metadata_context_bytes_retry_search_and_exports(tmp_path, content):
    server = Chunks()
    server.chunk = content
    path = tmp_path / "chunk.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=server)
    result = engine.fetch(SOURCE, REQUEST)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert server.calls == ["DocumentGetById", METHOD]
    record, = result.data["records"]
    assert record["original"] == server.metadata and record["identity"]["external_id"] == "23"
    assert record["normalized"]["supplied_chunk_sha256"] == sha256(content).hexdigest()
    assert record["normalized"]["supplied_chunk_byte_length"] == len(content)
    assert record["normalized"]["native_chunk_parameters"] == REQUEST["api_parameters"]
    assert record["normalized"]["chunk_units"] == "not_established_by_pinned_schema"
    assert record["normalized"]["chunk_assembly"] == "not_performed"
    assert record["normalized"]["document_complete"] is False
    assert "supplied_document_sha256" not in record["normalized"]
    assert result.coverage["document_complete"] is False and result.coverage["source_complete"] is False
    assert result.coverage["chunk_byte_length"] == len(content) and result.coverage["pages"] == 2
    assert result.data["extensions"]["native_request_context"] == REQUEST
    assert base64.b64decode(result.data["capture"]["content_base64"]) == server.payloads[0]
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == server.payloads[1]
    assert base64.b64decode(result.data["captures"][1]["content_base64"]) == content
    relation = record["relationships"][-1]
    assert relation["relation"] == "document_content_chunk"
    assert relation["value"]["native_document_id"] == 23
    assert relation["value"]["binding"] == "explicit_request_context_not_response_echo"
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(path))
    assert len(reopened.execute("search", {"query": {"phrases": ["Agenda"]}}).data["hits"]) == 1
    durable = reopened.storage.get("bundles", canonical_hash(result.data), scope=OperationContext().scope).value
    assert durable == result.data
    for capture in [durable["capture"], *durable["captures"]]:
        assert reopened.storage.get("captures", capture["sha256"], scope=OperationContext().scope).value == capture
    for format in ("json", "jsonl", "zip"):
        exported = reopened.execute("export", {"bundle": durable, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data
    with pytest.raises(ValueError, match="standalone"):
        soap.parse_bundle(SOURCE, "synthetic", server.payloads[1])


@pytest.mark.parametrize("field,value", [
    ("Id", 0), ("Id", True), ("offset", -1), ("offset", True), ("offset", 2 ** 31),
    ("length", 0), ("length", -1), ("length", "3"), ("length", 2 ** 31),
])
def test_native_chunk_parameters_fail_before_any_network(field, value):
    request, server = deepcopy(REQUEST), Chunks()
    request["api_parameters"][field] = value
    result = create_engine(provider_transport=server).fetch(SOURCE, request)
    assert result.status == "failed" and result.errors and not server.calls


@pytest.mark.parametrize("case", ["missing", "extra", "pages", "wrong_document", "invalid", "transfer"])
def test_metadata_content_and_bounds_fail_without_claiming_a_file(case):
    request, server, bounds = deepcopy(REQUEST), Chunks(), Bounds()
    if case == "missing":
        request["api_parameters"].pop("length")
    elif case == "extra":
        request["api_parameters"]["assemble"] = True
    elif case == "pages":
        bounds = Bounds(max_pages=1)
    elif case == "wrong_document":
        server.metadata["Id"] = 24
    elif case == "invalid":
        server.invalid = True
    else:
        server.chunk = b"x" * 8000
        bounds = Bounds(transfer_bytes=7000, parser_bytes=7000)
    result = create_engine(provider_transport=server).fetch(SOURCE, request, bounds=bounds)
    if case in {"invalid", "transfer"}:
        assert result.status == "partial" and result.errors
        assert result.data["records"][0]["original"] == server.metadata
        assert "supplied_chunk_sha256" not in result.data["records"][0]["normalized"]
        assert server.calls == ["DocumentGetById", METHOD]
    else:
        assert result.status == "failed" and result.errors and result.data is None
        assert server.calls == (["DocumentGetById"] if case == "wrong_document" else [])


@pytest.mark.parametrize("stage", ["DocumentGetById", METHOD, "mapping"])
@pytest.mark.parametrize("interrupt", ["cancel", "deadline"])
def test_chunk_interruption_cannot_report_completed_content(monkeypatch, stage, interrupt):
    server, context = Chunks(), OperationContext()
    clock = [0.0]
    monkeypatch.setattr(soap, "monotonic", lambda: clock[0])

    def stop():
        if interrupt == "cancel":
            context.cancellation.set()
        else:
            clock[0] = 2.0

    if stage == "mapping":
        original = soap.make_bundle

        def mapped(*args, **kwargs):
            bundle = original(*args, **kwargs)
            if args[3] == "escribe-native-document-chunk":
                stop()
            return bundle

        monkeypatch.setattr(soap, "make_bundle", mapped)
    else:
        server.after = lambda method: stop() if method == stage else None
    result = create_engine(provider_transport=server).fetch(SOURCE, REQUEST, context=context,
        bounds=Bounds(deadline_seconds=1))
    assert result.status == ("cancelled" if interrupt == "cancel" else "partial" if stage != "DocumentGetById" else "failed")
    assert not result.coverage.get("document_complete", False)
    assert server.calls == (["DocumentGetById"] if stage == "DocumentGetById" else ["DocumentGetById", METHOD])
