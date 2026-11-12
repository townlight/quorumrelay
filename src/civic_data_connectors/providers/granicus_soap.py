"""Bounded SOAP 1.1 binding for the pinned official Granicus Platform SDK.

This module has no login side effects. Credentials and session cookies belong to
the caller's private transport, never to serialized change plans or captures.
"""

import base64
import binascii
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from http.cookiejar import CookieJar
import json
import re
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request
import xml.etree.ElementTree as ET

SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
ENC = "http://schemas.xmlsoap.org/soap/encoding/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://www.w3.org/2001/XMLSchema"
MODEL = "http://granicus.com/xsd"
RPC = "urn:UserSDK"
for prefix, namespace in (("soap", SOAP), ("enc", ENC), ("xsi", XSI), ("g", MODEL), ("rpc", RPC)):
    ET.register_namespace(prefix, namespace)


@lru_cache(maxsize=1)
def contract():
    return json.loads(files("civic_data_connectors.data").joinpath("granicus_platform.json").read_text())


def _scalar(value, kind):
    if kind == "string":
        if not isinstance(value, str) or any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise ValueError("A documented SOAP string is required.")
        return value
    if kind == "int":
        if type(value) is not int or not -(2**31) <= value < 2**31:
            raise ValueError("A documented SOAP Int32 is required.")
        return str(value)
    if kind == "boolean":
        if type(value) is not bool:
            raise ValueError("A documented SOAP boolean is required.")
        return "true" if value else "false"
    if kind == "dateTime":
        if not isinstance(value, str):
            raise ValueError("A documented SOAP dateTime is required.")
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    if kind == "base64Binary":
        if not isinstance(value, str):
            raise ValueError("SOAP file content requires a base64 string.")
        try:
            base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid SOAP base64 content.") from error
        return value
    raise ValueError("An explicit supported SOAP field type is required.")


def _encode(element, value, type_name, depth=0):
    if depth > 32:
        raise ValueError("SOAP value nesting exceeds the binding limit.")
    prefix, kind = type_name.split(":", 1)
    if value is None:
        element.set(f"{{{XSI}}}nil", "true")
        return
    if prefix == "xsd":
        if kind == "anyType":
            # The official metadata Payload is extensible. Never guess its
            # vendor object schema; callers must supply a primitive explicitly.
            if type(value) is bool:
                kind = "boolean"
            elif type(value) is int:
                kind = "int"
            elif isinstance(value, str):
                kind = "string"
            else:
                raise ValueError("Untyped SOAP Payload objects are not inferred.")
        element.set(f"{{{XSI}}}type", "xsd:" + kind)
        element.text = _scalar(value, kind)
        return
    model = contract()["types"].get(kind)
    if model is None:
        raise ValueError("The SOAP model is absent from the pinned WSDL.")
    if "array" in model:
        if not isinstance(value, list):
            raise ValueError("A documented SOAP collection requires an array.")
        child_type = model["array"]
        element.set(f"{{{XSI}}}type", "enc:Array")
        element.set("enc:arrayType", child_type.replace("ns5:", "g:") + f"[{len(value)}]")
        for item in value:
            _encode(ET.SubElement(element, "item"), item, child_type, depth + 1)
        return
    if not isinstance(value, dict) or set(value) - set(model["fields"]):
        raise ValueError("SOAP objects accept only the pinned vendor fields.")
    element.set(f"{{{XSI}}}type", "g:" + kind)
    for key, item in value.items():
        _encode(ET.SubElement(element, key), item, model["fields"][key], depth + 1)


def request_xml(operation, parameters, *, byte_limit):
    definition = contract()["operations"].get(operation)
    if definition is None or not isinstance(parameters, dict) or set(parameters) != set(definition["request"]):
        raise ValueError("Supply exactly the documented in-domain SOAP method parameters.")
    envelope = ET.Element(f"{{{SOAP}}}Envelope", {"xmlns:xsd": XSD, "xmlns:g": MODEL, "xmlns:enc": ENC})
    body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
    call = ET.SubElement(body, f"{{{RPC}}}{operation}", {f"{{{SOAP}}}encodingStyle": ENC})
    for name, kind in definition["request"].items():
        _encode(ET.SubElement(call, name), parameters[name], kind)
    raw = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
    if len(raw) > byte_limit:
        raise ValueError("The encoded SOAP request exceeds its byte limit.")
    return raw, {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"' + definition["soap_action"] + '"'}


def response_value(operation, raw, *, byte_limit):
    """Decode inline and SOAP-encoded id/href values without resolving URLs."""
    if (operation not in contract()["operations"] or not isinstance(raw, bytes)
            or len(raw) > byte_limit or b"\0" in raw
            or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I)):
        raise ValueError("The SOAP response is outside the bounded XML contract.")
    root = ET.fromstring(raw)
    nodes = list(root.iter())
    if root.tag != f"{{{SOAP}}}Envelope" or len(nodes) > 20000:
        raise ValueError("Invalid or oversized SOAP envelope.")
    ids = {}
    for node in nodes:
        if key := node.get("id"):
            if key in ids:
                raise ValueError("SOAP references must have unique IDs.")
            ids[key] = node
    body = root.find(f"{{{SOAP}}}Body")
    if body is None or body.find(f"{{{SOAP}}}Fault") is not None:
        raise ValueError("The provider returned a SOAP fault or no response body.")
    result = body.find(f"{{{RPC}}}{operation}Response")
    if result is None:
        raise ValueError("The SOAP response does not match the requested method.")

    def decode(node, active=(), depth=0):
        if depth > 32:
            raise ValueError("SOAP response nesting exceeds the binding limit.")
        if href := node.get("href"):
            if not href.startswith("#") or href[1:] not in ids or href in active:
                raise ValueError("External, missing or cyclic SOAP reference.")
            return decode(ids[href[1:]], (*active, href), depth + 1)
        if node.get(f"{{{XSI}}}nil") in {"true", "1"}:
            return None
        children = list(node)
        if node.get(f"{{{ENC}}}arrayType") is not None:
            return [decode(child, active, depth + 1) for child in children]
        if children:
            value = {}
            for child in children:
                key = child.tag.rsplit("}", 1)[-1]
                if key in value:
                    raise ValueError("Duplicate SOAP object field.")
                value[key] = decode(child, active, depth + 1)
            return value
        text = node.text or ""
        kind = node.get(f"{{{XSI}}}type", "").split(":")[-1]
        if kind == "int":
            value = int(text)
            _scalar(value, kind)
            return value
        if kind == "boolean":
            if text not in {"true", "false", "1", "0"}:
                raise ValueError("Invalid SOAP boolean response.")
            return text in {"true", "1"}
        return text

    expected = contract()["operations"][operation]["response"]
    if {node.tag.rsplit("}", 1)[-1] for node in result} != set(expected):
        raise ValueError("SOAP return parameters differ from the pinned WSDL.")
    return {node.tag.rsplit("}", 1)[-1]: decode(node) for node in result}


class Session:
    """One operation's private, exact-origin SOAP session; never persist it."""

    def __init__(self, source, context, bounds, transport, *, deadline=None):
        from .novus import _cookies
        self._cookies = _cookies
        parsed = urlsplit(source.url)
        self.origin = f"https://{parsed.hostname}"
        config = context.credentials.get("granicus")
        if (source.provider != "granicus" or parsed.scheme != "https" or parsed.username
                or parsed.password or parsed.port not in {None, 443} or parsed.query or parsed.fragment
                or not re.fullmatch(r"[A-Za-z0-9-]+\.granicus\.com", parsed.hostname or "")
                or not source.namespace or not context.tenant or not isinstance(config, dict)
                or config.get("tenant") != context.tenant or config.get("origin") != self.origin
                or source.namespace not in config.get("allowed_namespaces", [config.get("namespace")])
                or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)):
            raise ValueError("Granicus SOAP policy must bind the exact host, tenant and source namespace.")
        if any(not isinstance(config.get(k), str) or not config[k]
               or any(c in config[k] for c in "\r\n\0") for k in ("username", "password")):
            raise ValueError("A private SOAP transport configuration is required.")
        self.url = self.origin + contract()["endpoint_path"]
        self.context, self.bounds, self.transport = context, bounds, transport
        self.deadline = deadline if deadline is not None else monotonic() + bounds.deadline_seconds
        self.jar, self.transferred, self.requests = CookieJar(), 0, 0
        self._config, self._logged_in = config, False

    def _call(self, operation, parameters, *, private=False):
        if self.context.check_cancelled() or monotonic() >= self.deadline:
            raise ValueError("The bounded SOAP operation stopped before its next request.")
        remaining_bytes = self.bounds.transfer_bytes - self.transferred
        if remaining_bytes <= 0:
            raise ValueError("The SOAP transfer byte limit was reached.")
        raw, headers = request_xml(operation, parameters, byte_limit=self.bounds.transfer_bytes)
        request = Request(self.url)
        self.jar.add_cookie_header(request)
        if request.has_header("Cookie"):
            headers["Cookie"] = request.get_header("Cookie")
        try:
            response = self.transport.request(self.url, method="POST", body=raw, headers=headers,
                byte_limit=min(self.bounds.parser_bytes, remaining_bytes),
                deadline_seconds=max(0.001, self.deadline - monotonic()),
                allowed_origins=(self.origin,), allow_redirects=False)
            self.requests += 1
            self.transferred += len(response.content)
            if (response.status != 200 or response.url != self.url
                    or self.transferred > self.bounds.transfer_bytes or monotonic() >= self.deadline):
                raise ValueError("SOAP response outside bounds.")
            value = response_value(operation, response.content, byte_limit=self.bounds.parser_bytes)
            if not private:
                decoded = json.dumps(value, ensure_ascii=False)
                secrets = [self._config[k] for k in ("username", "password")]
                secrets.extend(cookie.value for cookie in self.jar if cookie.value)
                if any(secret in decoded for secret in secrets):
                    raise ValueError("Credential material cannot become a source capture.")
            self._cookies(self.jar, response, self.url)
            return value, response.content
        except Exception:
            # SOAP fault strings and transport failures can contain secrets.
            raise ValueError("The exact-origin SOAP response could not be verified.") from None

    def call(self, operation, parameters):
        if operation in {"Login", "Logout"}:
            raise ValueError("Session operations are private transport steps.")
        if not self._logged_in:
            self._call("Login", {"Username": self._config["username"],
                                 "Password": self._config["password"]}, private=True)
            self._logged_in = True
        return self._call(operation, parameters)

    def close(self):
        try:
            if self._logged_in and not self.context.check_cancelled() and monotonic() < self.deadline:
                self._call("Logout", {}, private=True)
        finally:
            self.jar.clear()
            self._logged_in = False
