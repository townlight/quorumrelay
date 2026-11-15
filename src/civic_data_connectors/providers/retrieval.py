"""Fetch configured sources or capture-verified attachments, never arbitrary URLs."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from ..engine import source_identity_key
from ..models import Bounds, Error, OperationResult
from .contracts import PublicTransport, _origin
from .discovery import DEFAULT_FORMAT, _decode_content, discover, parse_page
from .identification import configured_source, validate_source, validate_url


def _download_origins(source, url):
    origins = source.options.get("download_origins", [])
    if not isinstance(origins, list) or len(origins) > 16:
        raise ValueError("download_origins must be an explicit bounded list of origins.")
    for origin in origins:
        validate_url(origin)
        if _origin(origin) != origin or urlsplit(origin).path:
            raise ValueError("Each download origin must be an exact HTTP(S) origin without a path.")
    base = _origin(source.url)
    target = _origin(url)
    # Published files on a CivicClerk API origin are part of the same configured tenant.
    if (source.provider == "civicplus-select" and
            (urlsplit(source.url).hostname or '').endswith(('.portal.civicclerk.com', '.api.civicclerk.com'))):
        from .discovery import _api_source
        base = _origin(_api_source(source))
    allowed = tuple(dict.fromkeys([base, *origins]))
    if target not in allowed:
        raise ValueError("The document origin needs explicit configured download_origins authorization.")
    return allowed


def fetch(engine, request, content, context, *, transport=None, browser=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context, content)
    bounds = Bounds(**request.get("bounds", {}))
    transport = transport or PublicTransport()
    content = _decode_content(request, content)
    attachment = request.get("attachment")
    if source.provider == "escribe" and source.input_format == "escribe-publishing-soap-xml" and content is None:
        if attachment is not None:
            raise ValueError("PublishingService requires explicit native parameters, not arbitrary attachment URLs.")
        from .escribe_publishing import read
        return read(engine, source, namespace, request, bounds, context, transport)
    if source.provider == "civicweb" and source.input_format == "civicweb-filepro-soap-xml" and content is None:
        from .civicweb_filepro import read
        return read(source, namespace, request, bounds, context, transport)
    if source.provider == "granicus" and source.input_format == "granicus-platform-soap-xml" and content is None:
        if attachment is not None:
            raise ValueError("SOAP document retrieval requires its documented resource mapping; no arbitrary attachment URL.")
        from .granicus_platform import read
        return read(source, namespace, request, bounds, context, transport)
    from .account_api import is_account_api
    if is_account_api(source) and attachment is None and content is None:
        from .account_reads import fetch_account
        return fetch_account(source, namespace, request, bounds, context, transport)
    if "parent_id" in request or "record_type" in request:
        if attachment is not None or content is not None:
            raise ValueError("Related record retrieval cannot be combined with attachment or saved input.")
        if source.provider == "legistar":
            from .legistar import fetch_related
            return fetch_related(source, namespace, request, bounds, context, transport)
        if source.provider == "civicweb":
            from .civicweb_listing import fetch_related
            return fetch_related(source, namespace, request, bounds, context, transport)
        if source.provider == "iqm2":
            from .iqm2_file import fetch_related
            return fetch_related(engine, source, namespace, request, bounds, context, transport)
        if source.provider == "onbase":
            from .onbase_detail import fetch_detail
            return fetch_detail(source, namespace, request, bounds, context, transport)
        if source.provider == "primegov":
            from .primegov_public import fetch_related
            return fetch_related(engine, source, namespace, request, bounds, context, transport)
        if source.provider == "boarddocs":
            from .boarddocs_agenda import fetch_related
            return fetch_related(engine, source, namespace, request, bounds, context, transport)
        return OperationResult.unsupported("fetch_related", reason=(
            "No verified related-record retrieval mapping is registered for this provider."))
    if "external_id" in request:
        if attachment is not None or content is not None:
            raise ValueError("Record detail retrieval cannot be combined with attachment or saved input.")
        if "caption_language" in request and source.provider == "iqm2":
            from .iqm2_player import fetch_captions
            return fetch_captions(engine, source, namespace, request, bounds, context, transport)
        if "caption_language" in request and source.provider == "suiteone-media":
            from .suiteone_player import fetch_captions
            return fetch_captions(engine, source, namespace, request, bounds, context, transport)
        if "caption_language" in request and source.provider == "telvue":
            from .telvue_player import fetch_captions
            return fetch_captions(engine, source, namespace, request, bounds, context, transport)
        if "caption_language" in request and source.provider == "swagit":
            from .swagit_player import fetch_captions
            return fetch_captions(engine, source, namespace, request, bounds, context, transport)
        if "caption_language" in request and source.provider == "town-hall-streams":
            from .townhall_captions import fetch_captions
            return fetch_captions(engine, source, namespace, request, bounds, context, transport)
        if "caption_language" in request and source.provider != "wistia":
            return OperationResult.unsupported("fetch_captions", reason=(
                "No verified supplied-caption retrieval mapping is registered for this provider."))
        if source.provider == "onbase":
            from .onbase_detail import fetch_detail
            return fetch_detail(source, namespace, request, bounds, context, transport)
        if source.provider == 'tyler-meeting-manager':
            from .tyler_public import fetch_detail
            return fetch_detail(engine, source, namespace, request['external_id'], bounds, context, transport)
        if source.provider == 'boarddocs':
            from .boarddocs_public import fetch_detail
            return fetch_detail(engine, source, namespace, request['external_id'], bounds, context, transport)
        if source.provider == 'civicplus-select':
            from .civicclerk_detail import fetch_detail
            return fetch_detail(engine, source, namespace, request['external_id'], bounds, context, transport)
        if source.provider == "laserfiche-weblink" and urlsplit(source.url).hostname == "api.laserfiche.com":
            from .repository import fetch_entry
            return fetch_entry(source, namespace, request["external_id"], bounds, context, transport,
                               include_text=request.get("include_text", False))
        if source.provider == "legistar":
            from .legistar import fetch_record
            return fetch_record(source, namespace, request["external_id"], bounds, context, transport)
        if source.provider == "simbli":
            from dataclasses import replace
            from urllib.parse import parse_qs, urlencode
            from .simbli_detail import fetch_detail
            district = parse_qs(urlsplit(source.url).query).get("S", [])
            external_id = request["external_id"]
            if (len(district) != 1 or re.fullmatch(r"[1-9][0-9]{0,18}", district[0]) is None
                    or not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None):
                raise ValueError("Simbli detail requires the configured district and supplied numeric meeting ID.")
            target = replace(source, url=_origin(source.url) + "/SB_Meetings/ViewMeeting.aspx?" +
                             urlencode({"S": district[0], "MID": external_id}))
            return fetch_detail(target, namespace, bounds, context, transport)
        if source.provider == "civicweb":
            from .civicweb import fetch_record
            return fetch_record(source, namespace, request["external_id"], bounds, context, transport)
        if source.provider == "boardable":
            from .boardable_detail import fetch_record
            return fetch_record(engine, source, namespace, request["external_id"], bounds, context, transport)
        if source.provider == "digital-towpath":
            external_id = request["external_id"]
            if (not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None
                    or bounds.checkpoint is not None):
                raise ValueError("Digital Towpath single-detail reads require a numeric supplied meeting ID and no checkpoint.")
            from dataclasses import replace
            target = replace(source, url=_origin(source.url) + "/meetings/detail/" + external_id,
                             input_format="digital-towpath-detail-html")
            coverage = {"scope": "one numeric public meeting detail; supplied documents only",
                        "catalog_complete": False, "source_complete": False}
            if context.check_cancelled():
                return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
            started = monotonic()
            try:
                response_limit = min(bounds.parser_bytes, bounds.transfer_bytes)
                response = transport.request(target.url, byte_limit=response_limit,
                    deadline_seconds=bounds.deadline_seconds, allowed_origins=(_origin(target.url),),
                    allow_redirects=False)
                if context.check_cancelled():
                    return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
                if (response.status != 200 or response.url != target.url
                        or len(response.content) > response_limit
                        or monotonic() - started >= bounds.deadline_seconds):
                    raise ValueError("The requested detail is unavailable or left its bounds.")
                bundle, errors = parse_page(engine, target, namespace, response.content,
                                            target.input_format, bounds, context)
                if context.check_cancelled():
                    return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
                if monotonic() - started >= bounds.deadline_seconds:
                    raise ValueError("The requested detail mapping exceeded its total deadline.")
                if any(record["identity"]["external_id"] != external_id for record in bundle["records"]):
                    raise ValueError("The public detail does not match the requested meeting ID.")
                return OperationResult("partial", bundle, errors, coverage, context.operation_id)
            except Exception:
                return OperationResult("failed", errors=(Error("provider_detail_unavailable",
                    "The requested public detail could not be retrieved or validated.", source=target.url),),
                    coverage=coverage, operation_id=context.operation_id)
        if source.provider == "wistia":
            from .wistia import fetch_record
            return fetch_record(source, namespace, request["external_id"], bounds, context, transport,
                                caption_language=request.get("caption_language"))
        if source.provider == "champ":
            external_id = request["external_id"]
            current = urlsplit(source.url)
            event = re.fullmatch(r"/([A-Za-z0-9_-]+)/event/([0-9]+)/?", current.path)
            if (current.hostname != "play.champds.com" or event is None
                    or not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None):
                raise ValueError("CHAMP detail requires a public tenant event URL and a decimal event ID.")
            from dataclasses import asdict, replace
            target = replace(source, url=f"https://play.champds.com/{event[1]}/event/{external_id}",
                             input_format="champ-event-json")
            result = discover(engine, {"source": target.public_dict(), "bounds": asdict(bounds)}, None,
                              context, transport=transport, browser=browser)
            if result.data and result.data["bundles"]:
                incomplete = any(result.coverage.get(field) for field in
                                 ("failures", "truncated", "unknown_date_records", "unknown_body_records"))
                status = result.status if result.status in {"failed", "cancelled"} else (
                    "partial" if incomplete else "completed")
                return OperationResult(status, result.data["bundles"][0], result.errors,
                    {**result.coverage, "scope": "one provider event detail", "catalog_complete": False},
                    context.operation_id)
            return result
        return OperationResult.unsupported("fetch_record", reason=(
            "A single-record detail mapping is not verified for this provider; "
            "this does not establish that its upstream service lacks record retrieval."))
    if attachment is None:
        if content is None:
            if source.provider == "simbli" and urlsplit(source.url).path == "/SB_Meetings/ViewMeeting.aspx":
                from .simbli_detail import fetch_detail
                return fetch_detail(source, namespace, bounds, context, transport)
            return discover(engine, request, None, context, transport=transport, browser=browser)
        selected = discover(engine, request, content, context, transport=transport, browser=browser)
        if selected.data and selected.data["bundles"]:
            return OperationResult(selected.status, selected.data["bundles"][0], selected.errors,
                                   selected.coverage, context.operation_id)
        return selected
    if not isinstance(attachment, dict):
        raise ValueError("attachment must identify a captured record and document index.")
    record_key = attachment.get("record_key")
    index = attachment.get("index", 0)
    kind = attachment.get("kind", "documents")
    url_field = attachment.get("url_field", "url")
    if (not isinstance(record_key, str) or type(index) is not int or index < 0 or
            kind not in {"documents", "recordings"}):
        raise ValueError("Use a source identity record_key, nonnegative index and documents/recordings kind.")
    if not isinstance(url_field, str) or url_field not in (
            {"url", "audio_url", "video_url", "playback_url"} if kind == "recordings" else {"url"}):
        raise ValueError("Select url, or a captured recording audio_url/video_url/playback_url field.")
    bundle = None
    if content is not None:
        bundle, _ = parse_page(engine, source, namespace, content,
                               source.input_format or DEFAULT_FORMAT[source.provider],
                               bounds, context)
        record = next((r for r in bundle["records"]
                       if source_identity_key(r["identity"]) == record_key), None)
    elif engine.storage is not None:
        stored = engine.storage.get("records", record_key, scope=context.scope)
        record = stored.value if stored else None
        if isinstance(record, dict) and "record" in record:
            record = record["record"]
    else:
        record = None
    if not isinstance(record, dict):
        raise ValueError("The attachment record was not found in this scoped storage or supplied capture.")
    identity = record.get("identity") or {}
    if identity.get("provider") != source.provider or identity.get("namespace") != namespace:
        raise ValueError("The attachment belongs to a different provider or tenant.")
    if source.provider == "laserfiche-weblink" and urlsplit(source.url).hostname == "api.laserfiche.com":
        if kind != "documents" or index != 0 or url_field != "url" or identity.get("record_type") != "document":
            raise ValueError("Repository original content selects document index zero only.")
        from .repository import fetch_document
        return fetch_document(source, namespace, record, bundle, bounds, context, transport)
    documents = record.get("normalized", {}).get(kind) or []
    if index >= len(documents) or not isinstance(documents[index], dict):
        raise ValueError("The captured record has no attachment at the requested index.")
    document = documents[index]
    url = document.get(url_field)
    if not isinstance(url, str):
        raise ValueError("The captured attachment has no retrievable URL.")
    if source.provider == 'tyler-meeting-manager':
        from .tyler_public import documents as tyler_documents, recordings as tyler_recordings
        raw = record.get('original') or {}
        if (url_field != 'url' or identity.get('record_type') != 'meeting'
                or identity.get('external_id') != raw.get('id') or record.get('source_url') != source.url
                or document not in (tyler_documents(source, raw) if kind == 'documents' else tyler_recordings(raw))):
            raise ValueError('The selected Tyler attachment does not match its captured meeting.')
        if kind == 'recordings':
            return OperationResult('unsupported', {'record': record, 'attachment': None, 'bundle': bundle,
                'recording': document}, (Error('operation_unavailable',
                'The captured Tyler recording supplies a player link, not a recording-byte contract.'),),
                coverage={'recording_metadata': 'supplied_player_link', 'recording_bytes': 'not_implemented'},
                operation_id=context.operation_id)
    civicclerk_detail = (source.provider == 'civicplus-select' and isinstance(record.get('original'), dict)
                         and 'meeting' in record['original'] and 'event' in record['original'])
    civicclerk_asset = source.provider == 'civicplus-select' and document.get('source_field') in {
        'mediaSourcePathMp4', 'closedCaptionSourcePath', 'closedCaptionBlobPath'}
    if civicclerk_asset:
        from .civicclerk_detail import event_assets
        event = record['original'].get('event') if civicclerk_detail else record.get('original')
        caption_docs, recordings = event_assets(event)
        if (identity.get('record_type') != 'meeting' or not isinstance(event, dict)
                or identity.get('external_id') != str(event.get('id')) or record.get('source_url') != source.url
                or document not in (caption_docs if kind == 'documents' else recordings)
                or url_field not in ({'url'} if kind == 'documents' else {'url', 'video_url'})):
            raise ValueError('The selected CivicClerk asset does not match its captured published Event.')
    elif source.provider == 'civicplus-select' and kind == 'recordings':
        event = record['original'].get('event') if civicclerk_detail else record.get('original')
        if (not isinstance(event, dict) or event.get('isPublished') != 'Published' or event.get('isDeleted')
                or identity.get('record_type') != 'meeting' or identity.get('external_id') != str(event.get('id'))
                or record.get('source_url') != source.url or document.get('source_field') is not None
                or document.get('url') not in (event.get('externalMediaUrl'), event.get('mediaStreamPath'))
                or url_field not in {'url', 'video_url'}
                or (url_field == 'video_url' and (url != document.get('url')
                    or not urlsplit(url).path.lower().endswith('.mp4')))):
            raise ValueError('The selected CivicClerk recording is not supplied by its captured Event.')
    if civicclerk_detail and not civicclerk_asset and kind == 'documents':
        from .civicclerk_detail import declared_documents
        event, meeting = record['original']['event'], record['original']['meeting']
        if (kind != 'documents' or url_field != 'url' or identity.get('record_type') != 'meeting'
                or not isinstance(event, dict) or identity.get('external_id') != str(event.get('id'))
                or record.get('source_url') != source.url or document not in declared_documents(source, event, meeting)):
            raise ValueError('The selected CivicClerk file does not match its captured published meeting.')
    civicclerk_event = (source.provider == 'civicplus-select' and kind == 'documents'
                        and not civicclerk_detail and not civicclerk_asset)
    if civicclerk_event:
        from .civicclerk_detail import event_documents
        event = record.get('original')
        if (kind != 'documents' or url_field != 'url' or identity.get('record_type') != 'meeting'
                or not isinstance(event, dict) or identity.get('external_id') != str(event.get('id'))
                or record.get('source_url') != source.url):
            raise ValueError('The selected CivicClerk file does not match its captured Event.')
        supplied = event_documents(source, event)
        legacy = event_documents(source, event, legacy=True)
        matches = [api for api, old in zip(supplied, legacy, strict=True) if document in (api, old)]
        if not matches:
            raise ValueError('The selected file was not supplied by the captured published Event.')
        url = matches[0]['url']
    if source.provider == 'boarddocs':
        from .boarddocs_public import public_file_url
        canonical, file_id = public_file_url(source, url)
        original = record.get('original') or {}
        hrefs = original.get('public_file_links') or []
        matches = []
        for href in hrefs:
            try:
                matches.append(public_file_url(source, href)[0])
            except ValueError:
                continue
        if (kind != 'documents' or url_field != 'url' or identity.get('record_type') != 'meeting'
                or record.get('source_url') != source.url or canonical not in matches
                or document.get('external_id') != file_id):
            raise ValueError('The selected public file must match the original configured meeting capture.')
    deadline = monotonic() + bounds.deadline_seconds
    supplemental = []

    def retained_data():
        if supplemental and bundle is not None:
            saved_captures = bundle.setdefault("captures", [])
            hashes = {capture["sha256"] for capture in saved_captures}
            saved_captures.extend(capture for capture in supplemental if capture["sha256"] not in hashes)
        return {"record": record, "bundle": bundle, **({"captures": supplemental} if supplemental else {})}

    try:
        validate_url(url)
        allowed = _download_origins(source, url)
        parsed = urlsplit(url)
        if (source.provider == "laserfiche-weblink" and
                parsed.path.casefold().endswith("/docview.aspx")):
            if browser is None:
                raise ValueError("A guarded browser session is required for supplied WebLink page text.")
            from .laserfiche import scanned_text
            downloaded = scanned_text(source, url, bounds, context, browser)
            result = {"citation_url": url, "content_type": "text/plain",
                      "text": downloaded["text"], "pages": downloaded["pages"],
                      "page_count": downloaded["page_count"],
                      "text_completeness": downloaded["completeness"],
                      "sha256": hashlib.sha256(downloaded["text"].encode()).hexdigest()}
            return OperationResult("partial" if downloaded["completeness"] != "complete" else "completed",
                                   {"record": record, "attachment": result, "bundle": bundle},
                                   coverage={"sources": [source.public_dict()], "failures": [],
                                             "available_text": downloaded["completeness"]},
                                   operation_id=context.operation_id)
        if (source.provider == "gworks" and parsed.hostname == "api.gworks.cloud" and
                re.fullmatch(r"/cms/public/city/\d+/(?:agenda|minutes)/pdf/\d+/", parsed.path)):
            ready = False
            for _ in range(min(bounds.max_pages, 3)):
                if context.check_cancelled():
                    return OperationResult("cancelled", {"record": record, "bundle": bundle},
                                           operation_id=context.operation_id)
                response = transport.request(
                    url, byte_limit=min(bounds.parser_bytes, 65536),
                    deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=allowed)
                if response.status != 200:
                    raise ValueError("The provider document resolver did not succeed.")
                block = json.loads(response.content)
                if isinstance(block, dict) and block.get("status") == "ready":
                    signed = block.get("signedUrl")
                    if not isinstance(signed, str) or urlsplit(signed).scheme != "https":
                        raise ValueError("The signed document response is invalid.")
                    allowed = _download_origins(source, signed)
                    transfer_url, ready = signed, True
                    break
                if not isinstance(block, dict) or block.get("status") != "wait":
                    break
            if not ready:
                raise ValueError("The provider has not made the captured document available.")
        else:
            transfer_url = url
        resolution = None
        if source.provider == "boardbook":
            from .boardbook import resolve_document
            transfer_url, resolution = resolve_document(url, transport, bounds, context, deadline)
        boardable_viewer = (source.provider == "boardable" and kind == "documents"
                            and parsed.hostname == "app.boardable.com" and parsed.path.endswith("/view"))
        remaining_transfer = bounds.transfer_bytes
        if boardable_viewer:
            from .boardable_documents import resolve_document
            transfer_url, resolution = resolve_document(source, url, transport, bounds, context, deadline)
            remaining_transfer -= resolution["viewer_capture"]["byte_length"]
            if remaining_transfer <= 0:
                raise ValueError("The document viewer exhausted the transfer budget.")
        primegov_selected = (source.provider == "primegov" and kind == "documents"
                             and (record.get("original") or {}).get("info") == "Attachment")
        if primegov_selected:
            from .primegov_documents import resolve_document
            response, resolution = resolve_document(source, url, record, document, bounds, context, transport,
                                                    deadline, _download_origins, supplemental)
        else:
            if context.check_cancelled():
                return OperationResult("cancelled", {"record": record, "bundle": bundle},
                                       operation_id=context.operation_id)
            response = transport.request(
                transfer_url, byte_limit=remaining_transfer,
                deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=allowed,
                **({"allow_redirects": False} if boardable_viewer or source.provider == "civicplus-select" or source.provider in {"onbase", "tyler-meeting-manager", "boarddocs", "utah-public-notice"} else {}))
        if context.check_cancelled():
            return OperationResult("cancelled", retained_data(), operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError("The captured attachment exceeded its total deadline.")
        if source.provider in {"boarddocs", "utah-public-notice"} and response.url != transfer_url:
            raise ValueError("The supplied asset changed its captured route.")
        if source.provider == "utah-public-notice" and document.get("kind") == "calendar":
            media_type = response.content_type.split(";", 1)[0].strip().lower()
            if (media_type != "text/calendar" or not response.content.startswith(b"BEGIN:VCALENDAR\r\n")
                    or not response.content.rstrip().endswith(b"END:VCALENDAR")):
                raise ValueError("The supplied Utah calendar did not return calendar bytes.")
        if response.status != 200:
            raise ValueError("The captured attachment did not return HTTP 200.")
        if (source.provider == "civicplus-select") and response.url != transfer_url:
            raise ValueError('The selected CivicClerk file changed its captured route.')
        if (source.provider == "onbase" and kind == "documents" and not response.content.startswith(b"%PDF-")
                and response.content_type.split(";", 1)[0].strip().lower() in {"text/html", "application/xhtml+xml"}):
            from .onbase_documents import resolve_document
            response, resolution = resolve_document(source, url, record, response, bounds, context, transport, deadline,
                                                     captures=supplemental)
        pdf_expected = (kind == "documents" and (
            source.provider == 'tyler-meeting-manager' or
            urlsplit(transfer_url).path.lower().endswith(".pdf") or
            (boardable_viewer and str(document.get("title", "")).lower().endswith(".pdf")) or
            response.content_type.split(";", 1)[0].strip().lower() == "application/pdf"))
        if ((resolution and not boardable_viewer and not primegov_selected) or pdf_expected) and not response.content.startswith(b"%PDF-"):
            raise ValueError("The supplied PDF download did not return PDF bytes.")
        if boardable_viewer and (response.content_type.split(";", 1)[0].strip().lower() in {
                "text/html", "application/xhtml+xml"} or response.content.lstrip().lower().startswith(
                    (b"<!doctype html", b"<html"))):
            raise ValueError("The document download returned another HTML viewer, not original file bytes.")
        if len(response.content) > remaining_transfer:
            raise ValueError("The document exceeds the configured transfer byte limit.")
        if not primegov_selected and _origin(response.url) not in allowed:
            raise ValueError("The document left its configured download origins.")
        if context.check_cancelled():
            return OperationResult("cancelled", retained_data(), operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError("The captured attachment exceeded its total deadline.")
        return OperationResult("completed", {
            **retained_data(), "attachment": {
                "citation_url": document.get("citation_url") or (record.get("normalized", {}).get("url") if primegov_selected else None) or document.get("url") or url,
                "selected_url_field": url_field, "content_type": response.content_type,
                "byte_length": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(),
                "content_base64": base64.b64encode(response.content).decode("ascii"),
                "text_availability": "not_extracted",
                **({"resolution": resolution} if resolution else {}),
            },
        }, coverage={"sources": [source.public_dict()], "failures": [], "unavailable_attachments": [],
                     **({"catalog_complete": False, "source_complete": False} if primegov_selected else {})},
                               operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", {**retained_data(), "attachment": None},
                               coverage={"sources": [source.public_dict()], "cancelled": True},
                               operation_id=context.operation_id)
    except Exception:
        return OperationResult("partial", {**retained_data(), "attachment": None},
                               (Error("attachment_unavailable",
                                      "The captured attachment could not be retrieved; the record is retained.",
                                      retryable=True, source=source.url),),
                               {"sources": [source.public_dict()], "failures": ["attachment_unavailable"],
                                "unavailable_attachments": [{"record_key": record_key, "index": index,
                                                            "kind": kind, "citation_url": url}]},
                               context.operation_id)
