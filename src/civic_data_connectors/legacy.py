"""Reviewable rich-result projections into the exact historical import contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .compat import source_formats, source_namespace
from .engine import source_identity_key
from .models import Error, OperationResult


def _merge_captured_civicplus_recordings(meeting, record):
    """Carry discovery-only CivicClerk media into a matched legacy preview."""
    if record.get("identity", {}).get("provider") != "civicplus-select":
        return
    original = record.get("original")
    normalized = record.get("normalized")
    if not isinstance(original, dict) or not isinstance(normalized, dict):
        return
    media_url = original.get("mediaStreamPath")
    normalized_recordings = normalized.get("recordings")
    if (not isinstance(media_url, str) or not media_url.startswith("https://")
            or not isinstance(normalized_recordings, list)
            or not any(isinstance(item, dict) and item.get("url") == media_url
                       for item in normalized_recordings)):
        return
    recordings = meeting.get("recordings")
    if not isinstance(recordings, list):
        recordings = []
    if any(isinstance(item, dict) and item.get("url") == media_url for item in recordings):
        return
    meeting["recordings"] = [*deepcopy(recordings), {"url": media_url}]


@dataclass(frozen=True)
class LegacyIdentityMapping:
    """Caller-owned, evidenced identity transition, never an inferred vendor alias."""

    provider: str
    upstream_namespace: str
    legacy_source_url: str
    external_ids: dict[str, str] = field(default_factory=dict)
    evidence: str = ""

    def __post_init__(self):
        parsed = urlsplit(self.legacy_source_url)
        if (not self.evidence or parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None):
            raise ValueError("A legacy mapping needs an original public source URL and explicit evidence.")
        if any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in self.external_ids.items()):
            raise ValueError("Legacy external-ID mappings must be explicit nonempty string identifiers.")


def legacy_previews(upstream: OperationResult | dict, *,
                    identity_mappings: tuple[LegacyIdentityMapping, ...] = (),
                    new_source: bool = False) -> OperationResult:
    """Project selected records without losing partial/failure status or rewriting legacy IDs.

    Existing v1 page previews remain authoritative. Additive API records require
    explicit source and per-ID mapping for an existing-source transition; an API
    host/client resemblance is not proof of historical identity equality.
    ``new_source=True`` is an explicit caller decision that no legacy identity
    transition is being attempted, and retains the configured source identity.
    """
    result = upstream if isinstance(upstream, OperationResult) else OperationResult.from_dict(upstream)
    if not isinstance(result.data, dict):
        return result
    data = result.data
    records = data.get("records", [])
    selected = {source_identity_key(record["identity"]): record for record in records}
    pages = data.get("bundles", [data])
    previews, projected, compatibility_hashes = [], set(), set()
    exact_baseline_formats = {(item["connector"], item["input_format"]) for item in source_formats()}
    for page in pages:
        preview = page.get("compatibility")
        if not isinstance(preview, dict) or preview.get("version") != 1:
            continue
        source = preview["source"]
        if ((source.get("connector"), source.get("format")) not in exact_baseline_formats
                or page.get("extensions", {}).get("compatibility") == "additive API format; not a legacy export"):
            continue
        compatibility_hashes.add((source["connector"], source["namespace"], source["sha256"]))
        meetings = []
        for meeting in preview.get("meetings", []):
            key = source_identity_key({
                "provider": source["connector"], "namespace": source["namespace"],
                "record_type": "meeting", "external_id": meeting["external_id"],
            })
            record = selected.get(key)
            if record and record["capture_sha256"] == source["sha256"] and key not in projected:
                projected_meeting = deepcopy(meeting)
                _merge_captured_civicplus_recordings(projected_meeting, record)
                meetings.append(projected_meeting)
                projected.add(key)
        if meetings:
            previews.append({**deepcopy(preview), "meetings": meetings})
    errors = list(result.errors)
    legacy_filtered = 0
    for key, record in selected.items():
        if key in projected:
            continue
        if (record["identity"]["provider"], record["identity"]["namespace"],
                record["capture_sha256"]) in compatibility_hashes:
            legacy_filtered += 1
            continue
        identity = record["identity"]
        # A legacy workflow deliberately omits cancelled/adjourned records.
        status = record.get("normalized", {}).get("source_status")
        if (isinstance(status, dict) and (status.get("canceled") or status.get("adjourned"))
                or status == "CANCELLED"):
            continue
        mapping = next((m for m in identity_mappings if m.provider == identity["provider"]
                        and m.upstream_namespace == identity["namespace"]
                        and identity["external_id"] in m.external_ids), None)
        if mapping is None and not new_source:
            errors.append(Error("legacy_identity_mapping_required",
                                "This additive or unprojected record requires an evidenced legacy identity mapping.",
                                details={"identity": deepcopy(identity)}))
            continue
        normalized = deepcopy(record["normalized"])
        normalized["external_id"] = (mapping.external_ids[identity["external_id"]] if mapping
                                     else identity["external_id"])
        # Project only the old public meeting fields; rich source data stays in the original result.
        fields = {"external_id", "title", "scheduled_start", "meeting_date", "source_start", "location",
                  "url", "documents", "recordings", "agenda_items", "notice", "board"}
        meeting = {name: value for name, value in normalized.items() if name in fields}
        source_url = mapping.legacy_source_url if mapping else record["source_url"]
        provider = mapping.provider if mapping else identity["provider"]
        namespace = source_namespace(provider, urlsplit(source_url))
        if not mapping and namespace != identity["namespace"]:
            errors.append(Error("legacy_source_mismatch",
                                "The configured citation URL does not establish this source namespace."))
            continue
        previews.append({
            "version": 1, "source": {
                "connector": provider, "url": source_url,
                "namespace": namespace,
                "format": "explicit-rich-projection", "sha256": record["capture_sha256"],
            }, "meetings": [meeting],
        })
        projected.add(key)
    missing = len(errors) > len(result.errors)
    status = result.status
    if missing and status == "completed":
        status = "partial" if previews else "failed"
    return OperationResult(status, {"previews": previews}, tuple(errors),
                           {**deepcopy(result.coverage), "legacy_projected_records": len(projected),
                            "legacy_filtered_records": legacy_filtered,
                            "legacy_mapping_required": missing, "new_source": new_source}, result.operation_id)
