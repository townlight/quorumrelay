"""Compile the scoped Publishing Service contract from checked-in vendor metadata."""
import io
import json
from pathlib import Path
from hashlib import sha256
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/capabilities/evidence/escribe-publishing-wsdl"
XSD = "http://www.w3.org/2001/XMLSchema"
WSDL = "http://schemas.xmlsoap.org/wsdl/"
SOAP12 = "http://schemas.xmlsoap.org/wsdl/soap12/"
NAMESPACE = "eSCRIBE.Internet.WebService"
MODELS = ("Meeting", "Agenda", "AgendaItem", "Attachment", "Document", "Package", "Bookmark", "Resolution")
READS = ("MeetingGetByPortal", "AgendaGetByMeeting", "AgendaItemGetByAgenda",
         "AttachmentGetByAgenda", "AttachmentGetByAgendaItem", "DocumentGetContent",
         "PackageGetByMeeting", "BookmarkGetByMeeting", "BookmarkGetByAgenda",
         "ResolutionGetByMeeting", "ResolutionGetByAgendaItem",
         "MeetingGetByMeetingType", "AgendaItemTextGetByMeetingId")


def compile_contract():
    types, elements, hashes = {}, {}, {}
    for path in sorted(EVIDENCE.glob("*.xsd")):
        content = path.read_bytes()
        hashes[path.name] = sha256(content).hexdigest()
        prefixes = dict(pair for _, pair in ET.iterparse(io.BytesIO(content), events=["start-ns"]))
        root = ET.fromstring(content)
        namespace = root.attrib["targetNamespace"]

        def qualified(value):
            prefix, name = value.split(":")
            return "{" + prefixes[prefix] + "}" + name

        def fields(node):
            result = []
            for e in node.findall("./{" + XSD + "}sequence/{" + XSD + "}element"):
                if "type" in e.attrib:
                    kind = qualified(e.attrib["type"])
                else:
                    inline = e.find("{" + XSD + "}complexType")
                    if inline is None:
                        raise ValueError("Unsupported anonymous schema type.")
                    def structural(node):
                        return [node.tag, sorted(node.attrib.items()), node.text or "",
                                [structural(child) for child in node]]
                    kind = "{" + namespace + "}inline/" + sha256(json.dumps(structural(e)).encode()).hexdigest()
                    types[kind] = {"fields": fields(inline)}
                result.append({"name": e.attrib["name"], "type": kind,
                               "namespace": namespace, "optional": e.attrib.get("minOccurs") == "0",
                               "nullable": e.attrib.get("nillable") == "true",
                               "many": e.attrib.get("maxOccurs") == "unbounded"})
            return result

        for node in root:
            name = node.attrib.get("name")
            if not name:
                continue
            key = "{" + namespace + "}" + name
            if node.tag == "{" + XSD + "}complexType":
                sequence = node.find("{" + XSD + "}sequence")
                if sequence is not None:
                    types[key] = {"fields": fields(node)}
            elif node.tag == "{" + XSD + "}simpleType":
                restriction = node.find("{" + XSD + "}restriction")
                if restriction is not None:
                    types[key] = {"base": qualified(restriction.attrib["base"])}
            elif node.tag == "{" + XSD + "}element" and namespace == NAMESPACE:
                value = node.find("{" + XSD + "}complexType")
                if value is not None:
                    elements[name] = fields(value)
    content = (EVIDENCE / "publishing.wsdl").read_bytes()
    hashes["publishing.wsdl"] = sha256(content).hexdigest()
    root = ET.fromstring(content)
    methods = set(READS) | {model + suffix for model in MODELS
                           for suffix in ("Create", "Update", "GetById", "Exists")}
    # Upload request shape is retained for attribution; chunk semantics are not inferred.
    methods.add("DocumentUpload")
    operations = {}
    for node in root.findall("./{" + WSDL + "}binding/{" + WSDL + "}operation"):
        name = node.attrib["name"]
        if name in methods:
            operations[name] = {"action": node.find("{" + SOAP12 + "}operation").attrib["soapAction"],
                                "request": elements[name], "response": elements[name + "Response"]}
    needed = set()

    def keep(key):
        if key not in types or key in needed:
            return
        needed.add(key)
        value = types[key]
        if "base" in value:
            keep(value["base"])
        for field in value.get("fields", []):
            keep(field["type"])

    for operation in operations.values():
        for field in operation["request"] + operation["response"]:
            keep(field["type"])
    return {"namespace": NAMESPACE, "metadata_sha256": hashes,
            "binding": "SOAP1.2 HTTPS with WS-Addressing2005/08; no client certificate required by pinned policy",
            "operations": operations, "types": {key: types[key] for key in sorted(needed)}}


if __name__ == "__main__":
    path = ROOT / "src/civic_data_connectors/data/escribe_publishing.json"
    path.write_bytes((json.dumps(compile_contract(), indent=2, ensure_ascii=True) + "\n").replace("\n", "\r\n").encode())
