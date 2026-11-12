"""Read a Boardable detail only through a scoped, capture-bound listing record."""

import base64
import hashlib
import re
from dataclasses import replace
from time import monotonic

from ..engine import source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .boardable import FORMAT, SITE_ORIGIN, _source_slug
from .discovery import parse_page
from .identification import validate_source
from .native import parse_native


def fetch_record(engine, source, namespace, external_id, bounds, context, transport):
    """The imported listing supplies the slug; a numeric ID never invents one."""
    _source_slug(source)
    if (not isinstance(external_id, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", external_id)
            or bounds.checkpoint is not None):
        raise ValueError("Boardable detail requires a numeric meeting ID and no checkpoint.")
    if not context.allows("fetch", namespace):
        return OperationResult("failed", errors=(Error("permission_denied",
            "The caller is not authorized to fetch this source namespace."),))
    coverage = {"scope": "one supplied Boardable detail from a scoped imported listing",
                "catalog_complete": False, "source_complete": False,
                "document_bytes_verified": False}
    deadline = monotonic() + bounds.deadline_seconds
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    identity = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                "external_id": external_id, "parent": None}
    stored = (engine.storage.get("records", source_identity_key(identity), scope=context.scope)
              if engine.storage is not None else None)
    if stored is None:
        raise ValueError("Import the Boardable listing record and its capture into this caller scope before detail retrieval.")
    record = stored.value
    digest = record.get("capture_sha256")
    captured = engine.storage.get("captures", digest, scope=context.scope) if isinstance(digest, str) else None
    if captured is None:
        raise ValueError("The scoped Boardable listing capture is unavailable; import it again.")
    capture = captured.value
    if (capture.get("source_url") != source.url or capture.get("input_format") != FORMAT
            or capture.get("sha256") != digest or record.get("source_url") != source.url
            or source_identity_key(record.get("identity")) != source_identity_key(identity)):
        raise ValueError("The stored listing record/capture does not match this Boardable source identity.")
    encoded = capture.get("content_base64")
    if not isinstance(encoded, str) or len(encoded) > 4 * ((bounds.parser_bytes + 2) // 3):
        raise ValueError("The stored Boardable listing exceeds the current parser bound.")
    content = base64.b64decode(encoded, validate=True)
    if (len(content) > bounds.parser_bytes or capture.get("byte_length") != len(content)
            or hashlib.sha256(content).hexdigest() != digest):
        raise ValueError("The stored Boardable listing bytes do not match their bound digest/size.")
    listing = parse_native(source, namespace, content, FORMAT)
    matches = [row for row in listing["records"] if row["identity"]["external_id"] == external_id]
    if len(matches) != 1:
        raise ValueError("The captured listing does not uniquely supply this Boardable meeting.")
    target = replace(source, url=matches[0]["normalized"]["url"], input_format="boardable-public-meeting-html")
    if validate_source(target, context) != namespace:
        raise ValueError("The supplied Boardable detail left the configured organization namespace.")
    coverage["listing_capture_sha256"] = digest
    try:
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError("The detail deadline expired before its request.")
        response = transport.request(target.url, allowed_origins=(SITE_ORIGIN,), allow_redirects=False,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes),
            deadline_seconds=max(.001, deadline - monotonic()))
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if (response.url != target.url or response.status != 200
                or response.content_type.split(";", 1)[0].strip().casefold() != "text/html"
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or monotonic() >= deadline):
            raise ValueError("The exact Boardable detail was not returned within its bounds.")
        # The existing fetch dispatch permits internal normalization while the
        # caller's externally exposed operations and namespace stay unchanged.
        bundle, errors = parse_page(engine, target, namespace, response.content,
                                    target.input_format, bounds, context)
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        rows = bundle["records"]
        if (len(rows) != 1 or source_identity_key(rows[0]["identity"]) != source_identity_key(identity)
                or monotonic() >= deadline):
            raise ValueError("The Boardable detail does not match the requested listing identity.")
        bundle["captures"] = [capture]
        return OperationResult("partial", bundle, errors, coverage, context.operation_id)
    except Exception:
        return OperationResult("failed", errors=(Error("provider_detail_unavailable",
            "The supplied Boardable detail could not be retrieved or identity-validated.", source=target.url),),
            coverage=coverage, operation_id=context.operation_id)
