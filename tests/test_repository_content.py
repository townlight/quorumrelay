"""Documented single-use Repository export through scoped attachment retrieval."""

import base64
import hashlib
import json
from dataclasses import replace

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.providers.contracts import Response
from test_repository_discovery import BASE, context, entry
from test_repository_fetch import ENTRY_URL

DOWNLOAD = "https://files.example.org/once?signature=private-download"
PDF = b"%PDF-1.7\nsynthetic supplied document\n"


class ExportTransport:
    def __init__(self, *, value=None, signed=DOWNLOAD, status=200, payload=PDF):
        self.value = value or entry(71)
        self.signed, self.status, self.payload, self.calls = signed, status, payload, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        if url == ENTRY_URL:
            assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
            return Response(url, json.dumps(self.value).encode(), "application/json")
        if url == ENTRY_URL + "/Export":
            assert kwargs["method"] == "POST"
            assert json.loads(kwargs["body"]) == {"part": "Edoc"}
            assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
            return Response(url, json.dumps({"value": self.signed}).encode(), "application/json", self.status)
        assert url == DOWNLOAD
        assert kwargs.get("headers", {}) == {}
        assert kwargs["allowed_origins"] == ("https://api.laserfiche.com", "https://files.example.org")
        return Response(url, self.payload, "application/pdf", self.status)


def fetch(transport, *, origins=None, bounds=None, caller=None, kind="Document"):
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json",
                    options={"download_origins": ["https://files.example.org"] if origins is None else origins})
    owner = create_engine(provider_transport=transport)
    capture = json.dumps(entry(71, kind=kind)).encode()
    row = owner.normalize(source, capture, input_format=source.input_format).data["records"][0]
    return owner.fetch_attachment(source, row, capture=capture, bounds=bounds, context=caller or context())


def test_repository_document_export_download_keeps_citation_and_hides_transfer_secret():
    transport = ExportTransport()
    result = fetch(transport)
    assert result.status == "completed", result.public_dict()
    attachment = result.data["attachment"]
    assert base64.b64decode(attachment["content_base64"]) == PDF
    assert attachment["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert attachment["citation_url"] == ENTRY_URL
    assert attachment["text_availability"] == "not_extracted"
    assert [call[0] for call in transport.calls] == [ENTRY_URL, ENTRY_URL + "/Export", DOWNLOAD]
    serialized = json.dumps(result.public_dict())
    assert "private-download" not in serialized and "secret-read-token" not in serialized


@pytest.mark.parametrize("transport,origins,bounds", [
    (ExportTransport(value=entry(71, parent=55)), None, None),
    (ExportTransport(value=entry(71, kind="Folder")), None, None),
    (ExportTransport(), [], None),
    (ExportTransport(signed="http://files.example.org/no-tls"), None, None),
    (ExportTransport(signed="https://files.example.org@evil.example.org/file"), None, None),
    (ExportTransport(status=403), None, None),
    (ExportTransport(payload=b"not a pdf"), None, None),
    (ExportTransport(), None, Bounds(transfer_bytes=1)),
])
def test_repository_export_failure_retains_record_without_signed_url(transport, origins, bounds):
    result = fetch(transport, origins=origins, bounds=bounds)
    assert result.status == "partial", result.public_dict()
    assert result.data["record"]["identity"]["external_id"] == "71"
    assert result.data["attachment"] is None
    assert "private-download" not in json.dumps(result.public_dict())
    assert sum(url == DOWNLOAD for url, _ in transport.calls) <= 1


def test_repository_export_cancellation_and_non_document_do_not_export():
    caller = context()
    caller.cancellation.set()
    transport = ExportTransport()
    assert fetch(transport, caller=caller).status == "cancelled"
    assert not transport.calls
    assert fetch(transport, kind="Folder").status == "failed"
    assert not transport.calls


@pytest.mark.parametrize("caller", [OperationContext(), context(allowed_namespaces=frozenset()),
                                    context(allowed_operations=frozenset({"discover"}))])
def test_repository_content_requires_caller_grants_and_token(caller):
    transport = ExportTransport()
    result = fetch(transport, caller=caller)
    assert result.status in {"failed", "partial"}
    assert not transport.calls


def test_repository_document_storage_reopen_and_retry_obtains_new_export(tmp_path):
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json",
                    options={"download_origins": ["https://files.example.org"]})
    database = tmp_path / "records.sqlite"
    owner = create_engine(storage=SQLiteStorage(database))
    capture = json.dumps(entry(71)).encode()
    normalized = owner.normalize(source, capture, input_format=source.input_format)
    imported = owner.execute("import_bundle", {"result": normalized.public_dict(), "persist": True}, context=context())
    assert imported.status == "completed", imported.public_dict()
    transport = ExportTransport()
    reopened = create_engine(storage=SQLiteStorage(database), provider_transport=transport)
    row = normalized.data["records"][0]
    for _ in range(2):
        result = reopened.fetch_attachment(source, row, context=context())
        assert result.status == "completed", result.public_dict()
    assert [url for url, _ in transport.calls] == [ENTRY_URL, ENTRY_URL + "/Export", DOWNLOAD] * 2


@pytest.mark.parametrize("stage", ["export_redirect", "download_redirect", "cancel_export", "cancel_download"])
def test_repository_export_redirects_and_mid_operation_cancellation(stage):
    caller = context()

    class Interrupted(ExportTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if url.endswith("/Export"):
                if stage == "export_redirect":
                    return replace(response, url=ENTRY_URL + "/different")
                if stage == "cancel_export":
                    caller.cancellation.set()
            if url == DOWNLOAD:
                if stage == "download_redirect":
                    return replace(response, url="https://elsewhere.example.org/file")
                if stage == "cancel_download":
                    caller.cancellation.set()
            return response

    transport = Interrupted()
    result = fetch(transport, caller=caller)
    assert result.status == ("cancelled" if stage.startswith("cancel") else "partial")
    assert result.data["attachment"] is None
    if stage in {"export_redirect", "cancel_export"}:
        assert not any(url == DOWNLOAD for url, _ in transport.calls)
