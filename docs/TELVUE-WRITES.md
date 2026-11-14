# TelVue Connect playlist writes

Current local source supports two narrowly mapped operations on an existing
Connect playlist. The vendor's anonymously served application bundle declares
the POST paths and form fields; the official Connect v2 guides describe the
playlist and playlist-item readback. See the [pinned source and limits](capabilities/evidence/telvue-client-write/source.json).
This is browser-client compatibility with synthetic execution, not a vendor
promise of a stable public write API. No live mutations were performed.

Configure the exact source URL `https://connect.telvue.com` and an explicit
application namespace. Application-owned `OperationContext.credentials["telvue"]`
must bind `tenant`, `origin`, `allowed_namespaces`, `meeting_ids` and `playlist_ids`.
Supply `session_cookie` and `csrf_token` for the native POST, and `access_key` plus
`secret_passphrase` for documented v2 GET readback. QuorumRelay does not sign in,
obtain credentials or grant API access. These values never enter saved plans or
receipts. Live deployments must establish that both credential sets access the
intended playlist. Missing credentials do not prevent synthetic verification.

Use the normal exact-plan approval lifecycle:

```python
change = {
    "key": "order-meeting-playlist",
    "entity": "playlist_order", "operation": "update",
    "resource_id": "837", "meeting_id": "7",
    "fields": {"playlist_item_ids": [37883, 37882]},
}
```

Permission `playlist_order:update` is required. The list must be an exact
permutation of all items returned for that playlist, using native playlist-item
IDs. This does not add or remove entries. The native request is
`POST /playlists/837/reorder` with repeated `playlist_item[]` form fields.

To add existing media, use entity `playlist_membership`, operation `create`,
the same playlist `resource_id` and application `meeting_id`, and
`fields={"medium_ids": [32263]}`. Require permission `playlist_membership:create`
and an explicit trusted `medium_ids` allowlist of string native media IDs.
The request is `POST /bulk/playlists/837/playlist_items/create` with repeated
`medium_ids[]` fields. Existing media-only playlists and empty playlists are
supported; duplicate requested media or media already in that playlist are
rejected. Streams, mixed playlists, removals and creation of playlists are not
mapped by this adapter. No insertion order is promised for new entries.

Both operations require complete bounded readback for the selected playlist:
`playables_count` must equal returned item count, every native parent must match,
and explicit sequence positions must be unique and contiguous. There is no
inferred pagination. A mismatch fails preparation or leaves a submitted mutation
uncertain. Reorder requires exact full resulting items, including unknown fields;
membership addition requires every existing item unchanged apart from sequence,
and exactly the requested new media, each with a distinct new native item ID.

Commit compares the saved before snapshot with fresh readback. This is a
preflight comparison, not atomic upstream CAS. It persists mutation intent before
POST and requires GET confirmation afterward. A timeout or unconfirmed result
uses read-only reconciliation on retry, never another POST. Cancellation,
tenant/namespace policy, byte/record/deadline limits and no-redirect transport
remain enforced. The `meeting_id` is an application authorization relationship;
these routes do not create a vendor meeting association.

Upload remains unmapped: the public client consumes runtime `fileUrl`, `dvdUrl`,
`uploadParams` and user/organization configuration without supplying a concrete
initializer in this bundle. It does not establish created-media identity,
processing/readiness or meeting-association readback. The exact missing contract
is a sanitized deployment-matched upload initializer and request/response plus
the processing/association readback specification, not a live account or live
upload. HyperCaster and CloudCast contracts are not substituted for Connect.
