# Select native event updates

The pinned Fishers CivicClerk v1 OpenAPI documents `PUT /v1/Events/{key}`,
its 18-property EventUpdateApiModel, and the GET EventModel. QuorumRelay supports
this exact native update through `plan_write`, `commit_write` and `receipt`.
Execution is verified synthetically. No live provider write has occurred.

Use public write entity `event`, operation `update`, resource_id containing the
positive native event ID, and the same ID in meeting_id. No parent, file,
language or page selector is accepted. The existing Select source/tenant/origin
policy applies; trusted credentials must explicitly allow `event:update` and
the selected meeting/resource IDs. Caller JSON cannot grant these permissions.

The change fields have exactly two keys:

```python
fields = {
    "native_request": complete_native_update_dto,
    "expected_readback": exact_intended_native_get_snapshot,
}
```

`native_request` must explicitly supply **all 18 properties**, including nullable
ones. This deliberately exceeds the vendor's minimum required-property list so
omitted defaults cannot silently select clock, media or publication behavior:

| Native property | Value |
|---|---|
| eventName | Nonempty string |
| eventDescription | String or null |
| eventStartDate | Native date-time literal |
| eventStartTime | Nonempty native clock string |
| address1, address2, city, state, zipCode | Each a string or null |
| startEventAutomatically | Boolean, preserved from GET |
| streamId | Int32, preserved from GET |
| eventCategoryId | Int32 |
| isPublished | Native enum 0/1/2, preserved from GET |
| publishStart | Native date-time literal, preserved from GET |
| externalMediaUrl | String or null, preserved from GET |
| actualStartTime, meetingEndTime | Each a native clock string or null |

The library sends these literal values unchanged. It does **not** derive clock
strings from eventDate/startDateTime, interpret time zones, or infer the inverse
mapping between native request and response fields. The caller must already have
the intended native request and native postcondition. This path does not close
the separate research gap for automatic normalized date/time conversion.

`expected_readback` must contain the same properties as the actual GET before
planning and conform to the pinned EventModel. Publication status/start,
automatic start, stream, external media URL, template ID, location identity and
unrelated GET fields must remain unchanged. Editable postcondition fields are
eventName/Description, eventDate/startDateTime, native category ID/name variants,
eventLocation address values, actualStartTime and meetingEndTime. Direct shared
request/readback keys and nested location values must agree. No implicit media,
publication, template change or new location identity is exposed.

Planning retrieves the native before snapshot and binds it, the exact native PUT
and expected GET to the immutable plan. A supplied expected_version must equal
the complete before snapshot's canonical hash. Commit reauthorizes and rereads
that snapshot before sending. This is preflight comparison, not atomic vendor CAS.

Only documented 200/204 PUT success followed by **exact full native GET equality**
confirms success. Lost responses, unapproved side effects, changed dates,
missing fields, cancellation and deadline expiry leave uncertainty when the PUT
may have been accepted. Durable intent and the exact event ID permit read-only
reconciliation after restart. A possibly accepted PUT is never automatically
resent. Current server applicability and undocumented side effects are not
claimed by the synthetic test.

Event creation remains separate and unimplemented: its template/default effects
and selected destination publication configuration are not established by this
update contract. No meeting/item create, document upload or account acquisition
requirement is added. Reproducible vendor model extraction lives in
`scripts/pin_select_event_contract.py`; tests and receipt identify the executed
scope in `verification/select-native-event-update-2026-11-15.json`.
