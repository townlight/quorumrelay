"""Documented read export variants reuse the same private, bounded transfer."""

import base64
import json
from dataclasses import replace

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from test_repository_content import DOWNLOAD, PDF, ExportTransport
from test_repository_discovery import BASE, context, entry
from test_repository_fetch import ENTRY_URL


@pytest.mark.parametrize("options,expected", [
    ({"repository_export_part": "Text"}, {"part": "Text", "textOptions": {"includeRedactions": True}}),
    ({"repository_export_part": "Image"}, {"part": "Image", "imageOptions": {
        "format": "PDF", "includeRedactions": True, "includeAnnotations": True}}),
    *[({"repository_export_part": "Image", "repository_image_format": image_format},
       {"part": "Image", "imageOptions": {"format": image_format, "includeRedactions": True,
           "includeAnnotations": True, **({"encoding": "AsStored"} if "TIFF" in image_format else {})}})
      for image_format in ["MultiPageTIFF", "SinglePageTIFF", "PNG", "JPEG"]],
    ({"repository_export_part": "AlternateEdoc", "repository_alternate_edoc_name": "Accessible_1"},
     {"part": "AlternateEdoc", "alternateEdocName": "Accessible_1"}),
])
def test_repository_export_documented_variant_fields_and_private_download(options, expected):
    image_format = expected.get("imageOptions", {}).get("format")
    payload = {"PDF": PDF, "MultiPageTIFF": b"II*\x00synthetic TIFF", "SinglePageTIFF": b"PK\x03\x04synthetic archive",
               "PNG": b"\x89PNG\r\n\x1a\nsynthetic PNG", "JPEG": b"\xff\xd8\xffsynthetic JPEG"}.get(image_format, PDF)
    if expected["part"] == "Text":
        payload = b"Existing redacted supplied text."

    class VariantTransport(ExportTransport):
        def request(self, url, **kwargs):
            if url == ENTRY_URL + "/Export":
                self.calls.append((url, kwargs))
                assert kwargs["method"] == "POST" and json.loads(kwargs["body"]) == expected
                assert kwargs["headers"]["Authorization"] == "Bearer secret-read-token"
                assert kwargs["allow_redirects"] is False
                return Response(url, json.dumps({"value": DOWNLOAD}).encode(), "application/json")
            response = super().request(url, **kwargs)
            if url == DOWNLOAD:
                return replace(response, content=payload, content_type="application/octet-stream")
            return response

    transport = VariantTransport()
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json",
                    options={**options, "download_origins": ["https://files.example.org"]})
    owner = create_engine(provider_transport=transport)
    capture = json.dumps(entry(71)).encode()
    row = owner.normalize(source, capture, input_format=source.input_format).data["records"][0]
    result = owner.fetch_attachment(source, row, capture=capture, context=context())
    assert result.status == "completed", result.public_dict()
    assert base64.b64decode(result.data["attachment"]["content_base64"]) == payload
    assert result.data["attachment"]["export_part"] == expected["part"]
    assert result.data["attachment"]["export_options"] == {k: v for k, v in expected.items() if k != "part"}
    assert result.data["attachment"]["citation_url"] == ENTRY_URL
    assert len(transport.calls) == 3


@pytest.mark.parametrize("options", [
    {"repository_export_part": "GenerateText"},
    {"repository_export_part": []},
    {"repository_export_part": "Image", "repository_image_format": "EXE"},
    {"repository_image_format": "PDF"},
    {"repository_export_part": "AlternateEdoc"},
    {"repository_export_part": "AlternateEdoc", "repository_alternate_edoc_name": "../private"},
    {"repository_export_part": "AlternateEdoc", "repository_alternate_edoc_name": "x" * 16},
    {"repository_alternate_edoc_name": "Accessible"},
])
def test_repository_export_invalid_variant_configuration_fails_without_network(options):
    transport = ExportTransport()
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json", options=options)
    owner = create_engine(provider_transport=transport)
    capture = json.dumps(entry(71)).encode()
    row = owner.normalize(source, capture, input_format=source.input_format).data["records"][0]
    result = owner.fetch_attachment(source, row, capture=capture, context=context())
    assert result.status == "failed" and not transport.calls


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "MultiPageTIFF", "SinglePageTIFF"])
def test_repository_image_export_rejects_another_file_representation(image_format):
    class WrongImage(ExportTransport):
        def request(self, url, **kwargs):
            if url.endswith("/Export"):
                self.calls.append((url, kwargs))
                return Response(url, json.dumps({"value": DOWNLOAD}).encode(), "application/json")
            return super().request(url, **kwargs)  # PDF bytes, not the requested image representation.

    transport = WrongImage()
    source = Source("laserfiche-weblink", BASE, input_format="laserfiche-repository-entries-json", options={
        "download_origins": ["https://files.example.org"], "repository_export_part": "Image",
        "repository_image_format": image_format})
    owner = create_engine(provider_transport=transport)
    capture = json.dumps(entry(71)).encode()
    row = owner.normalize(source, capture, input_format=source.input_format).data["records"][0]
    result = owner.fetch_attachment(source, row, capture=capture, context=context())
    assert result.status == "partial" and result.data["attachment"] is None
    assert result.data["record"]["identity"] == row["identity"]
