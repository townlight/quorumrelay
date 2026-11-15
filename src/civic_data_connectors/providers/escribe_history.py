"""Selected vendor history view; retain literal motions/votes without interpretation."""
from copy import deepcopy
import json

from ..engine import canonical_hash
from .native import make_bundle


def history_index_bundle(source, namespace, content, value, parameters):
    """Bind a native scalar ID list only to its explicit request meeting."""
    from .escribe_publishing import FORMAT

    if value is None:
        ids = []
    elif isinstance(value, dict) and set(value) <= {"int"} and isinstance(value.get("int", []), list):
        ids = value.get("int", [])
    else:
        raise ValueError("The history selector requires the pinned integer-array response.")
    if any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Every history item reference must have a unique positive native ID.")
    meeting = parameters["MeetingId"]
    rows = []
    for item in ids:
        identity = json.dumps({"MeetingId": meeting, "AgendaItemId": item}, sort_keys=True, separators=(",", ":"))
        rows.append(({"external_id": identity, "url": source.url,
            "native_agenda_item_id": item, "native_meeting_id": meeting,
            "meeting_binding": "explicit_request_context_not_response_echo",
            "agenda_type_availability": "not_supplied_by_history_index",
            "history_availability": "native_selector_only_fetch_selected_view_separately",
            "documents": [], "recordings": []}, item, "agenda_item_history_reference"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["extensions"]["native_request_context"] = {
        "api_method": "MeetingAgendaItemsWithHistory", "api_parameters": deepcopy(parameters)}
    bundle["extensions"]["native_result_availability"] = "nil" if value is None else "supplied_array"
    for record in bundle["records"]:
        record["relationships"] = [{"relation": "meeting", "identity": {
            "provider": source.provider, "namespace": namespace, "record_type": "meeting",
            "external_id": meeting}, "binding": "explicit_request_context_not_response_echo"},
            {"relation": "agenda_item_reference", "value": {
                "native_meeting_id": meeting, "native_agenda_item_id": record["original"],
                "agenda_type_availability": "not_supplied_by_history_index"}}]
    return bundle


def bind_history(parameters, bundle):
    if (type(parameters.get("AgendaItemId")) is not int or parameters["AgendaItemId"] <= 0
            or not isinstance(parameters.get("MeetingId"), str)):
        raise ValueError("A selected native meeting and positive item ID are required.")
    for record in bundle["records"]:
        history = record["original"]["History"]
        if (history["MeetingId"] != parameters["MeetingId"]
                or history["AgendaItemId"] != parameters["AgendaItemId"]):
            raise ValueError("History view does not match the exact selected meeting/item.")


def history_bundle(source, namespace, content, value):
    from .escribe_publishing import FORMAT

    if value is None:
        return make_bundle(source, namespace, content, FORMAT, [])
    history = value.get("History")
    if not isinstance(history, dict):
        raise ValueError("A selected history view requires its native history row.")
    identity = history.get("Id")
    if (not isinstance(identity, dict) or set(identity) != {"Id", "PortalId"}
            or type(identity["Id"]) is not int or identity["Id"] <= 0 or not identity["PortalId"]
            or type(history.get("AgendaItemId")) is not int or history["AgendaItemId"] <= 0
            or not isinstance(history.get("MeetingId"), str)):
        raise ValueError("Complete native history, meeting and item identities are required.")

    # The view can include earlier meetings. Keep their supplied native values;
    # do not assign every nested motion/document to the selected current item.
    components = 1
    text = []

    def visit(node, path):
        nonlocal components
        if not isinstance(node, dict):
            return
        for key, child in node.items():
            location = f"{path}.{key}" if path else key
            if isinstance(child, dict):
                components += 1
                visit(child, location)
            elif isinstance(child, list):
                for index, row in enumerate(child):
                    components += 1
                    visit(row, f"{location}[{index}]")
            elif key in {"AgendaItemTitle", "Comments", "Text", "BannerText", "DisplayName", "Name"}:
                if isinstance(child, str) and child:
                    text.append({"field": location, "text": child, "citation_url": source.url,
                        "completeness": "supplied_source_field", "provenance": {
                            "method": "escribe_publishing_soap_field", "source_field": location}})

    visit(value, "")
    normalized = {"external_id": json.dumps(identity, sort_keys=True, separators=(",", ":")),
        "title": history.get("AgendaItemTitle"), "url": source.url,
        "native_fields": deepcopy(value), "source_component_count": components,
        "time_zone_status": "not_interpreted", "documents": [], "recordings": [],
        "source_motions": deepcopy(value.get("Motions")), "source_votes": deepcopy(value.get("Votes")),
        "motion_vote_interpretation": "literal_native_fields_no_tally_or_result_inference"}
    bundle = make_bundle(source, namespace, content, FORMAT, [(normalized, value, "agenda_item_history_view")])
    record = bundle["records"][0]
    record["relationships"] = [{"relation": "meeting", "identity": {
        "provider": source.provider, "namespace": namespace, "record_type": "meeting",
        "external_id": history["MeetingId"]}}, {"relation": "agenda_item_reference", "value": {
            "native_meeting_id": history["MeetingId"], "native_agenda_item_id": history["AgendaItemId"],
            "agenda_type_availability": "not_supplied_by_history_view"}}]
    documents = [("History.DocumentId", history.get("DocumentId"))]
    if isinstance(value.get("Document"), dict):
        documents.append(("Document.Id", value["Document"].get("Id")))
    if isinstance(value.get("Documents"), dict):
        documents.extend((f"Documents.Document.Record[{index}].Id", row.get("Id"))
            for index, row in enumerate(value["Documents"].get("Document.Record", [])) if isinstance(row, dict))
    for path, native_id in documents:
        if type(native_id) is int and native_id > 0:
            record["relationships"].append({"relation": "document", "identity": {
                "provider": source.provider, "namespace": namespace, "record_type": "document",
                "external_id": str(native_id)}, "source_field": path})
    for entry in text:
        entry["provenance"]["capture_sha256"] = bundle["capture"]["sha256"]
    record["text"] = text
    record["normalized_sha256"] = canonical_hash(normalized)
    return bundle
