"""Register provider operations without starting network services or browser sessions."""

from .contracts import BrowserSession, PublicTransport, Response, Transport
from .discovery import discover
from .identification import FORMATS, identify_handler, validate_handler, validate_source
from .native import parse_native
from .retrieval import fetch
from ..models import OperationResult


def _parse_saved_native(source, content, input_format, bounds, context):
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    namespace = validate_source(source, context)
    bundle = parse_native(source, namespace, content, input_format)
    unknown = []
    if source.body:
        selected = []
        for record in bundle["records"]:
            body = record["normalized"].get("body")
            if body and body.casefold() != source.body.casefold():
                continue
            if not body:
                unknown.append(record["identity"]["external_id"])
            selected.append(record)
        bundle["records"] = selected
    return OperationResult("partial" if unknown else "completed", bundle,
                           coverage={"scope": "saved capture", "source_complete": False,
                                     "catalog_complete": False, "unknown_body_records": unknown},
                           operation_id=context.operation_id)


def register(engine, *, transport: Transport | None = None,
             browser: BrowserSession | None = None) -> None:
    """Compose operations once; injected transports are an SDK/server trust boundary."""
    engine.register_operation("identify", identify_handler)
    engine.register_operation("validate_source", validate_handler)
    for provider, input_format in (
            ("municode-meetings", "essential-multimedia-json"),
            ("telvue", "telvue-connect-media-json"), ("telvue", "telvue-connect-videos-json"),
            ("telvue", "telvue-connect-playlists-json"),
            ("legistar", "legistar-events-json"), ("legistar", "legistar-event-json"),
            ("legistar", "legistar-votes-json"), ("legistar", "legistar-rollcalls-json"),
            ("novusagenda", "novus-public-listing-html"),
            ("laserfiche-weblink", "laserfiche-repository-entries-json"),
            ("wistia", "wistia-api-media-json"), ("wistia", "wistia-media-detail-json"),
            ("wistia", "wistia-caption-json"),
            ("granicus", "granicus-listing-html"), ("peak", "granicus-listing-html")):
        engine.register_parser(provider, input_format, _parse_saved_native)
    engine.register_operation(
        "discover", lambda engine, request, content, context:
        discover(engine, request, content, context, transport=transport, browser=browser))
    engine.register_operation(
        "fetch", lambda engine, request, content, context:
        fetch(engine, request, content, context, transport=transport, browser=browser))
    from .wistia import native_search
    from ..storage import tracked_handler
    engine.register_native_search("wistia", tracked_handler("search", lambda engine, request, content, context:
                                  native_search(engine, request, content, context, transport=transport)))
    from .legistar import native_search as legistar_search
    engine.register_native_search("legistar", tracked_handler("search", lambda engine, request, content, context:
                                  legistar_search(engine, request, content, context, transport=transport)))
    from .granicus_search import native_search as granicus_search
    engine.register_native_search("granicus", tracked_handler("search", lambda engine, request, content, context:
                                  granicus_search(engine, request, content, context, transport=transport)))
    from .primegov_search import native_search as primegov_search
    engine.register_native_search("primegov", tracked_handler("search", lambda engine, request, content, context:
                                  primegov_search(engine, request, content, context, transport=transport)))
    from .civicplus_export import export_historical
    engine.register_native_export("civicplus-select", tracked_handler("export", export_historical))


__all__ = ["FORMATS", "BrowserSession", "PublicTransport", "Response", "Transport", "register"]
