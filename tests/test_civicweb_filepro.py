"""Real engine interfaces with synthetic vendor-shaped SOAP responses."""

import base64
import hashlib
from dataclasses import replace

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.civicweb_filepro import FORMAT
from test_civicweb_soap import CHILDREN, envelope

SOURCE = Source("civicweb", "https://synthetic.civicweb.net/Portal/", input_format=FORMAT)
FILE = envelope("GetOriginalFile", '<Html>&lt;p&gt;Council agenda&lt;/p&gt;</Html>'
                '<FileBytes>JVBERi0=</FileBytes><Extension>.pdf</Extension>')


class Network:
    def __init__(self, raw):
        self.raw, self.calls = raw, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["method"] == "POST"
        assert kwargs["allow_redirects"] is False
        return Response(url, self.raw, "text/xml")


def test_engine_discover_folder_identity_raw_capture_and_saved_offline():
    network = Network(CHILDREN)
    engine = create_engine(provider_transport=network)
    result = engine.discover(SOURCE)
    assert result.status == "partial", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "71"
    assert record["identity"]["record_type"] == "folder"
    assert record["identity"]["parent"] is None
    assert "preserved" in record["original"]["Future"]["xml"]
    bundle = result.data["bundles"][0]
    assert base64.b64decode(bundle["capture"]["content_base64"]) == CHILDREN
    replay = create_engine().normalize(SOURCE, CHILDREN, input_format=FORMAT)
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert len(network.calls) == 1


def test_engine_document_bytes_request_identity_and_saved_replay():
    network = Network(FILE)
    engine = create_engine(provider_transport=network)
    source = replace(SOURCE, options={"filepro_resource": "original"})
    result = engine.fetch_record(source, "77")
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["derivation"] == "requested_provider_identifier"
    assert record["identity"]["external_id"] == "77"
    assert record["identity"]["parent"] is None
    file = result.data["extensions"]["file"]
    assert base64.b64decode(file["content_base64"]) == b"%PDF-"
    assert file["sha256"] == hashlib.sha256(b"%PDF-").hexdigest()
    assert record["text"][0]["text"] == "Council agenda"
    # Exact raw response replay requires the supplied request ID; no invented ID.
    saved = replace(source, options={**source.options, "document_id": 77})
    replay = create_engine().normalize(saved, FILE, input_format=FORMAT)
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert create_engine().normalize(source, FILE, input_format=FORMAT).status == "failed"
    assert len(network.calls) == 1


def test_html_only_original_remains_partial_and_no_file_is_invented():
    raw = envelope("GetOriginalFile", '<Html>&lt;p&gt;Agenda&lt;/p&gt;</Html><Extension>.docx</Extension>')
    result = create_engine(provider_transport=Network(raw)).fetch_record(
        replace(SOURCE, options={"filepro_resource": "original"}), "77")
    assert result.status == "partial", result.public_dict()
    assert "file" not in result.data["extensions"]
    assert result.data["records"][0]["original"]["Html"] == "<p>Agenda</p>"


def test_parent_folder_and_midpage_resume_retries_hash_scope_and_filters():
    raw = envelope("GetChildList", '<ID>70</ID><Nodes>' + ''.join(
        f'<DocumentTreeNodeInformation><ID>{i}</ID><Name>Document {i}</Name>'
        '<Folder>false</Folder><IsPublic>true</IsPublic><CanUpdate>false</CanUpdate>'
        '</DocumentTreeNodeInformation>' for i in (71, 72, 73)) + '</Nodes>')
    network = Network(raw)
    engine = create_engine(provider_transport=network)
    source = replace(SOURCE, options={"folder_id": 70})
    first = engine.discover(source, bounds=Bounds(max_records=1))
    assert first.status == "partial", first.public_dict()
    record = first.data["records"][0]
    assert record["identity"]["parent"]["external_id"] == "70"
    token = first.coverage["checkpoint"]
    second = engine.discover(source, bounds=Bounds(max_records=1, checkpoint=token))
    assert second.data["records"][0]["identity"]["external_id"] == "72"
    again = engine.discover(source, bounds=Bounds(max_records=1, checkpoint=token))
    assert again.data["records"][0]["identity"] == second.data["records"][0]["identity"]
    assert engine.discover(source, bounds=Bounds(max_records=1, checkpoint=token),
        context=OperationContext(tenant="other")).status == "failed"
    network.raw = raw.replace(b'Document 71', b'Changed 71')
    assert engine.discover(source, bounds=Bounds(max_records=1, checkpoint=token)).status == "failed"


def test_pdf_variant_requires_pdf_bytes_and_explicit_meeting_id():
    source = replace(SOURCE, options={"filepro_resource": "meeting_pdf", "meeting_id": 17})
    raw = envelope("GetMeetingAttachmentPdfFile", '<FileBytes>JVBERi0=</FileBytes><Extension>.pdf</Extension>')
    result = create_engine(provider_transport=Network(raw)).fetch_record(source, "77")
    assert result.status == "completed", result.public_dict()
    assert result.data["records"][0]["identity"]["parent"]["external_id"] == "17"
    assert result.data["records"][0]["relationships"][0]["relation"] == "meeting"
    bad = envelope("GetMeetingAttachmentPdfFile", '<FileBytes>eA==</FileBytes><Extension>.pdf</Extension>')
    assert create_engine(provider_transport=Network(bad)).fetch_record(source, "77").status == "failed"


def test_saved_search_results_preserve_html_without_executing_or_inferred_parent():
    raw = envelope("GetSearchResultDetails", '<DocumentSearchResult><Id>77</Id>'
        '<TitleHtml>&lt;b&gt;Council&lt;/b&gt;</TitleHtml>'
        '<SampleHtml>&lt;script&gt;private&lt;/script&gt;Budget excerpt</SampleHtml>'
        '<PathHtml>&lt;a href="/Documents/DocumentList.aspx?ID=1"&gt;Meetings&lt;/a&gt;</PathHtml>'
        '</DocumentSearchResult>')
    result = create_engine().normalize(SOURCE, raw, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["normalized"]["title"] == "Council"
    assert record["normalized"]["search_excerpts"] == ["Budget excerpt"]
    assert record["identity"]["parent"] is None
    assert "<script>" in record["original"]["SampleHtml"]
    assert "meeting_date" not in record["normalized"]


@pytest.mark.parametrize("case", ["denied", "cancelled", "bytes"])
def test_affected_engine_policy_boundaries(case):
    network = Network(CHILDREN)
    ctx = OperationContext()
    bounds = Bounds()
    if case == "denied":
        ctx = OperationContext(allowed_namespaces=("unrelated",))
    elif case == "cancelled":
        ctx.cancellation.set()
    else:
        bounds = Bounds(parser_bytes=32)
    result = create_engine(provider_transport=network).discover(SOURCE, bounds=bounds, context=ctx)
    assert result.status in {"failed", "cancelled"}, result.public_dict()
    assert network.calls == []


def test_wrong_child_parent_rejected():
    result = create_engine(provider_transport=Network(CHILDREN)).discover(replace(SOURCE, options={"folder_id": 70}))
    assert result.status == "failed", result.public_dict()


class SearchNetwork:
    def __init__(self):
        self.calls = []
        self.changed = False

    def request(self, url, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["allow_redirects"] is False
        action = kwargs["headers"]["SOAPAction"]
        if action == '"http://civicweb.net/GetSearchResults"':
            raw = envelope("GetSearchResults", '<int>71</int><int>72</int><int>73</int>')
        else:
            assert action == '"http://civicweb.net/GetSearchResultDetails"'
            raw = envelope("GetSearchResultDetails", ''.join(
                f'<DocumentSearchResult><Id>{i}</Id><TitleHtml>{title}</TitleHtml>'
                '<SampleHtml>Returned sample only</SampleHtml><PathHtml>Meetings</PathHtml>'
                '</DocumentSearchResult>' for i, title in (
                    (71, 'Other'), (72, 'Council changed' if self.changed else 'Council budget'), (73, 'Council minutes'))))
        return Response(url, raw, "text/xml")


def test_engine_native_search_later_match_midbatch_resume_and_retry():
    network = SearchNetwork()
    engine = create_engine(provider_transport=network)
    request = {"native": True, "source": SOURCE.public_dict(), "query": {"terms": ["Council"], "limit": 1}}
    first = engine.execute("search", request)
    assert first.status == "partial", first.public_dict()
    assert first.data["hits"][0]["identity"]["external_id"] == "72"
    assert first.coverage["searched_records"] == 2  # first nonhit does not consume hit limit
    token = first.coverage["checkpoint"]
    resumed = {**request, "bounds": {"checkpoint": token}}
    second = engine.execute("search", resumed)
    assert second.status == "partial", second.public_dict()
    assert second.data["hits"][0]["identity"]["external_id"] == "73"
    assert second.coverage["query_candidates_exhausted"] is True
    retry = engine.execute("search", resumed)
    assert retry.data["hits"][0]["identity"] == second.data["hits"][0]["identity"]
    assert len(network.calls) == 6
    assert first.coverage["catalog_complete"] is False
    assert first.coverage["available_text_scope"].startswith("search excerpts")


def test_search_checkpoint_bound_to_caller_query_and_changed_capture():
    network = SearchNetwork()
    engine = create_engine(provider_transport=network)
    request = {"native": True, "source": SOURCE.public_dict(), "query": {"terms": ["Council"], "limit": 1}}
    token = engine.execute("search", request).coverage["checkpoint"]
    resume = {**request, "bounds": {"checkpoint": token}}
    assert engine.execute("search", resume, context=OperationContext(tenant="other")).status == "failed"
    assert engine.execute("search", {**resume, "query": {"terms": ["Other"]}}).status == "failed"
    network.changed = True
    result = engine.execute("search", resume)
    assert result.status == "partial" and result.errors
    assert result.data["hits"] == []
    assert result.coverage["checkpoint"] is None


def test_search_record_bound_continuation_unknown_filters_and_denied_policy():
    network = SearchNetwork()
    engine = create_engine(provider_transport=network)
    request = {"native": True, "source": SOURCE.public_dict(),
        "query": {"terms": ["Council"], "body": "Council"},
        "bounds": {"max_records": 1, "max_pages": 1, "date_from": "2026-01-01", "date_to": "2026-12-31"}}
    first = engine.execute("search", request)
    assert first.data["hits"] == []
    assert first.coverage["checkpoint"]
    result = engine.execute("search", {**request, "bounds": {
        **request["bounds"], "checkpoint": first.coverage["checkpoint"]}})
    assert result.data["hits"][0]["identity"]["external_id"] == "72"
    assert result.coverage["unknown_body_records"] == ["72"]
    assert result.coverage["unknown_date_records"] == ["72"]
    before = len(network.calls)
    assert engine.execute("search", request,
        context=OperationContext(allowed_namespaces=("other",))).status == "failed"
    assert len(network.calls) == before


def test_new_options_do_not_relax_legacy_or_credential_source_validation():
    engine = create_engine()
    assert engine.execute("validate_source", {"source": {
        **SOURCE.public_dict(), "input_format": "civicweb-html", "options": {"folder_id": 70}}}).status == "failed"
    assert engine.execute("validate_source", {"source": {
        **SOURCE.public_dict(), "options": {"folder_id": 70, "invented": "x"}}}).status == "failed"
    with pytest.raises(ValueError, match="Credential-bearing"):
        replace(SOURCE, options={"filepro_resource": "original", "credentials": {"password": "synthetic"}})
