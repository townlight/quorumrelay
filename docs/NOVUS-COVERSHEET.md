# Novus public cover sheets

Current local source accepts `novus-public-coversheet-html` for an exact supplied
HTTPS tenant `/agendapublic/Coversheet.aspx?ItemID=...&MeetingID=...` URL. The
existing listing parser preserves these links; select the supplied URL explicitly
as a configured source. Default configured discovery/fetch selects this format;
saved normalization can name it explicitly. This route is additive to the original
meeting-export reader and is not included in frozen dev8.

```python
from quorumrelay import Source, create_engine

source = Source(
    "novusagenda",
    "https://ebps.novusagenda.com/agendapublic/Coversheet.aspx?ItemID=12406&MeetingID=996",
    input_format="novus-public-coversheet-html",
)
engine = create_engine()
with open("coversheet.html", "rb") as saved:
    result = engine.normalize(source, saved.read(), input_format=source.input_format)
```

The captured public form independently binds the selected native ItemID and
MeetingID. One agenda-item record retains that native item identity and an explicit
meeting parent, subject, displayed meeting date, rendered text and source sections.
The complete original HTML is retained in the capture. Recommendations and blank
voting controls remain rendered source content; they do not establish adopted
motions, votes or attendee actions. No timezone is inferred.

Only supplied same-origin `AttachmentViewer.ashx` links with a native AttachmentID
and the current ItemID become associated supporting-document locators. Duplicate
identities, ambiguous query values, changed form context and foreign origins are
rejected. Transfer is a separate bounded `fetch_attachment` operation using the
existing capture/source policy and download safeguards. A locator does not prove
retrievable PDF bytes.

Evidence: [bounded capture and synthetic engine checks](verification/novus-public-coversheet-2026-11-12.json).
Six new distinct cases cover saved/default configured reads, native relationships,
text search, neutral export, synthetic attachment transfer and changed-context
denials; one existing saved-listing regression is reused. The initial configured
case exposed a listing-only dispatch branch and passed after the scoped correction.
One public page/template is covered. MeetingView, other cover-sheet templates,
Minutes, automatic listing-to-detail traversal and arbitrary-ID retrieval are not
claimed by this route. No script/form action is executed by the parser.
