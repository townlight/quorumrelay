"""Bounded CHAMP VOD URL enrichment from the captured public event payload."""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import unquote, urlsplit

from .identification import validate_url


def _safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return None
    if "\\" in value or any(ord(character) < 0x20 for character in value):
        return None
    parts = urlsplit(value)
    decoded_segments = unquote(parts.path).split("/")
    if parts.scheme or parts.netloc or parts.fragment or ".." in decoded_segments:
        return None
    return value


def _selected_url(original: dict) -> tuple[str, str, dict, dict] | None:
    media = original.get("MediaInfo")
    services = original.get("ServicesAndMachineInfo")
    if not isinstance(media, dict) or media.get("MediaType") != "VOD" or not isinstance(services, dict):
        return None

    # This follows the captured public player's loadPlayer selection order.
    service_id = "2048" if services.get("2048") else "8"
    service = services.get(service_id)
    if not isinstance(service, dict):
        return None

    base = service.get("URLBase")
    if not isinstance(base, str):
        return None
    try:
        validate_url(base)
        base_parts = urlsplit(base)
    except ValueError:
        return None
    if base_parts.scheme != "https" or not base_parts.hostname:
        return None

    vod2 = media.get("VOD2")
    if vod2:
        relative = _safe_relative_path(vod2)
        if relative is None:
            return None
        playback_url = f"{base}{relative}"
    else:
        media_path = _safe_relative_path(media.get("MediaPath"))
        filename = service.get("URLFilename")
        if media_path is None or not isinstance(filename, str) or "%MEDIA_PATH%" not in filename:
            return None
        # JavaScript String.replace() in the captured player replaces only its
        # first occurrence. Keep that behavior instead of broad substitution.
        filename = filename.replace("%MEDIA_PATH%", media_path, 1)
        if not filename.startswith("/"):
            filename = f"/{filename}"
        playback_url = f"{base}{filename}"

    try:
        validate_url(playback_url)
        playback_parts = urlsplit(playback_url)
    except ValueError:
        return None
    if (playback_parts.scheme != "https" or not playback_parts.hostname
            or playback_parts.hostname.lower() != base_parts.hostname.lower()
            or playback_parts.port != base_parts.port):
        return None

    path = playback_parts.path.lower()
    if path.endswith(".m3u8"):
        representation = "hls_manifest"
    elif path.endswith(".mp4"):
        representation = "direct_media"
    else:
        return None
    return playback_url, representation, media, service


def enrich_bundle(bundle: dict) -> dict:
    """Return a copy with a safe, source-derived CHAMP playback recording added.

    The original event, existing player citation, and compatibility projection
    are retained. This helper derives only a direct MP4 URL or an HLS manifest
    URL using the public player's captured URL construction rules.
    """
    enriched = deepcopy(bundle)
    if not isinstance(enriched, dict) or not isinstance(enriched.get("records"), list):
        return enriched

    for record in enriched["records"]:
        if not isinstance(record, dict):
            continue
        identity = record.get("identity")
        original = record.get("original")
        normalized = record.get("normalized")
        if (not isinstance(identity, dict) or identity.get("provider") != "champ"
                or not isinstance(original, dict) or not isinstance(normalized, dict)):
            continue
        customer = original.get("Customer")
        event = original.get("Event")
        event_id = event.get("CustomerEventID") if isinstance(event, dict) else None
        customer_id = customer.get("CustomerAccessID") if isinstance(customer, dict) else None
        recordings = normalized.get("recordings")
        relationships = record.get("relationships")
        player = normalized.get("url")
        if relationships is None:
            relationships = []
        if (event_id is None or not isinstance(customer_id, str) or not customer_id
                or str(event_id) != str(identity.get("external_id"))
                or not isinstance(recordings, list) or not isinstance(relationships, list)
                or not isinstance(player, str)):
            continue

        resolved = _selected_url(original)
        if resolved is None:
            continue
        try:
            validate_url(player)
            player_parts = urlsplit(player)
        except ValueError:
            continue
        if (player_parts.scheme != "https" or player_parts.hostname != "play.champds.com"
                or player_parts.path.casefold() != f"/{customer_id}/event/{event_id}".casefold()):
            continue

        playback_url, representation, media, service = resolved
        recording = next((item for item in recordings
                          if isinstance(item, dict) and item.get("url") == playback_url), None)
        if recording is None:
            recording = {
                "url": playback_url,
                "representation": representation,
                "citation_url": player,
                "source_fields": {
                    "media_info": deepcopy(media),
                    "service_info": deepcopy(service),
                },
            }
            if representation == "direct_media":
                recording["video_url"] = playback_url
            recordings.append(recording)

        if not any(
            isinstance(item, dict) and item.get("relation") == "recording"
            and isinstance(item.get("value"), dict)
            and item["value"].get("url") == playback_url
            for item in relationships
        ):
            relationships.append({"relation": "recording", "value": deepcopy(recording)})
        record["relationships"] = relationships

        # Keep discovery/import change detection aligned with the additive
        # normalized recording while leaving the captured original untouched.
        from ..engine import canonical_hash
        record["normalized_sha256"] = canonical_hash(normalized)

    return enriched
