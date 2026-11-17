# CivicWeb FilePro document reads

This additive integration uses the vendor-hosted [FilePro Connector guide dated 24 April 2014](https://livetest-us-east-1.civicweb.net/document/4758/) and the exact Trail/Live Test document-service WSDLs captured on 12 November 2026. The guide describes public document/search reads without login or session cookies. QuorumRelay sends no login request, cookie or credential for these operations. Deployment applicability is explicit; the historical guide is not a universal current-version guarantee.

The original `civicweb-html` meeting listing and supplied meeting-detail mapping are unchanged. Select `civicweb-filepro-soap-xml` for this document service. Its folder/document IDs are independent of calendar meeting IDs. No meeting association, agenda/minutes classification, date, body or time zone is inferred from document names or paths.

```python
from quorumrelay import Bounds, Source, create_engine

engine = create_engine()
source = Source(
    "civicweb", "https://your-tenant.civicweb.net/Portal/",
    input_format="civicweb-filepro-soap-xml",
    options={"folder_id": 0},
)
result = engine.discover(source, bounds=Bounds(max_records=100))
# result is partial: one folder, not a complete meeting archive.
```

`folder_id=0` requests the documented root; another supplied positive Int32 requests that folder. `GetChildList` fixes `path` and `controlId` to empty strings and uses the vendor's explicit document-provider identifier. Folder and document records retain native IDs, supplied parent IDs, unknown fields and exact response bytes. A local continuation token resumes the same response after the record bound; a changed response requires a restart. This operation does not recursively walk every folder. Date/body values absent from these responses remain unknown and are retained with coverage labels.

For original bytes, set `options={"filepro_resource": "original"}` and call `engine.fetch_record(source, "77")` using the configured source with those options. Use `pdf` for `GetPdfFile`; use `meeting_pdf` plus an explicit positive `options.meeting_id` for `GetMeetingAttachmentPdfFile`. These PDF variants require PDF bytes and extension. Returned exact file content, byte length, SHA-256 and extension are in `result.data["extensions"]["file"]`; original HTML and all raw values remain in the record/capture. An HTML-only result stays partial and does not become a successful original-file download. Original bytes may be any documented extension; they are not automatically converted, rendered or executed.

The SOAP file result does not echo its document ID. The identity is labelled `requested_provider_identifier`, bound to the supplied request, without claiming independent server identity readback. A meeting relationship is retained only for the explicit meeting-PDF request. The original response is always preserved; local SHA-256 proves captured bytes, not an independent vendor-provided digest.

Native document search uses the same explicit format:

```python
result = engine.execute("search", {
    "native": True,
    "source": source.public_dict(),
    "query": {"terms": ["Council"], "phrases": ["capital budget"], "limit": 10},
    "bounds": {"max_records": 100, "max_pages": 4},
})
```

The vendor candidate request uses `allWords` and the first `exactPhrase`; all requested terms/phrases are checked locally against returned title, sample and path text. It returns document candidates, then requests at most 50 IDs per detail batch. Candidate IDs and mid-batch raw response hashes bind continuation to the query, configured source, caller and grants. The hit limit counts local matches; unrelated candidates do not consume it. `max_records` limits candidates examined and `max_pages` limits detail responses; the candidate-ID response still counts toward transfer/deadline bounds. Query body/date fields not supplied by the API remain explicitly unknown. These snippets do not prove that the full original document was searched locally; catalog and calendar coverage stay partial.

The guide's summary says `GetSearchResultsDetails` and its child sample uses `controlID`. Both captured WSDLs establish `GetSearchResultDetails` and `controlId`; the binding follows the WSDL. The guide's convenience `GetSearchResultsBySearchCriteria` is absent from those WSDLs and is not called. The exact schema/action comparison is tested against both independent captured WSDL files.

Saved raw folder/search SOAP can be normalized without network or credentials:

```python
saved = engine.normalize(source, raw_soap_bytes, input_format="civicweb-filepro-soap-xml")
```

For a saved file response, add `options.document_id` with its supplied request ID. Without that context the parser rejects an invented identity. Parentless supporting responses that do not carry usable record IDs are not silently turned into meeting records.

All interfaces use the same registered operations: Python SDK, CLI request JSON, HTTP operation endpoints and MCP `discover`/`fetch`/`search`/`normalize` tools. Existing namespace/operation authorization applies. SOAP POST targets only the exact configured HTTPS tenant's `/Global/WebServices/Document.asmx`, with redirects disabled. XML DTD/entities, malformed base64, foreign namespaces, duplicate/missing typed fields, oversized/deep responses, cancellation, deadlines and cumulative request/response transfer bounds fail closed. Raw HTML is retained as evidence; normalized search text omits executable script/style content.

Evidence: [source pins and limitations](capabilities/evidence/civicweb-filepro/source.json), [packaged contract](../src/civic_data_connectors/data/civicweb_filepro.json), `tests/test_civicweb_soap.py` and `tests/test_civicweb_filepro.py`. Thirty-four distinct synthetic cases passed through the binding and real engine operations. This read-only document contract does not establish calendar/meeting create/update/upload fields, recursive archive completeness, private authenticated FilePro behavior or vendor-wide version compatibility. Those original-plan outcomes remain separate work; live tenant access is not a synthetic-verification gate.
