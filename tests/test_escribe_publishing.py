"""Vendor-metadata synthetic execution; no SOAP calls to a live tenant."""
import base64
from copy import deepcopy
from dataclasses import replace
import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import escribe_publishing as soap
from civic_data_connectors.providers.escribe_write import EscribeWriteAdapter, identity_key
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.identification import validate_source
from civic_data_connectors.write_transport import WriteResponse

ROOT = Path(__file__).resolve().parents[1]
URL = "https://tcdsbpublishing.escribemeetings.com/WebService/eSCRIBE.Internet.WebService.svc"
SOURCE = Source("escribe", URL, input_format=soap.FORMAT)
MEETING = "11111111-1111-4111-8111-111111111111"
PORTAL = "22222222-2222-4222-8222-222222222222"
DATA = "http://schemas.datacontract.org/2004/07/eSCRIBE.Internet.WebService"
ARRAY = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"


def fields_for(model):
    kind = soap.contract()["operations"][model + "Create"]["request"][0]["type"]
    return soap.contract()["types"][kind]["fields"]


def sample(model):
    # Complete explicit synthetic test data, never defaults in the production adapter.
    value = {f["name"]: (None if f["nullable"] else False if f["type"].endswith("}boolean")
                        else 0 if f["type"].endswith("}int") else "") for f in fields_for(model)}
    if model == "Meeting":
        value.update(Id=MEETING, PortalId=PORTAL, MeetingTypeId=7, Name="Budget & council",
                     Start="2026-11-15T18:30:00", End="2026-11-15T20:30:00", Location="Council chamber")
    elif model == "Agenda":
        value.update(Id={"MeetingId": MEETING, "Type": "Agenda"})
    elif model == "AgendaItem":
        value.update(Id={"AgendaType": "Agenda", "Id": 12, "MeetingId": MEETING},
                     Sequence=2, ParentAgendaItemId=0)
    elif model == "Attachment":
        value.update(Id={"AgendaItemId": 12, "AgendaType": "Agenda", "MeetingId": MEETING, "Sequence": 1},
                     DocumentId=23)
    elif model == "Resolution":
        value.update(Id={"AgendaItemId": 12, "MeetingId": MEETING, "Sequence": 1},
                     Comments="Literal source resolution", MovedBy=7, SecondedBy=8, Number="R-12",
                     Result="Source result", Type="Source type", VoteType="Source vote type")
    elif model == "Package":
        value.update(Id=31, DocumentId=23, LanguageId=1033, MeetingId=MEETING, Type="Agenda")
    elif model == "Bookmark":
        value.update(Id={"AgendaItemId": 12, "AgendaType": "Agenda", "Id": 5, "MeetingId": MEETING},
                     TimeStart=120, TimeEnd=240)
    elif model == "Document":
        value.update(Id=23, Name="agenda.pdf", DisplayName="Agenda", FileSize=6, IsPrivate=True)
    return value


def xml_fields(node, value, namespace):
    """Independent synthetic server XML; deliberately does not call the production encoder."""
    for key, entry in value.items():
        child = ET.SubElement(node, "{" + namespace + "}" + key)
        if entry is None:
            child.set("{" + soap.XSI + "}nil", "true")
        elif isinstance(entry, dict):
            nested = DATA if key == "Id" and "Type" in entry else soap.NS
            xml_fields(child, entry, nested)
        elif type(entry) is bool:
            child.text = "true" if entry else "false"
        else:
            child.text = str(entry)


def response(method, value, *, namespace=soap.NS, relation=None):
    envelope = ET.Element("{" + soap.SOAP + "}Envelope")
    header = ET.SubElement(envelope, "{" + soap.SOAP + "}Header")
    ET.SubElement(header, "{" + soap.ADDRESS + "}Action").text = (
        "eSCRIBE.Internet.WebService/IPublishingService/" + method + "Response")
    if relation:
        ET.SubElement(header, "{" + soap.ADDRESS + "}RelatesTo").text = relation
    body = ET.SubElement(envelope, "{" + soap.SOAP + "}Body")
    result = ET.SubElement(body, "{" + soap.NS + "}" + method + "Response")
    if value != "VOID":
        field = ET.SubElement(result, "{" + soap.NS + "}" + method + "Result")
        if value is None:
            field.set("{" + soap.XSI + "}nil", "true")
        elif isinstance(value, dict):
            xml_fields(field, value, namespace)
        else:
            field.text = str(value).lower() if type(value) is bool else str(value)
    return ET.tostring(envelope, encoding="utf-8")


class Server:
    mock = True

    def __init__(self, model="Meeting"):
        self.model, self.value = model, sample(model)
        self.calls, self.mutations = [], 0
        self.lose_response = False
        self.exists = True
        self.mutate_readback = False

    def send(self, url, **options):
        assert url == URL and options["method"] == "POST"
        assert options["byte_limit"] > 0 and options["deadline_seconds"] > 0
        assert options["headers"]["Content-Type"].startswith("application/soap+xml;")
        envelope = ET.fromstring(options["body"])
        header = envelope.find("{" + soap.SOAP + "}Header")
        assert header.findtext("{" + soap.ADDRESS + "}To") == URL
        message_id = header.findtext("{" + soap.ADDRESS + "}MessageID")
        node = envelope.find("{" + soap.SOAP + "}Body")[0]
        method = node.tag.split("}")[1]
        assert header.findtext("{" + soap.ADDRESS + "}Action") == (
            "eSCRIBE.Internet.WebService/IPublishingService/" + method)
        self.calls.append(method)
        if method.endswith("Exists"):
            value = self.exists
        elif method.endswith("GetById"):
            value = deepcopy(self.value)
            if self.mutate_readback:
                value["Name"] = "Server changed it"
        elif method.endswith(("Create", "Update")):
            assert len(node) == 1
            expected_parameter = ("data" if method in {"AgendaCreate", "AgendaItemCreate", "AttachmentCreate", "PackageCreate", "ResolutionCreate"}
                                  else "Id" if method == "DocumentUpdate" else "Data")
            assert node[0].tag == "{" + soap.NS + "}" + expected_parameter
            # Decode primitive/identifier test data independently from the production decoder.
            def decode(parent, previous):
                result = {}
                for child in parent:
                    key = child.tag.split("}")[1]
                    old = previous[key]
                    result[key] = (None if child.get("{" + soap.XSI + "}nil") == "true" else
                        decode(child, old) if isinstance(old, dict) else
                        child.text == "true" if type(old) is bool else
                        int(child.text) if type(old) is int or key in {"LogoDocumentId", "CssDocumentId"} else child.text or "")
                return result
            self.value = decode(node[0], self.value)
            self.mutations += 1
            self.exists = True
            if self.lose_response:
                self.lose_response = False
                raise TimeoutError("Synthetic lost mutation response")
            value = self.value["Id"] if method.endswith("Create") else "VOID"
        else:
            raise AssertionError(method)
        namespace = DATA if self.model == "Agenda" else soap.NS
        payload = response(method, value, namespace=namespace, relation=message_id)
        return WriteResponse(200, payload, {"content-type": "application/soap+xml; charset=utf-8"})

    def request(self, url, **options):
        assert options.pop("allow_redirects") is False
        assert options.pop("allowed_origins") == ("https://tcdsbpublishing.escribemeetings.com",)
        result = self.send(url, **options)
        return Response(url, result.content, "application/soap+xml", result.status, result.headers)


class SendOnly:
    mock = True

    def __init__(self, server):
        self.send = server.send


def setup(tmp_path, model="Meeting", create=False):
    server = Server(model)
    server.exists = not create
    source = replace(SOURCE, namespace=validate_source(SOURCE))
    entity = {"Meeting": "meeting", "Agenda": "agenda", "AgendaItem": "agenda_item",
              "Attachment": "attachment", "Document": "document",
              "Package": "package", "Bookmark": "bookmark", "Resolution": "resolution"}[model]
    context = OperationContext(tenant="test", authorization=frozenset({"write:plan", "write:commit"}),
        credentials={"escribe": {"endpoint": URL, "tenant": "test", "allowed_namespaces": [source.namespace],
            "permissions": [entity + (":create" if create else ":update")],
            "resource_ids": [identity_key(server.value["Id"])], "meeting_ids": [MEETING], "portal_ids": [PORTAL]}})
    field = {"Meeting": "Name", "Agenda": "LogoDocumentId", "AgendaItem": "Sequence",
             "Attachment": "DocumentId", "Document": "DisplayName",
             "Package": "DocumentId", "Bookmark": "TimeStart", "Resolution": "MovedBy"}[model]
    patch = {field: "After" if model in {"Meeting", "Document"} else 99}
    change = {"key": "test", "entity": entity, "operation": "create" if create else "update",
              "resource_id": None if create else identity_key(server.value["Id"]),
              "meeting_id": MEETING if entity in {"agenda", "agenda_item", "attachment", "package", "bookmark", "resolution"} else None,
              "fields": {**deepcopy(server.value), **patch} if create else patch}
    engine = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                           write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    return engine, server, source, context, change


def plan(owner, source, context, change):
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {"plan_id": result.data["plan_id"], "plan_hash": result.data["plan_hash"]}


def test_compiled_contract_exactly_matches_all_pinned_vendor_types_and_actions():
    spec = importlib.util.spec_from_file_location("pin_escribe", ROOT / "scripts/pin_escribe_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.compile_contract() == soap.contract()
    assert soap.contract()["operations"]["DocumentUpdate"]["request"][0]["name"] == "Id"
    assert soap.contract()["operations"]["AgendaCreate"]["request"][0]["name"] == "data"
    assert soap.contract()["operations"]["MeetingCreate"]["request"][0]["name"] == "Data"


@pytest.mark.parametrize("model", ["Meeting", "Agenda", "AgendaItem", "Attachment", "Document", "Package", "Bookmark", "Resolution"])
@pytest.mark.parametrize("create", [False, True])
def test_native_record_plan_commit_readback_idempotency_and_reopen(tmp_path, model, create):
    owner, server, source, context, change = setup(tmp_path, model, create)
    approval = plan(owner, source, context, change)
    assert server.mutations == 0
    result = owner.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"] == server.value
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert server.mutations == 1


@pytest.mark.parametrize("create", [False, True])
def test_response_loss_never_replays_mutation(tmp_path, create):
    owner, server, source, context, change = setup(tmp_path, create=create)
    approval = plan(owner, source, context, change)
    server.lose_response = True
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    result = reopened.execute("commit_write", approval, context=context)
    assert result.status == ("partial" if create else "completed"), result.public_dict()
    assert server.mutations == 1


def test_concurrent_change_and_revoked_target_fail_before_mutation(tmp_path):
    owner, server, source, context, change = setup(tmp_path)
    approval = plan(owner, source, context, change)
    server.value["Name"] = "Concurrent edit"
    assert owner.execute("commit_write", approval, context=context).status == "failed"
    assert server.mutations == 0
    context.credentials["escribe"]["resource_ids"] = []
    assert owner.execute("commit_write", approval, context=context).status == "failed"
    assert server.mutations == 0


@pytest.mark.parametrize("model", ["Meeting", "Agenda", "AgendaItem", "Attachment", "Document", "Package", "Bookmark", "Resolution"])
def test_explicit_native_read_capture_identity_persistence_search_and_export(tmp_path, model):
    server = Server(model)
    identity = server.value["Id"]
    method = model + "GetById"
    parameter = "MeetingId" if model == "Meeting" else "Id"
    owner = create_engine(storage=SQLiteStorage(tmp_path / "read.sqlite"), provider_transport=server)
    result = owner.fetch(SOURCE, {"api_method": method, "api_parameters": {parameter: identity}})
    assert result.status == "partial" and not result.errors, result.public_dict()
    record, = result.data["records"]
    assert record["original"] == server.value
    assert record["identity"]["external_id"] == identity_key(identity)
    assert base64.b64decode(result.data["capture"]["content_base64"]).startswith(b"<")
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "read.sqlite"))
    if model == "Meeting":
        assert reopened.execute("search", {"query": {"phrases": ["Budget & council"]}}).data["hits"]
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data


@pytest.mark.parametrize("mutation", ["unknown", "nil", "duplicate", "method", "doctype", "address"])
def test_wrong_or_unmapped_soap_is_rejected(mutation):
    payload = response("MeetingGetById", sample("Meeting"))
    if mutation == "unknown":
        payload = payload.replace(b"</e:MeetingGetByIdResult>", b"<e:Unknown>1</e:Unknown></e:MeetingGetByIdResult>")
    elif mutation == "nil":
        payload = payload.replace(b"<e:Id>", b'<e:Id i:nil="true">')
    elif mutation == "duplicate":
        payload = payload.replace(b"</e:MeetingGetByIdResult>", b"<e:Name>Duplicate</e:Name></e:MeetingGetByIdResult>")
    elif mutation == "method":
        payload = payload.replace(b"MeetingGetByIdResponse", b"MeetingUpdateResponse")
    elif mutation == "doctype":
        payload = b'<!DOCTYPE x [<!ENTITY a "bad">]>' + payload
    else:
        payload = payload.replace(b"IPublishingService/MeetingGetByIdResponse", b"IPublishingService/OtherResponse")
    with pytest.raises((ValueError, ET.ParseError)):
        soap.response_value(payload, "MeetingGetById")


def test_read_bounds_cancel_and_unmapped_upload_do_not_create_empty_success():
    server = Server()
    owner = create_engine(provider_transport=server)
    request = {"api_method": "MeetingGetById", "api_parameters": {"MeetingId": MEETING}}
    result = owner.fetch(SOURCE, request, bounds=Bounds(transfer_bytes=16))
    assert result.status == "failed" and not server.calls
    context = OperationContext()
    context.cancellation.set()
    assert owner.fetch(SOURCE, request, context=context).status == "cancelled"
    assert not server.calls
    assert owner.fetch(SOURCE, {"api_method": "DocumentUpload", "api_parameters": {}}).status == "failed"


@pytest.mark.parametrize("method,model,parent,wrapper,namespace", [
    ("ResolutionGetByMeeting", "Resolution", {"MeetingId": MEETING}, "Resolution.Record", soap.NS),
    ("ResolutionGetByAgendaItem", "Resolution", {"Id": {"AgendaType": "Agenda", "Id": 12,
     "MeetingId": MEETING}}, "Resolution.Record", soap.NS),
    ("PackageGetByMeeting", "Package", {"MeetingId": MEETING}, "Package.Record", soap.NS),
    ("BookmarkGetByMeeting", "Bookmark", {"MeetingId": MEETING}, "Bookmark.Record", soap.NS),
    ("BookmarkGetByAgenda", "Bookmark", {"AgendaId": {"MeetingId": MEETING, "Type": "Agenda"}},
     "Bookmark.Record", soap.NS),
    ("MeetingGetByPortal", "Meeting", {"PortalId": PORTAL}, "Meeting.Record", soap.NS),
    ("AgendaGetByMeeting", "Agenda", {"MeetingId": MEETING}, "Agenda.Record", DATA),
    ("AgendaItemGetByAgenda", "AgendaItem", {"AgendaId": {"MeetingId": MEETING, "Type": "Agenda"}},
     "AgendaItem.Record", soap.NS),
    ("AttachmentGetByAgenda", "Attachment", {"AgendaId": {"MeetingId": MEETING, "Type": "Agenda"}},
     "Attachment.Record", soap.NS),
    ("AttachmentGetByAgendaItem", "Attachment", {"AgendaItemId": {
        "AgendaType": "Agenda", "Id": 12, "MeetingId": MEETING}}, "Attachment.Record", soap.NS),
])
def test_unpaged_collections_retain_native_parents_and_enforce_record_bounds(method, model, parent, wrapper, namespace):
    class Collection:
        def request(self, url, **options):
            envelope = ET.fromstring(options["body"])
            relation = envelope.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
            payload = ET.fromstring(response(method, {}, relation=relation))
            result = payload.find("{" + soap.SOAP + "}Body")[0][0]
            xml_fields(ET.SubElement(result, "{" + namespace + "}" + wrapper), sample(model), namespace)
            return Response(url, ET.tostring(payload), "application/soap+xml")
    owner = create_engine(provider_transport=Collection())
    result = owner.fetch(SOURCE, {"api_method": method, "api_parameters": parent})
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.data["records"][0]["original"] == sample(model)
    bad = deepcopy(parent)
    key = next(iter(bad))
    if isinstance(bad[key], dict):
        bad[key]["MeetingId"] = PORTAL
    else:
        bad[key] = PORTAL if bad[key] != PORTAL else MEETING
    mismatch = owner.fetch(SOURCE, {"api_method": method, "api_parameters": bad})
    assert mismatch.status == "failed" and not mismatch.data


def test_native_document_content_bytes_metadata_binding_and_portable_captures(tmp_path):
    raw = b"ABCDEF"

    class ContentServer(Server):
        def send(self, url, **options):
            envelope = ET.fromstring(options["body"])
            method = envelope.find("{" + soap.SOAP + "}Body")[0].tag.split("}")[1]
            if method != "DocumentGetContent":
                return super().send(url, **options)
            self.calls.append(method)
            relation = envelope.find("{" + soap.SOAP + "}Header").findtext("{" + soap.ADDRESS + "}MessageID")
            return WriteResponse(200, response(method, base64.b64encode(raw).decode(), relation=relation),
                                 {"content-type": "application/soap+xml"})

    server = ContentServer("Document")
    owner = create_engine(storage=SQLiteStorage(tmp_path / "binary.sqlite"), provider_transport=server)
    request = {"api_method": "DocumentGetContent", "api_parameters": {"Id": 23}}
    result = owner.fetch(SOURCE, request)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert server.calls == ["DocumentGetById", "DocumentGetContent"]
    assert base64.b64decode(result.data["captures"][1]["content_base64"]) == raw
    assert result.data["records"][0]["normalized"]["supplied_document_byte_length"] == 6
    for _ in range(2):
        assert owner.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    for format in ("json", "jsonl", "zip"):
        exported = owner.execute("export", {"bundle": result.data, "format": format})
        assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == result.data
    server.calls.clear()
    assert owner.fetch(SOURCE, request, bounds=Bounds(max_pages=1)).status == "failed"
    assert not server.calls
    server.value["FileSize"] = 7
    mismatch = owner.fetch(SOURCE, request)
    assert mismatch.status == "partial" and mismatch.errors and mismatch.data["records"]
    assert "supplied_document_sha256" not in mismatch.data["records"][0]["normalized"]


def test_multilingual_item_source_text_keeps_native_language_keys_without_inference():
    payload = ET.fromstring(response("AgendaItemGetById", sample("AgendaItem")))
    result = payload.find("{" + soap.SOAP + "}Body")[0][0]
    for name, text in (("Title", "Budget & council"), ("Minutes", "The source reports this literal action.")):
        node = result.find("{" + soap.NS + "}" + name)
        node.attrib.clear()
        pair = ET.SubElement(node, "{" + ARRAY + "}KeyValueOfintstring")
        ET.SubElement(pair, "{" + ARRAY + "}Key").text = "1033"
        ET.SubElement(pair, "{" + ARRAY + "}Value").text = text
    normalized = create_engine().normalize(SOURCE, ET.tostring(payload), input_format=soap.FORMAT)
    assert normalized.status == "completed", normalized.public_dict()
    record, = normalized.data["records"]
    assert [segment["field"] for segment in record["text"]] == ["Title", "Minutes"]
    assert all(segment["provenance"]["source_language_key"] == 1033 for segment in record["text"])
    assert not {"motions", "votes", "language"} & record["normalized"].keys()


@pytest.mark.parametrize("case", ["missing_field", "unknown_field", "wrong_type", "wrong_parent", "upload", "delete"])
def test_unmapped_or_unsafe_record_change_is_rejected_before_mutation(tmp_path, case):
    owner, server, source, context, change = setup(tmp_path, "AgendaItem")
    if case == "missing_field":
        server.value.pop("Minutes")
    elif case == "unknown_field":
        change["fields"]["NotInSchema"] = "no"
    elif case == "wrong_type":
        change["fields"]["Sequence"] = True
    elif case == "wrong_parent":
        change["meeting_id"] = PORTAL
    else:
        change["operation"] = case
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    assert result.status == "failed" and not server.mutations, result.public_dict()


@pytest.mark.parametrize("fault", ["cancel", "mime", "oversize"])
def test_post_send_fault_keeps_uncertain_intent_and_only_reads_on_restart(tmp_path, fault, monkeypatch):
    owner, server, source, context, change = setup(tmp_path)
    approval = plan(owner, source, context, change)
    original = server.send

    def interrupted_send(url, **options):
        result = original(url, **options)
        if b"<e:MeetingUpdate>" in options["body"]:
            if fault == "cancel":
                context.cancellation.set()
            elif fault == "mime":
                return WriteResponse(200, result.content, {"content-type": "text/html"})
            else:
                return WriteResponse(200, b"x" * (options["byte_limit"] + 1), result.headers)
        return result

    monkeypatch.setattr(server, "send", interrupted_send)
    owner = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                          write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    assert owner.execute("commit_write", approval, context=context).status == "partial"
    fresh = replace(context, cancellation=OperationContext().cancellation)
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "store.sqlite"),
                             write_adapters={"escribe": EscribeWriteAdapter(SendOnly(server))})
    assert reopened.execute("commit_write", approval, context=fresh).status == "completed"
    assert server.mutations == 1


def test_wrong_native_read_id_and_expired_mapping_fail_without_empty_complete(monkeypatch):
    server = Server()
    owner = create_engine(provider_transport=server)
    request = {"api_method": "MeetingGetById", "api_parameters": {"MeetingId": PORTAL}}
    assert owner.fetch(SOURCE, request).status == "failed"
    original = soap.parse_bundle
    clock = [0.0]

    def delayed(*args):
        result = original(*args)
        clock[0] = 2.0
        return result

    monkeypatch.setattr(soap, "parse_bundle", delayed)
    monkeypatch.setattr(soap, "monotonic", lambda: clock[0])
    result = owner.fetch(SOURCE, {**request, "api_parameters": {"MeetingId": MEETING}},
                         bounds=Bounds(deadline_seconds=1))
    assert result.status == "failed" and not result.data


@pytest.mark.parametrize("identity", [23.5, "023", "+23"])
def test_document_update_does_not_coerce_an_invalid_resource_to_an_authorized_id(tmp_path, identity):
    owner, server, source, context, change = setup(tmp_path, "Document")
    change["resource_id"] = identity
    result = owner.execute("plan_write", {"source": source.public_dict(), "changes": [change]}, context=context)
    assert result.status == "failed" and not server.calls, result.public_dict()
