"""A supplied asset cannot complete after cancellation or its total deadline."""
import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from civic_data_connectors.providers import retrieval
from civic_data_connectors.providers.contracts import Response
from test_recording_retrieval import CAPTURE, MEDIA, SOURCE, VIDEO


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
@pytest.mark.parametrize("kind", ["documents", "recordings"])
def test_generic_asset_response_obeys_end_to_end_bounds(monkeypatch, boundary, kind):
    clock = [0.0]
    caller = OperationContext()
    calls = []
    capture = CAPTURE.replace(b'</tr>', b'<td headers="AgendaLink"><a href="AgendaViewer.php?view_id=2&amp;clip_id=100">Agenda</a></td></tr>')

    class Transport:
        def request(self, url, **options):
            calls.append((url, options))
            if boundary == "cancel":
                caller.cancellation.set()
            else:
                clock[0] = 2.0
            return Response(url, MEDIA if kind == "recordings" else b"%PDF-1.7\nsynthetic",
                            "video/mp4" if kind == "recordings" else "application/pdf")

    monkeypatch.setattr(retrieval, "monotonic", lambda: clock[0])
    engine = create_engine(provider_transport=Transport())
    record, = engine.normalize(SOURCE, capture, input_format=SOURCE.input_format).data["records"]
    result = engine.fetch_attachment(SOURCE, record, capture=capture, kind=kind,
        url_field="video_url" if kind == "recordings" else "url",
        bounds=Bounds(deadline_seconds=1), context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "partial"), result.public_dict()
    assert result.data["record"]["identity"] == record["identity"]
    assert result.data.get("attachment") is None
    assert len(calls) == 1
    if kind == "recordings":
        assert calls[0][0] == VIDEO
    if boundary == "deadline":
        assert result.errors[0].code == "attachment_unavailable"


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_final_wrapper_resolution_is_inside_attachment_deadline(monkeypatch, boundary):
    from civic_data_connectors.providers import onbase_documents
    from test_onbase_documents import CITATION, HTML, PDF, SOURCE as ONBASE, WRAPPER

    clock = [0.0]
    caller = OperationContext()

    class Transport:
        def request(self, url, **options):
            assert url == CITATION
            return Response(url, WRAPPER, "text/html")

    def resolve(*args, **kwargs):
        if boundary == "cancel":
            caller.cancellation.set()
        else:
            clock[0] = 2.0
        return Response(CITATION, PDF, "application/pdf"), {"requests": 1}

    monkeypatch.setattr(onbase_documents, "resolve_document", resolve)
    monkeypatch.setattr(retrieval, "monotonic", lambda: clock[0])
    engine = create_engine(provider_transport=Transport())
    record = engine.execute("discover", {"source": ONBASE.public_dict()}, content=HTML).data["records"][0]
    result = engine.fetch_attachment(ONBASE, record, capture=HTML,
        bounds=Bounds(deadline_seconds=1), context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "partial"), result.public_dict()
    assert result.data["record"]["identity"] == record["identity"]
    assert result.data.get("attachment") is None


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
@pytest.mark.parametrize("kind", ["documents", "recordings"])
def test_attachment_encoding_is_inside_completion_bounds(monkeypatch, boundary, kind):
    clock = [0.0]
    caller = OperationContext()
    capture = CAPTURE.replace(b'</tr>', b'<td headers="AgendaLink"><a href="AgendaViewer.php?view_id=2&amp;clip_id=100">Agenda</a></td></tr>')

    class Transport:
        def request(self, url, **options):
            return Response(url, MEDIA if kind == "recordings" else b"%PDF-1.7\nsynthetic",
                            "video/mp4" if kind == "recordings" else "application/pdf")

    monkeypatch.setattr(retrieval, "monotonic", lambda: clock[0])
    engine = create_engine(provider_transport=Transport())
    record, = engine.normalize(SOURCE, capture, input_format=SOURCE.input_format).data["records"]
    original_encode = retrieval.base64.b64encode

    def interrupted_encode(data):
        result = original_encode(data)
        if data in {MEDIA, b"%PDF-1.7\nsynthetic"}:
            if boundary == "cancel":
                caller.cancellation.set()
            else:
                clock[0] = 2.0
        return result

    monkeypatch.setattr(retrieval.base64, "b64encode", interrupted_encode)
    result = engine.fetch_attachment(SOURCE, record, capture=capture, kind=kind,
        url_field="video_url" if kind == "recordings" else "url",
        bounds=Bounds(deadline_seconds=1), context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "partial"), result.public_dict()
    assert result.data["record"]["identity"] == record["identity"]
    assert result.data.get("attachment") is None
