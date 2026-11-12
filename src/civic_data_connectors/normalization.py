"""Shared local-first connector import normalization primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_CONNECTORS = ("granicus", "legistar", "novusagenda", "primegov")


@dataclass(frozen=True)
class ConnectorImportError(ValueError):
    """Actionable validation error for local connector import payloads."""

    message: str
    fix: str

    def public_dict(self) -> dict[str, str]:
        return {
            "message": self.message,
            "fix": self.fix,
        }


@dataclass(frozen=True)
class ImportedAgendaItem:
    """Normalized agenda item imported from a local connector payload."""

    external_item_id: str
    title: str
    department: str | None
    connector: str

    def public_dict(self) -> dict[str, str | None | dict[str, str]]:
        return {
            "external_item_id": self.external_item_id,
            "title": self.title,
            "department": self.department,
            "source_provenance": {
                "connector": self.connector,
                "imported_from": "local_payload",
                "external_item_id": self.external_item_id,
            },
        }


@dataclass(frozen=True)
class ImportedMeeting:
    """Normalized meeting imported from a local connector payload."""

    connector: str
    external_meeting_id: str
    title: str
    scheduled_start: str
    agenda_items: tuple[ImportedAgendaItem, ...]

    def public_dict(self) -> dict[str, str | list[dict] | dict[str, str]]:
        return {
            "connector": self.connector,
            "external_meeting_id": self.external_meeting_id,
            "title": self.title,
            "scheduled_start": self.scheduled_start,
            "source_provenance": {
                "connector": self.connector,
                "imported_from": "local_payload",
                "external_meeting_id": self.external_meeting_id,
            },
            "agenda_items": [item.public_dict() for item in self.agenda_items],
        }


def import_meeting_payload(
    *,
    connector_name: str,
    payload: dict[str, Any],
) -> ImportedMeeting:
    """Normalize one local export payload from a supported agenda platform."""

    connector = connector_name.strip().lower()
    if connector not in SUPPORTED_CONNECTORS:
        raise ConnectorImportError(
            message=f"Unsupported connector '{connector_name}'.",
            fix="Use one of: granicus, legistar, novusagenda, primegov.",
        )
    return _CONNECTOR_IMPORTERS[connector](payload)


def _require(
    payload: dict[str, Any],
    *,
    connector_label: str,
    field: str,
) -> Any:
    value = payload.get(field)
    if value in (None, ""):
        raise ConnectorImportError(
            message=f"{connector_label} meeting payload is missing required field {field}.",
            fix=f"Export the meeting again with {field} included, then retry the local import.",
        )
    return value


def _items_from(
    raw_items: Any,
    *,
    connector: str,
    id_field: str,
    title_field: str,
    department_field: str,
) -> tuple[ImportedAgendaItem, ...]:
    if not isinstance(raw_items, list):
        raw_items = []
    items: list[ImportedAgendaItem] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            continue
        external_item_id = str(raw_item.get(id_field) or f"{connector}-item-{index}")
        title = str(raw_item.get(title_field) or "Untitled agenda item")
        department = raw_item.get(department_field)
        items.append(
            ImportedAgendaItem(
                external_item_id=external_item_id,
                title=title,
                department=str(department) if department not in (None, "") else None,
                connector=connector,
            )
        )
    return tuple(items)


def _import_granicus(payload: dict[str, Any]) -> ImportedMeeting:
    connector = "granicus"
    return ImportedMeeting(
        connector=connector,
        external_meeting_id=str(_require(payload, connector_label="Granicus", field="id")),
        title=str(_require(payload, connector_label="Granicus", field="name")),
        scheduled_start=str(_require(payload, connector_label="Granicus", field="start")),
        agenda_items=_items_from(
            payload.get("agenda"),
            connector=connector,
            id_field="id",
            title_field="title",
            department_field="department",
        ),
    )


def _import_legistar(payload: dict[str, Any]) -> ImportedMeeting:
    connector = "legistar"
    return ImportedMeeting(
        connector=connector,
        external_meeting_id=str(_require(payload, connector_label="Legistar", field="MeetingId")),
        title=str(_require(payload, connector_label="Legistar", field="MeetingName")),
        scheduled_start=str(_require(payload, connector_label="Legistar", field="MeetingDate")),
        agenda_items=_items_from(
            payload.get("AgendaItems"),
            connector=connector,
            id_field="FileNumber",
            title_field="Title",
            department_field="DepartmentName",
        ),
    )


def _import_primegov(payload: dict[str, Any]) -> ImportedMeeting:
    connector = "primegov"
    return ImportedMeeting(
        connector=connector,
        external_meeting_id=str(_require(payload, connector_label="PrimeGov", field="meeting_id")),
        title=str(_require(payload, connector_label="PrimeGov", field="title")),
        scheduled_start=str(_require(payload, connector_label="PrimeGov", field="scheduled_start")),
        agenda_items=_items_from(
            payload.get("items"),
            connector=connector,
            id_field="item_id",
            title_field="subject",
            department_field="owner",
        ),
    )


def _import_novusagenda(payload: dict[str, Any]) -> ImportedMeeting:
    connector = "novusagenda"
    return ImportedMeeting(
        connector=connector,
        external_meeting_id=str(_require(payload, connector_label="NovusAGENDA", field="MeetingGuid")),
        title=str(_require(payload, connector_label="NovusAGENDA", field="MeetingTitle")),
        scheduled_start=str(_require(payload, connector_label="NovusAGENDA", field="MeetingDateTime")),
        agenda_items=_items_from(
            payload.get("Agenda"),
            connector=connector,
            id_field="Guid",
            title_field="Caption",
            department_field="Dept",
        ),
    )


_CONNECTOR_IMPORTERS = {
    "granicus": _import_granicus,
    "legistar": _import_legistar,
    "novusagenda": _import_novusagenda,
    "primegov": _import_primegov,
}


__all__ = [
    "ConnectorImportError",
    "ImportedAgendaItem",
    "ImportedMeeting",
    "SUPPORTED_CONNECTORS",
    "import_meeting_payload",
]
