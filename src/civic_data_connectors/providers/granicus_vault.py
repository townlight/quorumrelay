"""Pinned MediaVault document/literal contract; private session impersonation only."""

import base64
from functools import lru_cache
from importlib.resources import files
import re
from time import monotonic
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .granicus_soap import SOAP, _scalar

NAMESPACE = "http://granicus.com/MediaVault/SDK"


@lru_cache(maxsize=1)
def contract():
    import json
    return json.loads(files("civic_data_connectors.data").joinpath("granicus_vault.json").read_text())


def request_xml(operation, parameters, *, service_host, token, byte_limit):
    definition = contract()["operations"].get(operation)
    if definition is None or not isinstance(parameters, dict) or set(parameters) != set(definition["request"]):
        raise ValueError("Supply exactly the documented MediaVault parameters.")
    root = ET.Element(f"{{{SOAP}}}Envelope")
    security = ET.SubElement(ET.SubElement(root, f"{{{SOAP}}}Header"), f"{{{NAMESPACE}}}SecurityHeader")
    for name, value in (("ServiceHost", service_host), ("SecurityToken", token)):
        ET.SubElement(security, f"{{{NAMESPACE}}}{name}").text = _scalar(value, "string")
    method = ET.SubElement(ET.SubElement(root, f"{{{SOAP}}}Body"), f"{{{NAMESPACE}}}{operation}")
    for name, datatype in definition["request"].items():
        value = parameters[name]
        kind = datatype.split(":")[-1]
        if kind == "long":
            if type(value) is not int or not -(2**63) <= value < 2**63:
                raise ValueError("A documented Int64 is required.")
            text = str(value)
        elif kind == "base64Binary":
            if not isinstance(value, bytes):
                raise ValueError("MediaVault bytes must be exact immutable file bytes.")
            text = base64.b64encode(value).decode("ascii")
        else:
            text = _scalar(value, kind)
        ET.SubElement(method, f"{{{NAMESPACE}}}{name}").text = text
    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(raw) > byte_limit:
        raise ValueError("The MediaVault request exceeds the configured byte bound.")
    return raw, {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"' + definition["soap_action"] + '"'}


def response_value(operation, raw, *, byte_limit):
    if (not isinstance(raw, bytes) or len(raw) > byte_limit or b"\0" in raw
            or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I)):
        raise ValueError("The MediaVault XML response is outside bounds.")
    root = ET.fromstring(raw)
    if root.tag != f"{{{SOAP}}}Envelope" or sum(1 for _ in root.iter()) > 256:
        raise ValueError("Invalid MediaVault SOAP envelope.")
    body = root.find(f"{{{SOAP}}}Body")
    if body is None or body.find(f"{{{SOAP}}}Fault") is not None or len(body) != 1:
        raise ValueError("MediaVault returned no exact response or a fault.")
    result = body.find(f"{{{NAMESPACE}}}{operation}Response")
    expected = contract()["operations"][operation]["response"]
    if result is None or [node.tag for node in result] != [f"{{{NAMESPACE}}}{name}" for name in expected]:
        raise ValueError("MediaVault response parameters differ from the pinned WSDL.")
    values = {}
    for node, (name, datatype) in zip(result, expected.items()):
        if len(node):
            raise ValueError("The documented MediaVault return is primitive, not a nested object.")
        text, kind = node.text or "", datatype.split(":")[-1]
        if kind in {"int", "long"}:
            value = int(text)
            if not -(2**(31 if kind == "int" else 63)) <= value < 2**(31 if kind == "int" else 63):
                raise ValueError("MediaVault integer result is outside the documented range.")
            values[name] = value
        else:
            values[name] = text
    return values


class VaultSession:
    """Shares one live private Platform session; never stores a token in a plan."""

    def __init__(self, platform, folder_id):
        self.platform, self.folder_id = platform, folder_id
        self._url, self._token = None, None

    def _connect(self):
        platform = self.platform
        if not platform._logged_in:
            platform._call("Login", {"Username": platform._config["username"],
                                    "Password": platform._config["password"]}, private=True)
            platform._logged_in = True
        value, _ = platform._call("GetFolderUploadInterface", {"FolderID": self.folder_id}, private=True)
        interface = next(iter(value.values()))
        origin = platform._config.get("media_origin")
        parsed = urlsplit(origin) if isinstance(origin, str) else None
        supplied = interface.get("Host") if isinstance(interface, dict) else None
        host = urlsplit(supplied if isinstance(supplied, str) and "://" in supplied else "https://" + str(supplied))
        if (parsed is None or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or parsed.hostname != host.hostname or (parsed.port or 443) != interface.get("ControlPort")
                or not re.fullmatch(r"[A-Za-z0-9-]+\.granicus\.com", parsed.hostname)):
            raise ValueError("MediaVault requires an explicit HTTPS origin matching the supplied folder interface.")
        tokens = [cookie.value for cookie in platform.jar if cookie.name == "PHPSESSID"]
        if len(tokens) != 1 or not tokens[0]:
            raise ValueError("The SDK requires the current private PHPSESSID impersonation token.")
        self._token, self._url = tokens[0], origin.rstrip("/") + contract()["endpoint_path"]

    def call(self, operation, parameters):
        platform = self.platform
        if "FolderID" in parameters and parameters["FolderID"] != self.folder_id:
            raise ValueError("The upload folder differs from its private interface binding.")
        if platform.context.check_cancelled() or monotonic() >= platform.deadline:
            raise ValueError("The MediaVault operation stopped before the next request.")
        try:
            if self._url is None:
                self._connect()
            raw, headers = request_xml(operation, parameters,
                service_host=urlsplit(platform.url).hostname, token=self._token,
                byte_limit=platform.bounds.transfer_bytes)
            remaining = platform.bounds.transfer_bytes - platform.transferred
            if remaining <= 0 or platform.context.check_cancelled() or monotonic() >= platform.deadline:
                raise ValueError("MediaVault transfer/time/cancellation budget exhausted.")
            response = platform.transport.request(self._url, method="POST", body=raw, headers=headers,
                byte_limit=min(platform.bounds.parser_bytes, remaining),
                deadline_seconds=max(0.001, platform.deadline-monotonic()),
                allowed_origins=(self._url.removesuffix(contract()["endpoint_path"]),), allow_redirects=False)
            platform.requests += 1
            platform.transferred += len(response.content)
            if (response.status != 200 or response.url != self._url or len(response.content) > remaining
                    or monotonic() >= platform.deadline):
                raise ValueError("MediaVault response outside exact-origin/bounds policy.")
            value = response_value(operation, response.content, byte_limit=platform.bounds.parser_bytes)
            # Even a hostile server must not reflect its private token into a receipt.
            if any(secret in str(value) for secret in (self._token, platform._config["username"], platform._config["password"])):
                raise ValueError("Private session material cannot enter a result.")
            return value
        except Exception:
            raise ValueError("The exact-origin MediaVault operation could not be verified.") from None

    def close(self):
        self._token = None
        self._url = None
