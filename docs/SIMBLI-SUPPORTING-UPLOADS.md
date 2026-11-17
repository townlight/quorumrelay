# Simbli supporting-document uploads

The registered Simbli dispatcher supports a new file on an existing editable,
nondeleted, no-workflow agenda item. It uses the native supporting-document
component's multipart upload and attachment descriptor, then the existing native
item lock and full-item save. Source excerpts and the historical binary delivery
observation are recorded in
`capabilities/evidence/simbli-supporting-upload-followup/source.json`.

Use the same exact meeting source and private tenant/session/user/item bindings
as `SIMBLI-WRITES.md`. Credentials additionally require
`agenda_item_attachment:upload` and a `supporting_fields` allowlist containing
the selected native `FieldName`. `agenda_item:update` remains required because
the native workflow saves the whole item. The fresh staff page must expose its
native encrypted module context; a caller cannot supply an alternate module.

The change has these fields:

```json
{
  "key": "supporting-file",
  "entity": "agenda_item_attachment",
  "operation": "upload",
  "meeting_id": "123",
  "parent_id": "176766",
  "fields": {"field_name": "fileAttachment"},
  "files": [{
    "part": "file",
    "filename": "supporting.pdf",
    "content_type": "application/pdf",
    "file_handle": "<scoped staged file handle>"
  }]
}
```

Omit `resource_id`: the new attachment has no final native ID during planning.
The coordinator accepts its usual scoped file handle or inline base64 input and
binds immutable SHA256/length references into the exact approved plan. The parent
must be an explicitly authorized existing agenda ID. The selected content field
must be native `ControlType=9`. Empty arrays and native null attachment lists are
supported. A preexisting original filename collision is rejected during planning.
The native uploader's blocked extensions, including executable/script, shortcut
and HTML types, are rejected before any network request.

Planning reads the fresh page, tree and item DTO without a lock or mutation.
Commit compares the complete approved state, acquires the native item lock and
compares again under that lock. It uploads multipart `file` with fresh context
and native new-file selectors `attachmentId=0&id=0`. The returned `Data.isSuccess`
and `Data.FileDetail` must supply the native descriptor with matching original
filename, MIME and byte length. The descriptor is durably recorded before save.

The native UI inserts the new attachment first, numbers it `Order=1`, renumbers
existing attachment order from2, and inherits the existing field visibility.
These effects are part of the planned operation. It does not change field
visibility, item title, comments, hyperlinks or other content. Existing attachment
tokens are rebound from fresh reads and never persisted as raw secrets. The full
item DTO is saved through the same editing lock and cleanup path as title writes.

Independent fresh native reads must find exactly one new attachment in that
selected field, preserve unrelated state and resolve its site, meeting and final
attachment ID. The declared Module1 `Meetings/Attachment.aspx` route must then
return the approved original MIME, SHA256 and exact byte length. HTML challenges,
redirects, transformed previews and different bytes leave the result uncertain.
The historical binary PDF capture establishes a binary-delivery branch; current
anonymous requests returned a security challenge. No live staff upload has been
performed for adapter acceptance.

Recovery reads only. A returned upload descriptor without a durable item-save
attempt remains uncertain; the adapter does not replay an upload, resave an item,
search filenames for an unknown temporary upload or delete a possible orphan.
A lost save response can be reconciled through the selected native item and
original-file readback. Native lock release is attempted in cleanup, including
after cancellation. A failed release remains an explicit durable cleanup error.

The operation covers one new supporting attachment at a time. It exposes no
replacement or deletion. New items/meetings, minutes and publication remain
unfinished. Publication visibility follows the already configured
item/field; there is no implicit visibility change or publication operation.
