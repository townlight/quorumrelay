# Legistar legislative text preparation

The official [Legistar Text Editor guide](https://support.granicus.com/articles/How_To/Drafting-Legislative-Files-Legistar-Text-Editor), Step 2 Option 2, documents importing a `.txt` or `.rtf` file with `..title` and `..body` sections. QuorumRelay prepares a single plain-text file from explicit caller-supplied fields:

```python
result = engine.execute("export", {
    "source": {"provider": "legistar", "url": "https://webapi.legistar.com/v1/example"},
    "provider_specific": True,
    "format": "legistar-legislative-text",
    "title": "Budget action",
    "body": "Explicit legislative text supplied by the application.",
    "text_encoding": "ascii",
})
```

`text_encoding` is required: `ascii`, `cp1252`, or `utf-8`. The vendor guide does not specify an encoding. Select one compatible with the destination; unencodable characters fail rather than being replaced. The exporter writes the two section markers on separate lines and normalizes supplied line endings to CRLF. Input lines beginning with `..` after whitespace are rejected because the guide supplies no escaping convention. Nonempty plain text is required for both sections.

The response contains base64 file bytes and a manifest with `legislative-text.txt`, the selected encoding, length, SHA-256 and projection losses. `stream=true` stores the same bytes as an application-scoped artifact through the existing storage/download contract. Byte limits, cancellation and deadlines apply through final encoding/storage. Export namespace permissions apply.

Only title and body enter the file. IDs, dates, statuses, meeting relationships, provenance, attachments, formatting and media are not embedded. Local hashes verify preparation; they do not prove that a particular Legistar installation accepted an import. The documented workflow opens the file inside an existing legislative file's Text Editor. QuorumRelay performs no vendor transfer, record creation, import, publication or meeting association. Historical migration packages and media import remain separate unresolved contracts.

The original official HTML and its request/hash receipt are pinned under `capabilities/evidence/legistar-text-import/`. Synthetic tests assert exact output bytes, encoding failures, section-injection rejection, bounds, cancellation and scoped artifact persistence/reopening. No live Legistar mutation was performed.
