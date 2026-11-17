"""Pinned eSCRIBE PublishingService SOAP 1.2 binding; no discovery or login effects."""
import base64
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
import json
from hashlib import sha256
import re
from time import monotonic
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from ..engine import canonical_hash
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from ..write_adapters import WriteCancelled
from .contracts import _origin
from .identification import validate_url
from .native import make_bundle

FORMAT = "escribe-publishing-soap-xml"
NS = "eSCRIBE.Internet.WebService"
SOAP = "http://www.w3.org/2003/05/soap-envelope"
ADDRESS = "http://www.w3.org/2005/08/addressing"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://www.w3.org/2001/XMLSchema"
SER = "http://schemas.microsoft.com/2003/10/Serialization/"
READS = frozenset({"MeetingGetById", "MeetingGetByPortal", "AgendaGetById", "AgendaGetByMeeting",
    "AgendaItemGetById", "AgendaItemGetByAgenda", "AttachmentGetById", "AttachmentGetByAgenda",
    "AttachmentGetByAgendaItem", "DocumentGetById", "DocumentGetContent", "PackageGetById", "PackageGetByMeeting",
    "BookmarkGetById", "BookmarkGetByMeeting", "BookmarkGetByAgenda",
    "ResolutionGetById", "ResolutionGetByMeeting", "ResolutionGetByAgendaItem",
    "MeetingGetByMeetingType", "AgendaItemTextGetByMeetingId", "AgendaItemItemHistoryView",
    "MeetingAgendaItemsWithHistory", "MeetingTypeGetByPortal", "DocumentGetContentChunk", "DocumentGetSince"})
for prefix, namespace in (("s", SOAP), ("a", ADDRESS), ("e", NS), ("i", XSI)):
    ET.register_namespace(prefix, namespace)


@lru_cache(maxsize=1)
def contract():
    return json.loads(files("civic_data_connectors.data").joinpath("escribe_publishing.json").read_bytes())


def endpoint(source):
    validate_url(source.url)
    p = urlsplit(source.url)
    if (source.provider != "escribe" or p.scheme != "https" or p.port not in {None, 443}
            or not re.fullmatch(r"[a-z0-9-]+\.escribemeetings\.com", p.hostname or "")
            or p.path != "/WebService/eSCRIBE.Internet.WebService.svc" or p.query or p.fragment
            or source.options or source.input_format != FORMAT):
        raise ValueError("Use an explicit HTTPS eSCRIBE PublishingService source and format without options.")
    return source.url


def scalar(value, kind, *, decode=False):
    namespace, name = kind[1:].split("}")
    if namespace == SER and name == "guid":
        if not isinstance(value, str) or str(UUID(value)) != value.lower():
            raise ValueError("A canonical vendor GUID is required.")
        return value
    if kind in contract()["types"] and "base" in contract()["types"][kind]:
        return scalar(value, contract()["types"][kind]["base"], decode=decode)
    if namespace != XSD:
        raise ValueError("Unmapped scalar namespace.")
    if name in {"int", "long"}:
        if decode and isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
            value = int(value)
        bits = 32 if name == "int" else 64
        if type(value) is not int or not -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
            raise ValueError("A bounded vendor integer is required.")
        return value if decode else str(value)
    if name == "boolean":
        if decode:
            if value not in {"true", "false", "1", "0"}:
                raise ValueError("Unrecognized XML boolean.")
            return value in {"true", "1"}
        if type(value) is not bool:
            raise ValueError("An explicit boolean is required.")
        return "true" if value else "false"
    if not isinstance(value, str) or any(ord(c) < 32 and c not in "\r\n\t" for c in value):
        raise ValueError("A source string without forbidden control characters is required.")
    if name == "dateTime":
        if "T" not in value:
            raise ValueError("An explicit dateTime literal is required.")
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif name == "base64Binary":
        base64.b64decode(value, validate=True)
    elif name != "string":
        raise ValueError("Unmapped vendor scalar type.")
    return value


def encode_fields(node, values, fields, depth=0):
    if depth > 32 or not isinstance(values, dict) or set(values) - {f["name"] for f in fields}:
        raise ValueError("Unknown or excessive vendor model fields.")
    for field in fields:
        name = field["name"]
        if name not in values:
            if not field["optional"]:
                raise ValueError("Missing required vendor field.")
            continue
        value = values[name]
        entries = value if field["many"] else [value]
        if not isinstance(entries, list):
            raise ValueError("A repeated vendor field requires an array.")
        for item in entries:
            child = ET.SubElement(node, "{" + field["namespace"] + "}" + name)
            if item is None:
                if not field["nullable"]:
                    raise ValueError("Vendor field is not nullable.")
                child.set("{" + XSI + "}nil", "true")
            else:
                model = contract()["types"].get(field["type"], {})
                if "fields" in model:
                    encode_fields(child, item, model["fields"], depth + 1)
                else:
                    child.text = scalar(item, field["type"])


def decode_fields(node, fields, depth=0):
    if depth > 32 or (node.text and node.text.strip()):
        raise ValueError("Unmapped mixed/deep vendor model.")
    known = {"{" + f["namespace"] + "}" + f["name"]: (i, f) for i, f in enumerate(fields)}
    result, position = {}, -1
    for child in node:
        if child.tag not in known:
            raise ValueError("Unmapped vendor response field.")
        index, field = known[child.tag]
        if index < position or (index == position and not field["many"]):
            raise ValueError("Duplicate or reordered vendor response field.")
        position = index
        if child.tail and child.tail.strip():
            raise ValueError("Unmapped mixed vendor content.")
        if set(child.attrib) - {"{" + XSI + "}nil"}:
            raise ValueError("Unmapped vendor field attributes.")
        nil = child.attrib.get("{" + XSI + "}nil")
        if nil in {"true", "1"}:
            if not field["nullable"] or len(child) or (child.text and child.text.strip()):
                raise ValueError("Invalid nil vendor field.")
            value = None
        else:
            if nil not in {None, "false", "0"}:
                raise ValueError("Invalid nil declaration.")
            model = contract()["types"].get(field["type"], {})
            if "fields" in model:
                value = decode_fields(child, model["fields"], depth + 1)
            else:
                if len(child):
                    raise ValueError("Vendor scalar has nested fields.")
                value = scalar(child.text or "", field["type"], decode=True)
        if field["many"]:
            result.setdefault(field["name"], []).append(value)
        else:
            result[field["name"]] = value
    for field in fields:
        if not field["optional"] and field["name"] not in result:
            raise ValueError("Missing required response field.")
    return result


def request_xml(method, parameters, url):
    operation = contract()["operations"][method]
    envelope = ET.Element("{" + SOAP + "}Envelope")
    header = ET.SubElement(envelope, "{" + SOAP + "}Header")
    message_id = "urn:uuid:" + str(uuid4())
    for name, text in (("Action", operation["action"]), ("MessageID", message_id), ("To", url)):
        node = ET.SubElement(header, "{" + ADDRESS + "}" + name)
        node.text = text
        if name in {"Action", "To"}:
            node.set("{" + SOAP + "}mustUnderstand", "1")
    reply = ET.SubElement(header, "{" + ADDRESS + "}ReplyTo")
    ET.SubElement(reply, "{" + ADDRESS + "}Address").text = ADDRESS + "/anonymous"
    body = ET.SubElement(envelope, "{" + SOAP + "}Body")
    encode_fields(ET.SubElement(body, "{" + NS + "}" + method), parameters, operation["request"])
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True), message_id


def response_value(content, method=None, message_id=None):
    if b"\0" in content or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("Unsupported SOAP XML declaration.")
    root = ET.fromstring(content)
    if root.tag != "{" + SOAP + "}Envelope":
        raise ValueError("The pinned binding requires SOAP1.2.")
    bodies = root.findall("{" + SOAP + "}Body")
    if len(bodies) != 1 or len(bodies[0]) != 1:
        raise ValueError("One exact SOAP response body is required.")
    node = bodies[0][0]
    if not node.tag.startswith("{" + NS + "}") or not node.tag.endswith("Response"):
        raise ValueError("SOAP fault or unmapped result.")
    actual = node.tag.split("}")[1].removesuffix("Response")
    if actual not in contract()["operations"] or (method is not None and actual != method):
        raise ValueError("SOAP response method does not match the exact request.")
    headers = root.findall("{" + SOAP + "}Header")
    if len(headers) > 1 or (message_id is not None and len(headers) != 1):
        raise ValueError("One exact addressing header is required for a requested response.")
    header = headers[0] if headers else None
    if header is not None:
        for name, expected in (("Action", contract()["operations"][actual]["action"] + "Response"),
                               ("RelatesTo", message_id)):
            nodes = header.findall("{" + ADDRESS + "}" + name)
            if ((message_id is not None and len(nodes) != 1) or len(nodes) > 1
                    or (nodes and expected is not None and nodes[0].text != expected)):
                raise ValueError("SOAP addressing does not match the exact request.")
    values = decode_fields(node, contract()["operations"][actual]["response"])
    return actual, next(iter(values.values()), None)


class Session:
    def __init__(self, source, context, bounds, transport, *, storage=None, deadline=None):
        self.url, self.context, self.bounds, self.transport = endpoint(source), context, bounds, transport
        self.storage = storage
        self.deadline = deadline if deadline is not None else monotonic() + bounds.deadline_seconds
        self.pages, self.bytes = 0, 0

    def check(self):
        if operation_cancelled(self.storage, self.context):
            raise WriteCancelled()
        if monotonic() >= self.deadline:
            raise ValueError("Publishing Service exceeded the operation deadline.")

    def call(self, method, parameters):
        self.check()
        if self.pages >= self.bounds.max_pages:
            raise ValueError("Publishing Service exceeded the request count bound.")
        body, message_id = request_xml(method, parameters, self.url)
        remaining = min(self.bounds.parser_bytes, self.bounds.transfer_bytes - self.bytes)
        if len(body) > remaining:
            raise ValueError("SOAP request exceeds remaining byte bounds.")
        headers = {"Content-Type": 'application/soap+xml; charset=utf-8; action="' +
                   contract()["operations"][method]["action"] + '"', "Accept": "application/soap+xml"}
        if callable(getattr(self.transport, "request", None)):
            response = self.transport.request(self.url, method="POST", body=body, headers=headers,
                byte_limit=remaining, deadline_seconds=self.deadline - monotonic(),
                allowed_origins=(_origin(self.url),), allow_redirects=False)
            if response.url != self.url:
                raise ValueError("SOAP response was redirected.")
            mime = response.content_type.split(";", 1)[0].lower().strip()
        else:
            response = self.transport.send(self.url, method="POST", body=body, headers=headers,
                byte_limit=remaining, deadline_seconds=self.deadline - monotonic())
            mime = next((v for k, v in response.headers.items() if k.lower() == "content-type"), "").split(";", 1)[0].lower().strip()
        self.pages += 1
        self.bytes += len(response.content)
        self.check()
        if response.status != 200 or len(response.content) > remaining or mime != "application/soap+xml":
            raise ValueError("The exact bounded SOAP1.2 response was not returned.")
        _, value = response_value(response.content, method, message_id)
        self.check()
        return value, response.content


def records(value, model):
    if value is None:
        return []
    if model.split("}")[-1].startswith("ArrayOf"):
        fields = contract()["types"][model]["fields"]
        return value.get(fields[0]["name"], [])
    return [value]


def bind_records(method, parameters, bundle):
    fields = contract()["operations"][method]["request"]
    if not isinstance(parameters, dict) or set(parameters) != {f["name"] for f in fields}:
        raise ValueError("Every native selection parameter must be explicit.")
    selected = next(iter(parameters.values()))
    if selected is None:
        raise ValueError("A native parent/identity selection cannot be nil.")
    if method == "AgendaItemItemHistoryView":
        from .escribe_history import bind_history
        return bind_history(parameters, bundle)
    for record in bundle["records"]:
        raw = record["original"]
        identity = raw["Id"]
        if method.endswith("GetById"):
            matches = identity == selected
        elif method == "DocumentGetSince":
            # The metadata declares a literal selector, not inclusive/exclusive
            # ordering, a page stride or a per-row parent identity.
            matches = type(selected) is int and 0 <= selected < 2**31
        elif method == "MeetingGetByMeetingType":
            matches = (raw.get("MeetingTypeId") == selected.get("Id")
                       and raw.get("PortalId") == selected.get("PortalId"))
        elif method == "AgendaItemTextGetByMeetingId":
            matches = (raw.get("MeetingId") == parameters["meetingId"]
                       and raw.get("LanguageId") == parameters["languageId"])
        elif method == "MeetingGetByPortal":
            matches = raw.get("PortalId") == selected
        elif method == "MeetingTypeGetByPortal":
            matches = isinstance(identity, dict) and identity.get("PortalId") == selected
        elif method == "PackageGetByMeeting":
            matches = raw.get("MeetingId") == selected
        elif method in {"AgendaGetByMeeting", "BookmarkGetByMeeting", "ResolutionGetByMeeting"}:
            matches = identity.get("MeetingId") == selected
        elif method in {"AgendaItemGetByAgenda", "AttachmentGetByAgenda", "BookmarkGetByAgenda"}:
            matches = (identity.get("MeetingId") == selected.get("MeetingId")
                       and identity.get("AgendaType") == selected.get("Type"))
        elif method == "ResolutionGetByAgendaItem":
            matches = (identity.get("MeetingId") == selected.get("MeetingId")
                       and identity.get("AgendaItemId") == selected.get("Id"))
        elif method == "AttachmentGetByAgendaItem":
            matches = (identity.get("MeetingId") == selected.get("MeetingId")
                       and identity.get("AgendaType") == selected.get("AgendaType")
                       and identity.get("AgendaItemId") == selected.get("Id"))
        else:
            matches = False
        if not matches:
            raise ValueError("The native record is outside the exact selected parent/identity.")


def parse_bundle(source, namespace, content):
    endpoint(source)
    method, value = response_value(content)
    if method not in READS or method in {"DocumentGetContent", "DocumentGetContentChunk"}:
        raise ValueError("Only mapped record reads form a standalone record bundle.")
    if method == "MeetingAgendaItemsWithHistory":
        raise ValueError("History item IDs require explicit request meeting context; use fetch.")
    if method == "AgendaItemItemHistoryView":
        from .escribe_history import history_bundle
        return history_bundle(source, namespace, content, value)
    response = contract()["operations"][method]["response"][0]
    model = response["type"]
    kind = {"Meeting": "meeting", "Agenda": "agenda", "AgendaItem": "agenda_item",
            "Attachment": "attachment", "Document": "document",
            "Package": "package", "Bookmark": "bookmark", "Resolution": "resolution",
            "AgendaItemText": "agenda_item_text", "MeetingType": "meeting_type"}[method.split("Get")[0]]
    rows = []
    meeting_type_ids = set()
    document_since_ids = set()
    for raw in records(value, model):
        if not isinstance(raw, dict) or "Id" not in raw or raw["Id"] is None:
            raise ValueError("A native identity is required for every returned record.")
        identity = raw["Id"]
        if kind == "agenda_item_text":
            if any(raw.get(k) is None or raw.get(k) == "" for k in ("MeetingId", "AgendaType", "LanguageId")):
                raise ValueError("The item text requires its native meeting, agenda type and language key.")
            identity = {k: raw[k] for k in ("MeetingId", "AgendaType", "Id", "LanguageId")}
        if isinstance(identity, dict):
            needed = {"agenda": ("MeetingId", "Type"), "agenda_item": ("MeetingId", "AgendaType", "Id"),
                      "attachment": ("MeetingId", "AgendaType", "AgendaItemId", "Sequence"),
                      "bookmark": ("MeetingId", "AgendaType", "AgendaItemId", "Id"),
                      "resolution": ("MeetingId", "AgendaItemId", "Sequence"),
                      "agenda_item_text": ("MeetingId", "AgendaType", "Id", "LanguageId"),
                      "meeting_type": ("Id", "PortalId")}[kind]
            if set(identity) != set(needed) or any(identity[k] is None or identity[k] == "" for k in needed):
                raise ValueError("Every component of the native compound identity is required.")
            identity_text = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        else:
            identity_text = str(identity)
        if method == "DocumentGetSince":
            if type(identity) is not int or not 0 < identity < 2**31 or identity in document_since_ids:
                raise ValueError("Document selector rows require unique positive native Int32 IDs.")
            document_since_ids.add(identity)
        if kind == "meeting_type":
            if identity_text in meeting_type_ids:
                raise ValueError("A meeting-type collection repeats its native compound identity.")
            meeting_type_ids.add(identity_text)
        normalized = {"external_id": identity_text, "url": source.url, "native_fields": deepcopy(raw),
                      "time_zone_status": "not_interpreted", "documents": [], "recordings": []}
        if kind == "meeting":
            normalized.update(title=raw.get("Name"), source_start=raw.get("Start"), source_end=raw.get("End"))
            if raw.get("VideoURL"):
                validate_url(raw["VideoURL"])
                normalized["recordings"] = [{"url": raw["VideoURL"], "availability": "supplied_reference_only"}]
        elif kind == "document":
            normalized["title"] = raw.get("DisplayName", raw.get("Name"))
        elif kind == "agenda_item_text":
            normalized["source_parent_identity"] = {k: raw[k] for k in ("MeetingId", "AgendaType", "Id")}
        elif kind == "package":
            if not isinstance(raw.get("MeetingId"), str) or not raw["MeetingId"]:
                raise ValueError("The package must supply its native meeting identity.")
            normalized["source_parent_identity"] = {"MeetingId": raw["MeetingId"]}
        else:
            normalized["source_parent_identity"] = deepcopy(raw["Id"])
        rows.append((normalized, raw, kind))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"]:
        raw = record["original"]
        kind = record["identity"]["record_type"]
        if kind in {"agenda", "agenda_item", "attachment"}:
            native = raw["Id"]
            parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                      "external_id": native["MeetingId"]}
            record["relationships"].append({"relation": "meeting", "identity": parent})
            if kind != "agenda":
                agenda = {"MeetingId": native["MeetingId"], "Type": native["AgendaType"]}
                record["relationships"].append({"relation": "agenda", "identity": {
                    **parent, "record_type": "agenda",
                    "external_id": json.dumps(agenda, sort_keys=True, separators=(",", ":"))}})
            if kind == "attachment":
                if type(native.get("AgendaItemId")) is int and native["AgendaItemId"] > 0:
                    item = {"MeetingId": native["MeetingId"], "AgendaType": native["AgendaType"],
                            "Id": native["AgendaItemId"]}
                    record["relationships"].append({"relation": "agenda_item", "identity": {
                        **parent, "record_type": "agenda_item",
                        "external_id": json.dumps(item, sort_keys=True, separators=(",", ":"))}})
                if type(raw.get("DocumentId")) is int and raw["DocumentId"] > 0:
                    record["relationships"].append({"relation": "document", "identity": {
                        **parent, "record_type": "document", "external_id": str(raw["DocumentId"])}})
        if kind == "agenda_item_text":
            item = {k: raw[k] for k in ("MeetingId", "AgendaType", "Id")}
            record["relationships"].append({"relation": "agenda_item", "identity": {
                "provider": source.provider, "namespace": namespace, "record_type": "agenda_item",
                "external_id": json.dumps(item, sort_keys=True, separators=(",", ":"))}})
        if kind in {"package", "bookmark", "resolution"}:
            meeting_id = raw["MeetingId"] if kind == "package" else raw["Id"]["MeetingId"]
            record["relationships"].append({"relation": "meeting", "identity": {
                "provider": source.provider, "namespace": namespace, "record_type": "meeting",
                "external_id": meeting_id}})
            if kind == "package":
                if type(raw.get("DocumentId")) is not int or raw["DocumentId"] <= 0:
                    raise ValueError("The package must supply a positive native document ID.")
                record["relationships"].append({"relation": "document", "identity": {
                    "provider": source.provider, "namespace": namespace, "record_type": "document",
                    "external_id": str(raw["DocumentId"])}})
            elif kind == "resolution":
                # Resolution.Identifier omits AgendaType; do not invent a complete item identity.
                record["relationships"].append({"relation": "agenda_item_reference", "value": {
                    "native_agenda_item_id": raw["Id"]["AgendaItemId"], "native_meeting_id": meeting_id,
                    "agenda_type_availability": "not_supplied_by_resolution_identifier"}})
                record["normalized"]["source_resolution"] = deepcopy(raw)
            else:
                item = {k: raw["Id"][k] for k in ("MeetingId", "AgendaType")}
                item["Id"] = raw["Id"]["AgendaItemId"]
                record["relationships"].append({"relation": "agenda_item", "identity": {
                    "provider": source.provider, "namespace": namespace, "record_type": "agenda_item",
                    "external_id": json.dumps(item, sort_keys=True, separators=(",", ":"))}})
                record["normalized"]["timing_units"] = "not_declared_by_pinned_schema"
        text = []
        for field in ("Name", "Description", "Title", "Header", "Minutes", "Comments", "Mintues"):
            value = raw.get(field)
            entries = value.get("KeyValueOfintstring", []) if isinstance(value, dict) else [value]
            for entry in entries:
                language_key = entry.get("Key") if isinstance(entry, dict) else (
                    raw["LanguageId"] if kind == "agenda_item_text" else None)
                literal = entry.get("Value") if isinstance(entry, dict) else entry
                if isinstance(literal, str) and literal:
                    text.append({"field": field, "text": literal, "citation_url": source.url,
                        "completeness": "supplied_source_field", "provenance": {
                            "method": "escribe_publishing_soap_field", "source_language_key": language_key,
                            "capture_sha256": bundle["capture"]["sha256"]}})
        record["text"] = text
        record["normalized_sha256"] = canonical_hash(record["normalized"])
    return bundle


def read(engine, source, namespace, request, bounds, context, transport, *, discover=False):
    operation = "discover" if discover else "fetch"
    if not context.allows(operation, namespace):
        raise ValueError("The source namespace is not authorized for this operation.")
    if bounds.checkpoint or bounds.date_from or bounds.date_to:
        raise ValueError("Select explicit native parameters; no paging/date semantics are inferred.")
    method = request.get("api_method")
    if method not in READS:
        raise ValueError("Select a mapped native record read.")
    parameters = request.get("api_parameters")
    if not isinstance(parameters, dict) or set(parameters) != {
            f["name"] for f in contract()["operations"][method]["request"]} or any(
                v is None for v in parameters.values()):
        raise ValueError("Supply every exact native selection parameter without nulls.")
    if method == "DocumentGetSince" and (type(parameters["intLastInsertedId"]) is not int
            or not 0 <= parameters["intLastInsertedId"] < 2**31):
        raise ValueError("Supply an explicit nonnegative native Int32 last-inserted ID.")
    if method == "AgendaItemItemHistoryView":
        from .escribe_history import bind_history
        bind_history(parameters, {"records": []})
    selected = next(iter(parameters.values()))
    selected_type = contract()["operations"][method]["request"][0]["type"]
    selected_fields = contract()["types"].get(selected_type, {}).get("fields")
    if selected_fields is not None and (not isinstance(selected, dict)
            or set(selected) != {f["name"] for f in selected_fields}
            or any(v is None or v == "" for v in selected.values())):
        raise ValueError("Every compound native identifier component must be explicit.")
    session = Session(source, context, bounds, transport, storage=engine.storage)
    bundle = None
    try:
        if method in {"DocumentGetContent", "DocumentGetContentChunk"}:
            if bounds.max_pages < 2 or type(parameters.get("Id")) is not int or parameters["Id"] <= 0:
                raise ValueError("Document metadata and content require two calls and a positive native document ID.")
            if method == "DocumentGetContentChunk" and (
                    type(parameters["offset"]) is not int or not 0 <= parameters["offset"] < 2 ** 31
                    or type(parameters["length"]) is not int or not 0 < parameters["length"] < 2 ** 31):
                raise ValueError("An explicit nonnegative native offset and positive native length are required.")
            document = {"Id": parameters["Id"]}
            value, content = session.call("DocumentGetById", document)
            candidate = parse_bundle(source, namespace, content)
            bind_records("DocumentGetById", document, candidate)
            if len(candidate["records"]) != 1:
                raise ValueError("The selected native document metadata is unavailable.")
            bundle = candidate
            value, raw_content = session.call(method, parameters)
            decoded = base64.b64decode(value, validate=True)
            record = bundle["records"][0]
            if method == "DocumentGetContentChunk":
                raw_capture = make_bundle(source, namespace, raw_content, FORMAT, [])["capture"]
                chunk_capture = make_bundle(source, namespace, decoded, "escribe-native-document-chunk", [])["capture"]
                bundle["captures"] = [raw_capture, chunk_capture]
                bundle["extensions"]["native_request_context"] = {
                    "api_method": method, "api_parameters": deepcopy(parameters)}
                record["normalized"].update(supplied_chunk_sha256=sha256(decoded).hexdigest(),
                    supplied_chunk_byte_length=len(decoded), native_chunk_parameters=deepcopy(parameters),
                    chunk_units="not_established_by_pinned_schema", chunk_assembly="not_performed",
                    document_complete=False, content_type="application/octet-stream",
                    content_type_availability="not_declared_by_pinned_content_method", text_availability="not_extracted")
                record["relationships"].append({"relation": "document_content_chunk", "value": {
                    "native_document_id": parameters["Id"], "capture_sha256": chunk_capture["sha256"],
                    "native_request_parameters": deepcopy(parameters), "binding": "explicit_request_context_not_response_echo"}})
                record["normalized_sha256"] = canonical_hash(record["normalized"])
                session.check()
                return OperationResult("partial", bundle, coverage={
                    "scope": "one native document metadata and explicitly requested chunk pair",
                    "api_method": method, "source_complete": False, "catalog_complete": False,
                    "document_complete": False, "pages": session.pages, "chunk_received": True,
                    "chunk_byte_length": len(decoded), "chunk_units": "not_established_by_pinned_schema",
                    "pagination": "not_inferred", "text_extracted": False}, operation_id=context.operation_id)
            if record["original"].get("FileSize") != len(decoded):
                raise ValueError("The content byte length does not match the exact native metadata.")
            raw_capture = make_bundle(source, namespace, raw_content, FORMAT, [])["capture"]
            byte_capture = make_bundle(source, namespace, decoded, "escribe-native-document-bytes", [])["capture"]
            bundle["captures"] = [raw_capture, byte_capture]
            record["normalized"].update(supplied_document_sha256=sha256(decoded).hexdigest(),
                supplied_document_byte_length=len(decoded), content_type="application/octet-stream",
                content_type_availability="not_declared_by_pinned_content_method", text_availability="not_extracted")
            record["relationships"].append({"relation": "document_content", "value": {
                "native_document_id": parameters["Id"], "capture_sha256": byte_capture["sha256"]}})
            record["normalized_sha256"] = canonical_hash(record["normalized"])
            session.check()
            return OperationResult("partial", bundle, coverage={"scope": "one native document metadata/content pair",
                "source_complete": False, "catalog_complete": False, "pages": session.pages,
                "document_content_received": True, "text_extracted": False}, operation_id=context.operation_id)
        value, content = session.call(method, parameters)
        if method == "MeetingAgendaItemsWithHistory":
            from .escribe_history import history_index_bundle
            bundle = history_index_bundle(source, namespace, content, value, parameters)
        else:
            bundle = parse_bundle(source, namespace, content)
            bind_records(method, parameters, bundle)
        if method == "DocumentGetSince":
            bundle["extensions"]["native_request_context"] = {
                "api_method": method, "api_parameters": deepcopy(parameters),
                "selection_semantics": "literal_vendor_selector; ordering/inclusion/continuation_not_inferred"}
        if sum(r["normalized"].get("source_component_count", 1) for r in bundle["records"]) > bounds.max_records:
            raise ValueError("The selected unpaged response exceeds max_records; it is not silently truncated.")
        session.check()
        return OperationResult("partial", bundle, coverage={"scope": "one explicit native SOAP method",
            "api_method": method, "source_complete": False, "catalog_complete": False,
            "pages": session.pages, "pagination": "not_inferred", "live_acceptance": "NOT_RUN"},
            operation_id=context.operation_id)
    except WriteCancelled:
        return OperationResult("cancelled", bundle, operation_id=context.operation_id)
    except (ValueError, TypeError, KeyError, OSError, ET.ParseError):
        return OperationResult("partial" if method in {"DocumentGetContent", "DocumentGetContentChunk"} and bundle else "failed",
            bundle if method in {"DocumentGetContent", "DocumentGetContentChunk"} else None, errors=(Error("publishing_read_unverified",
            "The exact PublishingService response could not be verified.", source=source.url),),
            operation_id=context.operation_id)
