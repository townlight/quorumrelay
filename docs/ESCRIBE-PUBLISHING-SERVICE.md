# eSCRIBE Publishing Service

This local source mapping comes from the deployed vendor PublishingService WSDL
and five imported XSDs captured on November 15, 2026. The service landing page
declared both `?wsdl` and `?singleWsdl`. The earlier denial of `?singleWsdl` did
not establish that the other metadata URL was inaccessible: `?wsdl` returned
HTTP 200 XML, 222,643 bytes. All five exact declared schemas also returned 200.
[Original metadata and hashes](capabilities/evidence/escribe-publishing-wsdl/source.json)
are checked in. No SOAP operation was called on the live service.

The binding is SOAP 1.2 over HTTPS with WS-Addressing 2005/08. The pinned policy
does not require a client certificate. It does not document an application login
exchange or guarantee anonymous operation access. Destination authentication, if
needed, belongs to an explicitly injected trusted transport. No speculative
token, cookie or authorization protocol is implemented.

Use an explicit source with `input_format="escribe-publishing-soap-xml"` and the
exact tenant `/WebService/eSCRIBE.Internet.WebService.svc` URL. The namespace is
derived from that host. A publishing host and a public portal host are separate
source namespaces; this mapping does not guess a cross-host identity merge.

## Explicit reads

```python
from quorumrelay import Bounds, Source, create_engine

source = Source(
    "escribe",
    "https://selected-tenant.escribemeetings.com/WebService/eSCRIBE.Internet.WebService.svc",
    input_format="escribe-publishing-soap-xml",
)
result = create_engine().fetch(source, {
    "api_method": "MeetingGetById",
    "api_parameters": {"MeetingId": "11111111-1111-4111-8111-111111111111"},
}, bounds=Bounds(max_pages=1, max_records=1, deadline_seconds=15))
```

The example identifiers are synthetic. Do not send it to an unrelated tenant.
The selected destination must authorize the read.

Implemented record methods are MeetingGetById/GetByPortal,
AgendaGetById/GetByMeeting, AgendaItemGetById/GetByAgenda,
AttachmentGetById/GetByAgenda/GetByAgendaItem and DocumentGetById. Parameters use
their exact XSD names and native identifier objects; missing or nil selection
parameters fail before network. Collection rows must match the supplied native
portal, meeting, agenda or item parent. Responses exceeding `max_records` fail;
there is no invented server paging, continuation, date filter or complete catalog.

DocumentGetContent first reads the exact DocumentGetById metadata, then retrieves
the SOAP base64 content. Supply `{"Id": 23}` and allow two request pages. Exact
bytes must match the supplied FileSize. Both SOAP responses and the decoded
content remain captured with hashes. A failed content step retains independently
verified metadata. The content method supplies no MIME field, so bytes are opaque
`application/octet-stream`; no PDF interpretation, text extraction or playback
is claimed.

Record reads return partial scope. Original XML, native fields, compound IDs,
relationships and available text survive persistence, reopening and neutral
JSON/JSONL/ZIP export. Meeting times remain native literals. Language-map integer
keys remain source keys, without an inferred language. Supplied Minutes text is
not interpreted as structured motions or votes. Unknown model fields, SOAP faults,
wrong method/addressing, duplicate fields and invalid typed values fail explicitly.

## Record writes

The existing plan/commit coordinator now supports native `meeting`, `agenda`,
`agenda_item`, `attachment` and `document` record create/update. For those operations, `document` means its metadata record; Attachment.Record binds an existing DocumentId to an
explicit native meeting/agenda/item identifier. Those record operations do not upload bytes; the separately scoped upload below does.
Meeting.VideoURL is a supplied reference, not a recording upload.

Server-side `context.credentials["escribe"]` must bind the exact `endpoint`,
`tenant`, `allowed_namespaces`, `permissions` such as `meeting:update`, and
`resource_ids`. Meeting records additionally require allowed `portal_ids`;
related agenda/item/attachment operations require `meeting_ids` and an explicit
`change.meeting_id`. Compound resource IDs use canonical sorted JSON objects
without spaces. No private credentials are serialized into plans.

Use native field names without case conversion. Create requires every field of
the selected pinned record model, including explicit nullable values. Update
reads the complete model, preserves its other fields, rejects identity changes
and compares the full preflight fingerprint before sending. Expected version is
that fingerprint; this is not an atomic upstream compare-and-swap guarantee.

The plan contains exact native before/after models and method parameters. Commit
requires its exact plan ID/hash. Durable intent precedes sending; returned create
identities are saved before readback. Full-model readback must match. Duplicate
commits and restart reconciliation do not repeat a mutation. If a create response
is lost before its identity is saved, the receipt stays uncertain: no unique
lookup or replay rule is inferred. Cancellation or an unverifiable response after
sending likewise preserves uncertainty and reconciles by read methods only.

These are vendor-schema synthetic execution results. No vendor write was made;
runtime access, server-side transformations, effective publication/visibility and
current deployment compatibility remain separately qualified. No publication, unpublish, delete, portal administration or workflow method is
called. Requested DatePublished/IsPrivate model values remain explicit plan fields;
their effective visibility consequences are not inferred from successful field readback.

## Explicit chunk upload with whole-document hash verification

`document` / `upload` accepts one scoped file part named `Chunk` and these explicit
fields: `offset`, `length`, `IsPrivate`, `expected_document_sha256`. The first three
are native request fields. The expected hash is a local readback condition, not a
vendor parameter. Length must equal the supplied chunk byte count; offset is a
caller-selected nonnegative Int32. No splice, append, truncate or replacement rule
is computed by the library. The server policy must grant `document:upload` for the
exact existing document resource ID.

Planning reads the complete document metadata and bytes, checks FileSize, retains
the original bytes in scoped immutable storage for recovery, and binds a combined
metadata/content fingerprint. IsPrivate must match the existing record. The plan
contains an immutable chunk reference and the caller's intended whole-document
hash. It does not place the raw chunk or original document bytes in plan JSON.

Commit repeats both preflight reads, compares the fingerprint, sends one exact
DocumentUpload request, and reads metadata/content again. Success requires the
caller-declared final whole-document hash, the native FileSize matching the actual
bytes, and preservation of the remaining metadata. At least five request pages
are required: two preflight reads, one upload and two readback calls. Byte and
deadline bounds remain active throughout. Failed or different server behavior
stays uncertain and reconciles by reads only; a void response alone proves no
completed upload. Original bytes are available for explicit recovery, never an
automatic rollback or additional write.

This narrow execution contract does not establish general multi-chunk sequencing,
append/replacement/truncation semantics, processing readiness, automatic metadata
or meeting association, or a vendor file-import format. Those remain targeted
research gaps, not proof that outside help is the only way to resolve them. No
clear, append, finalize, publication or processing-poll method is inferred.

The scoped runtime contract is reproducibly generated by
`scripts/pin_escribe_contract.py` from the checked-in metadata without network.
[Execution receipt](verification/escribe-publishing-2026-11-15.json) distinguishes
synthetic record execution from actual metadata GET observations.
