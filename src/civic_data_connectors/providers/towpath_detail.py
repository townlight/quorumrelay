"""Rich fields from supplied Digital Towpath meeting detail HTML only."""

import base64
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import re
from urllib.parse import urlsplit

from ..engine import canonical_hash
from .escribe_detail import Page


def enrich_bundle(bundle):
    result = deepcopy(bundle)
    capture = result["capture"]
    url = capture["source_url"]
    match = re.fullmatch(r"/meetings/detail/(\d+)/?", urlsplit(url).path)
    if not match or capture["input_format"] != "digital-towpath-detail-html":
        return result
    content = base64.b64decode(capture["content_base64"], validate=True)
    digest = sha256(content).hexdigest()
    if digest != capture["sha256"]:
        raise ValueError("Digital Towpath detail capture hash mismatch.")
    page = Page()
    page.feed(content.decode("utf-8", errors="replace"))

    def field(name):
        nodes = [n for n in page.root.walk() if "dtp-meeting-" + name in n.classes()]
        if len(nodes) > 1:
            raise ValueError("Digital Towpath detail has ambiguous supplied fields.")
        return nodes[0] if nodes else None

    fields = {}
    for name in ("category", "venue", "address1", "address2", "zipcode", "description"):
        node = field(name)
        if node is not None:
            fields[name] = {"text": node.text(), "attributes": dict(node.attrs)}
    times = [n for n in page.root.walk() if n.tag == "time" and n.attrs.get("datetime")]
    temporal = {}
    if len(times) == 1:
        node = times[0]
        temporal = {"source_date": node.attrs["datetime"], "source_time_label": node.text(),
                    "time_zone_status": "unknown"}
        try:
            value = datetime.strptime(node.text(), "%B %d, %Y, %I:%M %p")
        except ValueError:
            pass
        else:
            if value.date().isoformat() == node.attrs["datetime"]:
                temporal["source_start"] = value.isoformat()
    states = {}
    for name in ("agenda", "minutes"):
        node = field(name)
        if node is not None:
            states[name] = node.parent.text()
    for record in result["records"]:
        if (record["identity"]["external_id"] != match[1]
                or record["source_url"] != url or record["capture_sha256"] != digest):
            raise ValueError("Digital Towpath meeting disagrees with its capture identity.")
        normalized = record["normalized"]
        normalized.update(temporal, supplied_detail_fields=deepcopy(fields),
                          source_document_states=states)
        if fields.get("category", {}).get("text"):
            normalized["category"] = fields["category"]["text"]
        location = [fields[name]["text"] for name in ("venue", "address1", "address2", "zipcode")
                    if fields.get(name, {}).get("text")]
        if location:
            normalized["location"] = ", ".join(location)
        description = fields.get("description", {}).get("text", "")
        normalized["description"] = description
        record["text"] = [s for s in record.get("text", [])
                          if s.get("provenance", {}).get("method") != "towpath_supplied_description"]
        if description:
            record["text"].append({"field": "description", "text": description,
                "citation_url": url, "completeness": "supplied_description_only",
                "provenance": {"method": "towpath_supplied_description", "capture_sha256": digest,
                               "selector": ".dtp-meeting-description"}})
        record["normalized_sha256"] = canonical_hash(normalized)
    return result
