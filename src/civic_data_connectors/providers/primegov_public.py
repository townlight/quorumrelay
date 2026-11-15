"""Pinned public portal document and speaker-request outline read contracts."""

from copy import deepcopy
import json
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit

from ..engine import source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .identification import validate_url
from .native import make_bundle


def _positive(v):
    return type(v) is int and 0 < v <= 9999999999999999999


def documents(source, raw):
    """Mirror getHref's native identifier branches, without changing legacy output."""
    result, unmapped = [], 0
    for doc in raw.get("documentList", []):
        if (not isinstance(doc, dict) or not _positive(doc.get("id"))
                or doc.get("meetingId") != raw.get("id")):
            unmapped += 1
            continue
        template, output = doc.get("templateId"), doc.get("compileOutputType")
        locator = doc.get("link")
        locator_identity = "source_link"
        if locator is None:
            vote_summary = template is None or (type(template) is int and template <= 0)
            if (not vote_summary and not _positive(template)) or type(output) is not int or output not in {1, 2, 3}:
                unmapped += 1
                continue
            parameter = {"compiledMeetingDocumentFileId" if vote_summary else "meetingTemplateId":
                         doc["id"] if vote_summary else template}
            locator_identity = next(iter(parameter))
            path = "/Portal/Meeting?" if output == 3 else "/Public/CompiledDocument?"
            if output != 3:
                parameter["compileOutputType"] = output
            locator = _origin(source.url) + path + urlencode(parameter)
        elif not isinstance(locator, str) or not locator:
            unmapped += 1
            continue
        locator = urljoin(source.url, locator)
        try:
            validate_url(locator)
        except ValueError:
            unmapped += 1
            continue
        title = doc.get("templateName")
        label = title.casefold() if isinstance(title, str) else ""
        kind = next((k for k in ("cancel", "minutes", "packet", "agenda") if k in label), "attachment")
        result.append({"external_id": str(doc["id"]), "kind": kind, "title": title,
            "url": locator, "citation_url": locator, "published_at": doc.get("publishDate"),
            "availability": "vendor_client_locator_not_fetched", "source_metadata": {
                "template_id": template, "compile_output_type": output, "language": doc.get("language"),
                "publish_status": doc.get("publishStatus"), "locator_identity": locator_identity,
                "source_fields": deepcopy(doc)}})
    return result, unmapped


def outline_bundle(source, namespace, content, meeting, kind, maximum):
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError("Public outline response must be a section array.")
    rows, seen = [], set()
    citation = _origin(source.url) + "/Portal/Meeting?" + urlencode({"meetingId": meeting})
    for section in payload:
        if (not isinstance(section, dict) or not _positive(section.get("id"))
                or section.get("meetingId") != int(meeting) or not isinstance(section.get("name"), str)
                or not section["name"].strip() or not isinstance(section.get("items"), list)):
            raise ValueError("Public section identity/meeting/name/items changed.")
        native_id = str(section["id"])
        if ("agenda_section", native_id) in seen:
            raise ValueError("Repeated section native identity.")
        seen.add(("agenda_section", native_id))
        rows.append(({"external_id": native_id, "title": section["name"], "url": citation,
            "meeting_external_id": meeting, "source_number": section.get("number"),
            "source_meeting_section_id": section.get("meetingSectionId"),
            "content_availability": "public_speaker_request_outline_only"}, section, "agenda_section"))
        for item in section["items"]:
            if (not isinstance(item, dict) or not _positive(item.get("id"))
                    or not isinstance(item.get("titleDisplayField"), str) or not item["titleDisplayField"].strip()
                    or ("meetingId" in item and item["meetingId"] != int(meeting))):
                raise ValueError("Public item identity/title/meeting changed.")
            item_id = str(item["id"])
            if ("agenda_item", item_id) in seen:
                raise ValueError("Repeated item native identity.")
            seen.add(("agenda_item", item_id))
            rows.append(({"external_id": item_id, "title": item["titleDisplayField"], "url": citation,
                "meeting_external_id": meeting, "section_external_id": native_id,
                "source_number": item.get("number"), "source_level": item.get("level"),
                "source_parent_id": item.get("parentId"), "source_system_item_id": item.get("systemItemId"),
                "source_section_template_id": item.get("sectionTemplateId"),
                "content_availability": "public_speaker_request_outline_only",
                "item_parent_mapping": "native parentId retained; hierarchy not inferred"}, item, "agenda_item"))
    selected = [row for row in rows if row[2] == kind]
    bundle = make_bundle(source, namespace, content, "primegov-public-speaker-outline-json", selected[:maximum])
    parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting", "external_id": meeting}
    for record in bundle["records"]:
        record["identity"]["parent"] = deepcopy(parent)
        record["relationships"].append({"relation": "meeting", "identity": deepcopy(parent)})
        section = record["normalized"].get("section_external_id")
        if section:
            record["relationships"].append({"relation": "agenda_section", "identity": {
                **parent, "record_type": "agenda_section", "external_id": section, "parent": deepcopy(parent)}})
    bundle["extensions"]["public_speaker_outline"] = {
        "matching_records": len(selected), "record_limit_reached": len(selected) > maximum,
        "meeting_binding": "native_section_meetingId_and_selected_stored_meeting",
        "full_agenda_complete": False, "public_speaker_submission_performed": False}
    return bundle


def fetch_related(engine, source, namespace, request, bounds, context, transport):
    meeting, kind = request.get("parent_id"), request.get("record_type")
    parts = urlsplit(source.url)
    if (not isinstance(meeting, str) or not meeting.isascii() or not meeting.isdecimal()
            or str(int(meeting)) != meeting or not _positive(int(meeting))
            or kind not in {"agenda_section", "agenda_item"} or request.get("external_id") is not None
            or bounds.checkpoint or bounds.date_from or bounds.date_to
            or parts.scheme != "https" or not (parts.hostname or "").endswith(".primegov.com")
            or parts.path.lower() != "/public/portal" or parts.query or parts.fragment):
        raise ValueError("Select a stored public PrimeGov meeting outline without dates/continuation.")
    identity = {"provider": source.provider, "namespace": namespace, "record_type": "meeting", "external_id": meeting}
    stored = engine.storage.get("records", source_identity_key(identity), scope=context.scope) if engine.storage else None
    record = stored.value if stored else None
    if isinstance(record, dict) and "record" in record:
        record = record["record"]
    raw = record.get("original") if isinstance(record, dict) else None
    if (not isinstance(raw, dict) or record.get("source_url") != source.url
            or raw.get("id") != int(meeting) or raw.get("allowPublicSpeaker") is not True):
        raise ValueError("This outline needs a captured meeting with public speaker requests explicitly enabled.")
    coverage = {"scope": "one selected public speaker-request outline; not full agenda",
        "catalog_complete": False, "collection_complete": False, "source_complete": False,
        "public_speaker_submission_performed": False}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    url = _origin(source.url) + "/api/PublicSpeakerAndComment/GetSectionsAndItemsForSpeakerRequest?" + urlencode({"meetingId": meeting})
    deadline, retained = monotonic() + bounds.deadline_seconds, None
    try:
        response = transport.request(url, byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes),
            deadline_seconds=bounds.deadline_seconds, allowed_origins=(_origin(source.url),), allow_redirects=False)
        if (response.status != 200 or response.url != url or not isinstance(response.content, bytes)
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or response.content_type.split(";", 1)[0].strip().lower() != "application/json"):
            raise ValueError("Public outline left its bounded exact JSON contract.")
        retained = make_bundle(source, namespace, response.content, "primegov-public-speaker-outline-json", [])
        retained["capture"]["retrieval_url"] = url
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", retained, coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError("Public outline exceeded its deadline.")
        bundle = outline_bundle(source, namespace, response.content, meeting, kind, bounds.max_records)
        if monotonic() >= deadline:
            raise ValueError("Public outline parsing exceeded its deadline.")
        bundle["capture"]["retrieval_url"] = url
        coverage.update(bundle["extensions"]["public_speaker_outline"])
        return OperationResult("partial", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult("partial" if retained else "failed", retained, errors=(Error(
            "provider_outline_unavailable", "The selected public speaker-request outline could not be verified.",
            source=source.url),), coverage=coverage, operation_id=context.operation_id)
