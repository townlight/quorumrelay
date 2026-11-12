"""Roster-bounded source identification, without network requests."""

from __future__ import annotations

import ipaddress
import json
import re
from functools import lru_cache
from importlib.resources import files
from urllib.parse import parse_qs, unquote, urlsplit

from .. import compat
from ..models import OperationContext, OperationResult, Source

FORMATS = {provider: tuple(row["input_format"] for row in compat.source_formats()
                           if row["connector"] == provider)
           for provider in dict.fromkeys(row["connector"] for row in compat.source_formats())}
ADDITIONAL_FORMATS = {"legistar": ("legistar-events-json", "legistar-event-json", "legistar-votes-json",
                                 "legistar-rollcalls-json"),
                      "civicweb": ("civicweb-detail-html",),
                      "swagit": ("swagit-listing-html",),
                      "onbase": ("onbase-public-listing-html",),
                      "boardable": ("boardable-public-meetings-json",),
                      "telvue": ("telvue-connect-media-json", "telvue-connect-videos-json",
                                 "telvue-connect-playlists-json"),
                      "municode-meetings": ("essential-multimedia-json",),
                      "novusagenda": ("novus-public-listing-html",),
                      "granicus": ("granicus-listing-html",),
                      "peak": ("granicus-listing-html",),
                      "wistia": ("wistia-api-media-json", "wistia-media-detail-json", "wistia-caption-json"),
                      "laserfiche-weblink": ("laserfiche-listing-json", "laserfiche-repository-entries-json")}


@lru_cache(maxsize=1)
def _aliases():
    payload = json.loads(files("civic_data_connectors").joinpath(
        "data/provider-identities.json").read_text(encoding="utf-8"))
    aliases = payload["alias_to_canonical"]
    if set(aliases.values()) != set(FORMATS):
        raise ValueError("Packaged provider identities do not match the fixed baseline roster.")
    return aliases


def canonical_provider(provider):
    if not isinstance(provider, str):
        raise ValueError("A source provider must be an explicit provider identifier.")
    value = _aliases().get(provider.strip().lower())
    if value is None:
        raise ValueError("The configured provider is outside the fixed 31-family roster.")
    return value


def configured_source(value):
    if not isinstance(value, dict):
        raise ValueError("source must be a configured source object.")
    return Source.from_dict({**value, "provider": canonical_provider(value.get("provider"))})
SENSITIVE_QUERY = re.compile(
    r"^(?:token|access_token|id_token|password|secret|authorization|credential|"
    r"api[-_]?key|signature|sig|x-amz-.*|x-goog-.*)$", re.I,
)
_HOSTS = (
    ("primegov", r"(?:[^.]+\.)?primegov\.com"),
    ("legistar", r"(?:[^.]+\.)?legistar\.com"),
    ("civicplus-select", r"[^.]+\.(?:portal|api)\.civicclerk\.com"),
    ("escribe", r"pub-[^.]+\.escribemeetings\.com"),
    ("municode-meetings", r"[^.]+\.municodemeetings\.com"),
    ("municode-meetings", r"meetingsgov\.devmunicode\.com"),
    ("boardbook", r"meetings\.boardbook\.org"),
    ("simbli", r"simbli\.eboardsolutions\.com"),
    ("civicweb", r"[^.]+\.civicweb\.net"),
    ("iqm2", r"[^.]+\.iqm2\.com"),
    ("swagit", r"(?:[^.]+\.)*(?:swagit\.com|swagit\.avcaptureall\.com)"),
    ("suiteone-media", r"[^.]+\.suiteonemedia\.com"),
    ("destiny-agendaquick", r"(?:public\.)?destinyhosted\.com"),
    ("town-hall-streams", r"(?:www\.)?townhallstreams\.com"),
    ("telvue", r"videoplayer\.telvue\.com"),
    ("telvue", r"connect\.telvue\.com"),
    ("champ", r"play\.champds\.com"),
    ("laserfiche-weblink", r"api\.laserfiche\.com"),
    ("towncloud", r"towncloud\.io"),
    ("clerkbase", r"(?:[^.]+\.)?(?:clerkbase\.com|clerkshq\.com)"),
    ("wistia", r"(?:[^.]+\.)?wistia\.(?:com|net)"),
    ("boardable", r"site\.boardable\.com"),
    ("gworks", r"(?:files\.frontdeskgworks\.com|api\.gworks\.cloud)"),
    ("boarddocs", r"(?:go|www)\.boarddocs\.com"),
    ("tyler-meeting-manager", r"[^.]+\.meetingmanager\.tylerapp\.com"),
    ("novusagenda", r"(?:[^.]+\.)?novusagenda\.com"),
)


def validate_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Use a public HTTP(S) source URL without embedded credentials.")
    if p.fragment or p.port not in {None, 443 if p.scheme == "https" else 80}:
        raise ValueError("Source URLs cannot contain custom ports or fragments.")
    host = p.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise ValueError("A provider source must use a public host.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (not address.is_global or address.is_reserved or address.is_multicast):
        raise ValueError("A provider source must use a public host.")
    if any(SENSITIVE_QUERY.search(key) for key in parse_qs(p.query, keep_blank_values=True)):
        raise ValueError("Keep credentials and signed transfer URLs out of source citations.")


def candidates(url: str, content: bytes | None = None) -> list[str]:
    validate_url(url)
    p = urlsplit(url)
    host, path = p.hostname.lower(), unquote(p.path).lower()
    found = [provider for provider, pattern in _HOSTS if re.fullmatch(pattern, host)]
    if re.fullmatch(r"[^.]+\.granicus\.com", host):
        # Peak and legacy ViewPublisher share the same URL shape.
        found += ["granicus", "peak"]
    if path.startswith("/agendacenter") or path == "/archive.aspx":
        found.append("civicplus-agenda-center")
    if re.search(r"/(?:public)?weblink(?:/|$)", path):
        found.append("laserfiche-weblink")
    if "/onbaseagendaonline" in path:
        found.append("onbase")
    if host in {"utah.gov", "www.utah.gov"} and path.startswith("/pmn/"):
        found.append("utah-public-notice")
    if path.endswith(".ics"):
        found.append("first-party")
    if content:
        sample = content[:262144].lower()
        if b"begin:vcalendar" in sample:
            found.append("first-party")
        if b"digital towpath" in sample or b"digitaltowpath.com" in sample:
            found.append("digital-towpath")
        if b"novusagenda" in sample:
            found.append("novusagenda")
        if content.startswith(b"%PDF") and b"boarddocs" in sample:
            found.append("boarddocs")
    return list(dict.fromkeys(found))


def validate_source(source: Source, context: OperationContext | None = None,
                    content: bytes | None = None) -> str:
    if source.provider not in FORMATS:
        raise ValueError("The configured provider is outside the fixed 31-family roster.")
    identified = candidates(source.url, content)
    if identified and source.provider not in identified:
        raise ValueError("The configured provider does not match the source URL or capture.")
    valid_formats = FORMATS[source.provider] + ADDITIONAL_FORMATS.get(source.provider, ())
    if source.input_format is not None and source.input_format not in valid_formats:
        raise ValueError("The input format does not belong to the configured provider.")
    from .account_api import account_namespace, is_account_api
    account_api = is_account_api(source)
    namespace = (account_namespace(source) if account_api else
                 compat.source_namespace(source.provider, urlsplit(source.url)))
    if not account_api and source.namespace is not None and namespace != source.namespace:
        raise ValueError("The configured namespace does not match the provider-derived source namespace.")
    if (context is not None and context.allowed_namespaces is not None and
            namespace not in context.allowed_namespaces):
        raise ValueError("The source namespace is outside the caller's authorized source scope.")
    allowed_options = {"download_origins"}
    if source.provider in {"legistar", "wistia", "laserfiche-weblink"}:
        allowed_options.add("page_size")
    if source.provider == "wistia":
        allowed_options.add("folder_id")
    if source.provider == "laserfiche-weblink":
        allowed_options.add("max_folder_depth")
    if source.provider == "tyler-meeting-manager":
        allowed_options.add("calendar_api_base")
    if not isinstance(source.options, dict) or set(source.options) - allowed_options:
        raise ValueError("Source options contain unrecognized provider configuration; credentials belong in context.")
    return namespace


def identify_handler(engine, request, content, context):
    url = request.get("url") or request.get("source", {}).get("url")
    if not isinstance(url, str):
        raise ValueError("identify requires a source URL.")
    matches = candidates(url, content)
    return OperationResult("completed", {
        "url": url, "identified": len(matches) == 1, "candidates": matches,
        "ambiguous": len(matches) > 1,
        "provider": matches[0] if len(matches) == 1 else None,
        "evidence": "URL/capture shape, not tenant API acceptance",
    }, operation_id=context.operation_id)


def validate_handler(engine, request, content, context):
    source = configured_source(request["source"])
    namespace = validate_source(source, context, content)
    matches = candidates(source.url, content)
    return OperationResult("completed", {
        "source": {**source.public_dict(), "namespace": namespace},
        "provider_recognition": "matched" if matches else "explicit_configuration_unverified",
        "body_validation": "requires_catalog" if source.body else "not_requested",
    }, operation_id=context.operation_id)
