"""Public FilePro SOAP reads pinned to CivicWeb's supplied document-service WSDL.

This binding never logs in or carries a cookie. It implements document reads,
not calendar/meeting mutation or a deployment-independent compatibility claim.
"""

import base64
import binascii
from functools import lru_cache
from importlib.resources import files
import json
import re
from time import monotonic
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .contracts import RetrievalError, _origin
from .identification import validate_url

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS = "http://civicweb.net/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("soap", SOAP)
ET.register_namespace("cw", NS)


@lru_cache(maxsize=1)
def contract():
    return json.loads(files("civic_data_connectors.data").joinpath("civicweb_filepro.json").read_text())


def _integer(value):
    if type(value) is not int or not -(2**31) <= value < 2**31:
        raise ValueError("A FilePro Int32 value is required.")
    return str(value)


def _encode(parent, value, kind):
    if kind == "int":
        parent.text = _integer(value)
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("A FilePro boolean is required.")
        parent.text = "true" if value else "false"
    elif kind == "string":
        if not isinstance(value, str) or any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise ValueError("A valid FilePro string is required.")
        parent.text = value
    elif kind == "ArrayOfInt":
        if not isinstance(value, list) or len(value) > 50 or len(set(map(str, value))) != len(value):
            raise ValueError("FilePro detail batches require at most 50 distinct document IDs.")
        for identity in value:
            if type(identity) is not int or identity <= 0:
                raise ValueError("Positive document IDs are required.")
            ET.SubElement(parent, f"{{{NS}}}int").text = _integer(identity)
    else:
        raise ValueError("An explicitly supported FilePro request type is required.")


def request_xml(method, parameters, *, byte_limit):
    operation = contract()["operations"].get(method)
    if operation is None or not isinstance(parameters, dict):
        raise ValueError("An explicitly supported public document read is required.")
    fields = operation["request"]
    if set(parameters) != {f["name"] for f in fields}:
        raise ValueError("FilePro requests require the exact pinned method fields.")
    if method == "GetChildList" and (parameters["path"] != "" or parameters["controlId"] != ""
            or parameters["documentProvider"] != "iCompass.CivicWeb.Items.DocumentProvider"):
        raise ValueError("FilePro child listing requires the documented fixed provider/empty state.")
    for name in ("id", "documentId", "meetingId"):
        if name in parameters and (type(parameters[name]) is not int or parameters[name] < 0
                or (name != "id" or method != "GetChildList") and parameters[name] == 0):
            raise ValueError("The documented supplied document/folder/meeting identity is required.")
    root = ET.Element(f"{{{SOAP}}}Envelope")
    body = ET.SubElement(root, f"{{{SOAP}}}Body")
    node = ET.SubElement(body, f"{{{NS}}}{method}")
    for field in fields:
        _encode(ET.SubElement(node, f"{{{NS}}}{field['name']}"), parameters[field["name"]], field["type"])
    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(raw) > byte_limit:
        raise ValueError("FilePro request exceeds its byte bound.")
    return raw, {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"' + operation["soap_action"] + '"'}


def _decode(node, kind, depth=0):
    if depth > 32:
        raise ValueError("FilePro response exceeds its nesting bound.")
    if node.get(f"{{{XSI}}}nil") in {"true", "1"}:
        if len(node) or (node.text or "").strip():
            raise ValueError("A nil FilePro value cannot contain data.")
        return None
    text = node.text or ""
    if kind in {"string", "int", "boolean", "base64Binary"}:
        if len(node):
            raise ValueError("A FilePro scalar cannot contain child elements.")
        if kind == "string":
            return text
        if kind == "int":
            if not re.fullmatch(r"-?[0-9]+", text):
                raise ValueError("Invalid FilePro Int32 response.")
            value = int(text)
            _integer(value)
            return value
        if kind == "boolean":
            if text not in {"true", "false", "1", "0"}:
                raise ValueError("Invalid FilePro boolean response.")
            return text in {"true", "1"}
        try:
            value = base64.b64decode(re.sub(r"\s+", "", text), validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid FilePro base64 file bytes.") from error
        # Public captures/records remain JSON serializable and retain exact bytes.
        return base64.b64encode(value).decode("ascii")
    fields = contract()["types"].get(kind)
    if fields is None:
        # Preserve additive vendor XML without inventing semantics or emitting HTML.
        return {"xml": ET.tostring(node, encoding="unicode")}
    array = len(fields) == 1 and fields[0]["array"]
    known = {f["name"]: f for f in fields}
    result = [] if array else {}
    for child in node:
        if not child.tag.startswith("{" + NS + "}"):
            raise ValueError("FilePro response contains a foreign field namespace.")
        name = child.tag.split("}", 1)[1]
        field = known.get(name)
        if array:
            if field is None:
                raise ValueError("Unexpected FilePro collection member.")
            result.append(_decode(child, field["type"], depth + 1))
        else:
            if name in result:
                raise ValueError("Duplicate FilePro response field.")
            result[name] = _decode(child, field["type"] if field else None, depth + 1)
    if not array and any(not f["optional"] and f["name"] not in result for f in fields):
        raise ValueError("FilePro response lacks a required vendor field.")
    return result


def response_value(method, content, *, byte_limit):
    if method not in contract()["operations"] or not isinstance(content, bytes) or len(content) > byte_limit:
        raise ValueError("An explicitly supported bounded FilePro response is required.")
    if b"\0" in content or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("Unsupported FilePro XML encoding or declaration.")
    root = ET.fromstring(content)
    if root.tag != f"{{{SOAP}}}Envelope" or sum(1 for _ in root.iter()) > 100000:
        raise ValueError("Invalid or excessive FilePro SOAP envelope.")
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > 40:
            raise ValueError("FilePro XML exceeds its nesting bound.")
        stack.extend((child, depth + 1) for child in node)
    bodies = root.findall(f"{{{SOAP}}}Body")
    if len(bodies) != 1 or len(bodies[0]) != 1 or bodies[0][0].tag != f"{{{NS}}}{method}Response":
        raise ValueError("FilePro SOAP fault or unexpected method response.")
    fields = contract()["operations"][method]["response"]
    node = bodies[0][0]
    if len(node) == 0:
        if all(f["optional"] for f in fields):
            return None
        raise ValueError("Missing required FilePro response.")
    if len(node) != 1 or node[0].tag != f"{{{NS}}}{fields[0]['name']}":
        raise ValueError("Unexpected FilePro result field.")
    return _decode(node[0], fields[0]["type"])


class PublicClient:
    """One bounded operation's public document transport; no authenticated session."""

    def __init__(self, source, bounds, context, transport):
        validate_url(source.url)
        parsed = urlsplit(source.url)
        if (source.provider != "civicweb" or parsed.scheme != "https" or parsed.username or parsed.password
                or not re.fullmatch(r"[^.]+\.civicweb\.net", parsed.hostname or "")):
            raise ValueError("An exact configured CivicWeb HTTPS tenant is required.")
        self.url = _origin(source.url) + "/Global/WebServices/Document.asmx"
        self.bounds, self.context, self.transport = bounds, context, transport
        self.started, self.transferred = monotonic(), 0

    def call(self, method, parameters):
        if self.context.check_cancelled():
            raise RetrievalError("cancelled")
        remaining = self.bounds.deadline_seconds - (monotonic() - self.started)
        if remaining <= 0:
            raise RetrievalError("provider_deadline_exceeded")
        raw, headers = request_xml(method, parameters, byte_limit=self.bounds.parser_bytes)
        budget = self.bounds.transfer_bytes - self.transferred - len(raw)
        if budget <= 0:
            raise RetrievalError("transfer_bytes_exceeded")
        response = self.transport.request(self.url, method="POST", body=raw, headers=headers,
            byte_limit=min(self.bounds.parser_bytes, budget), deadline_seconds=remaining,
            allowed_origins=(_origin(self.url),), allow_redirects=False)
        self.transferred += len(raw) + len(response.content)
        if self.context.check_cancelled():
            raise RetrievalError("cancelled")
        if monotonic() - self.started >= self.bounds.deadline_seconds:
            raise RetrievalError("provider_deadline_exceeded")
        if (response.status != 200 or response.url != self.url
                or self.transferred > self.bounds.transfer_bytes):
            raise RetrievalError("civicweb_soap_unavailable")
        value = response_value(method, response.content, byte_limit=min(self.bounds.parser_bytes, budget))
        return value, response.content
