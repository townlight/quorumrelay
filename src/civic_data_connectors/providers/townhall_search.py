"""Public Town Hall Streams archive keyword POST; exact local metadata matching."""
from dataclasses import asdict, replace
from hashlib import sha256
import re
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit

from ..compat import read_town_hall_streams
from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source
from .native import make_bundle
from .search_echo import require_search_echo

HOST = "https://www.townhallstreams.com"


def _location(source):
    p = urlsplit(source.url)
    pairs = parse_qsl(p.query, keep_blank_values=True)
    if (source.provider != "town-hall-streams" or _origin(source.url) != HOST or p.path != "/town.php"
            or p.fragment or len(pairs) != 1 or pairs[0][0] != "id"
            or not re.fullmatch(r"[1-9][0-9]{0,18}", pairs[0][1])):
        raise ValueError("Use an exact HTTPS Town Hall Streams town.php location source.")
    return pairs[0][1]


def parse_bundle(source, namespace, content, location):
    content.decode("utf-8", errors="strict")
    rows = read_town_hall_streams(source.url, content)
    for row in rows:
        for recording in row["recordings"]:
            p = urlsplit(recording["url"])
            pairs = parse_qsl(p.query, keep_blank_values=True)
            if (_origin(recording["url"]) != HOST or p.username or p.password or p.fragment
                    or p.path != "/stream.php" or len(pairs) != 2
                    or dict(pairs) != {"location_id": location, "id": row["external_id"]}):
                raise ValueError("Keyword result escaped its native location/event binding.")
        row.update(time_zone_status="unknown", agenda_items_availability="absent",
                   url=row["recordings"][0]["url"])
    return make_bundle(source, namespace, content, "town-hall-streams-html", [(r, r, "meeting") for r in rows])


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    location = _location(source)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Search namespace is not authorized."),))
    if content is not None or any(k in request for k in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Saved search captures require native=false.")
    bounds, query = Bounds(**request.get("bounds", {})), _query(request.get("query", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if (not expressions or not expressions[0].strip() or len(expressions[0]) > 255
            or any(ord(c) < 32 or ord(c) == 127 or c in "<>" for c in expressions[0])
            or source.body or query.body
            or query.record_types and set(query.record_types) != {"meeting"}):
        raise ValueError("Use a bounded search expression; only supplied meeting metadata is searched and body is unavailable.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query),
                              "scope": context.scope, "contract": "townhall-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"offset", "sha256"}
            or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 100000):
        raise ValueError("Invalid Town Hall Streams search continuation.")
    task = queue[0]
    url = source.url
    body = urlencode({"search": expressions[0], "searchbtn": "Search"}).encode()
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "source_complete": False, "catalog_complete": False, "status": "partial",
        "scope": "public archive keyword results; literal meeting IDs/titles/dates and supplied stream locators",
        "provider_query_semantics": "provider-defined first expression; exact local AND",
        "pagination": "local offset in one hash-bound capture; provider truncation/exhaustion unverified",
        "full_document_text_searched": False, "pages": 0}
    deadline = monotonic() + bounds.deadline_seconds

    def stopped():
        if operation_cancelled(engine.storage, context):
            raise InterruptedError
        if monotonic() >= deadline:
            raise TimeoutError

    try:
        stopped()
        response = (transport or PublicTransport()).request(url, method="POST", body=body,
            headers={"Accept": "text/html", "Content-Type": "application/x-www-form-urlencoded"},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=deadline-monotonic(),
            allowed_origins=(HOST,), allow_redirects=False)
        stopped()
        if (response.status != 200 or response.url != url or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or response.content_type.split(";", 1)[0].strip().lower() != "text/html"):
            raise ValueError("Search response changed route/type or exceeded bounds.")
        require_search_echo(response.content, "search", expressions[0])
        bundle = parse_bundle(source, namespace, response.content, location)
        stopped()
        digest = sha256(response.content).hexdigest()
        rows = bundle["records"]
        if task.get("sha256") and task["sha256"] != digest or task["offset"] > len(rows):
            raise ValueError("Search result changed; restart explicitly.")
        end = min(len(rows), task["offset"] + min(bounds.max_records, query.limit))
        selected = [r for r in rows[task["offset"]:end] if canonical_hash(r["identity"]["external_id"]) not in seen]
        seen.update(canonical_hash(r["identity"]["external_id"]) for r in selected)
        bundle["records"] = selected
        bundle["capture"]["retrieval_url"] = url
        bundle["extensions"]["public_search_request"] = {"method": "POST", "url": url, "fields": {"search": expressions[0], "searchbtn": "Search"}}
        coverage.update(pages=1, provider_returned_rows=len(rows),
            checkpoint=_checkpoint(binding, [{"offset": end, "sha256": digest}], seen) if end < len(rows) else None)
        result = search_records(selected, query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline-monotonic())), sources=coverage["sources"],
            inherited_coverage=coverage, context=context, storage=engine.storage)
        stopped()
        if result.data is None:
            return result
        return OperationResult(result.status, {**result.data, "bundle": bundle}, result.errors,
            {**result.coverage, **coverage}, context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    except (ValueError, TimeoutError):
        return OperationResult("failed", errors=(Error("provider_search_failed",
            "Town Hall Streams search result could not be verified; no empty completeness inferred."),),
            coverage=coverage, operation_id=context.operation_id)
