"""Official related-record wire shapes; isolated bounded transport and replay."""

import base64
import json
import hashlib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response


class RelatedTransport:
    def __init__(self, prefix="Vote", count=3):
        self.prefix, self.calls = prefix, []
        self.rows = [{prefix + "Id": i, prefix + "EventItemId": 8, prefix + "PersonId": 20 + i,
                      prefix + "PersonName": "Councilor " + str(i), prefix + "ValueId": 1,
                      prefix + "ValueName": "Yea" if prefix == "Vote" else "Present",
                      prefix + "RowVersion": "QEA=", prefix + "LastModifiedUtc": "2026-11-11T00:00:00Z",
                      "unknown": {"preserve": [None, False]}} for i in range(1, count + 1)]

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        query = parse_qs(urlsplit(url).query)
        if "$filter" in query:
            after = int(query["$filter"][0].split()[-1])
            value = [row for row in self.rows if row[self.prefix + "Id"] > after][:int(query["$top"][0])]
        else:
            value = next(row for row in self.rows if str(row[self.prefix + "Id"]) == urlsplit(url).path.split("/")[-1])
        return Response(url, json.dumps(value).encode(), "application/json", 200)


@pytest.mark.parametrize("kind,prefix,route,fmt", [
    ("vote", "Vote", "Votes", "legistar-votes-json"),
    ("roll_call", "RollCall", "RollCalls", "legistar-rollcalls-json"),
])
def test_related_collection_keyset_checkpoint_detail_and_saved_replay(kind, prefix, route, fmt):
    transport = RelatedTransport(prefix)
    engine = create_engine(provider_transport=transport)
    source = Source("legistar", "https://webapi.legistar.com/v1/city", options={"page_size": 2})
    context = OperationContext(credentials={"legistar_token": "secret-token"})
    first = engine.fetch_related(source, "8", kind, bounds=Bounds(max_records=2), context=context)
    assert first.status == "partial", first.public_dict()
    assert len(first.data["records"]) == 2
    checkpoint = first.coverage["checkpoint"]
    second = engine.fetch_related(source, "8", kind, bounds=Bounds(checkpoint=checkpoint), context=context)
    assert second.status == "completed", second.public_dict()
    assert [r["identity"]["external_id"] for r in second.data["records"]] == ["3"]
    assert "secret-token" not in json.dumps(first.public_dict())
    assert parse_qs(urlsplit(transport.calls[1][0]).query)["$filter"] == [prefix + "Id gt 2"]
    assert transport.calls[0][1]["allowed_origins"] == ("https://webapi.legistar.com",)
    detail = engine.fetch_related(source, "8", kind, external_id="1")
    assert detail.status == "completed", detail.public_dict()
    row = detail.data["records"][0]
    assert row["original"]["unknown"] == {"preserve": [None, False]}
    assert row["source_revision"]["value"][prefix + "RowVersion"] == "QEA="
    assert row["identity"]["parent"]["external_id"] == "8"
    assert row["identity"]["parent"]["record_type"] == "agenda_item"
    assert row["relationships"][0]["relation"] == "agenda_item"
    assert row["citation_urls"][-1].endswith(f"/EventItems/8/{route}/1")
    assert "meeting_date" not in row["normalized"]
    raw = base64.b64decode(detail.data["capture"]["content_base64"])
    replay = engine.normalize(Source("legistar", source.url), raw, input_format=fmt)
    assert replay.status == "completed"
    assert replay.data["records"][0]["identity"] == row["identity"]
    assert engine.fetch_related(source, "9", kind, bounds=Bounds(checkpoint=checkpoint)).status == "failed"
    assert engine.fetch_related(source, "8", kind, bounds=Bounds(checkpoint=checkpoint),
                                context=OperationContext(principal="different")).status == "failed"


def test_related_failure_scope_bounds_and_untrusted_ids():
    transport = RelatedTransport()
    engine = create_engine(provider_transport=transport)
    source = Source("legistar", "https://webapi.legistar.com/v1/city")
    for parent, kind in (("../8", "vote"), ("8", "invented"), (8, "vote")):
        assert engine.fetch_related(source, parent, kind).status == "failed"
    assert not transport.calls
    assert engine.fetch_related(source, "8", "vote", context=OperationContext(
        allowed_namespaces=frozenset())).status == "failed"
    assert not transport.calls
    assert engine.fetch_related(source, "8", "vote", bounds=Bounds(parser_bytes=1)).status == "failed"
    transport.rows[0]["VoteEventItemId"] = 9
    assert engine.fetch_related(source, "8", "vote").status == "failed"
    context = OperationContext()
    context.cancellation.set()
    assert engine.fetch_related(source, "8", "vote", context=context).status == "cancelled"


@pytest.mark.parametrize("kind,prefix,digest", [
    ("vote", "Vote", "45499f4d858159245edbc9d5b1d273d0ff5ca8c3687250faff4ba8c11d64a13b"),
    ("roll_call", "RollCall", "acc86baf85f172624442007c7cb55a04b0275f7ad7faafb2d48e98c0f8432b84"),
])
def test_independent_public_related_capture_preserves_supplied_rows(kind, prefix, digest):
    raw = (Path(__file__).parent / "fixtures" / "brief-discovery" /
           ("legistar-olympia-" + kind + "-page.json")).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    fmt = "legistar-votes-json" if kind == "vote" else "legistar-rollcalls-json"
    result = create_engine().normalize(Source("legistar", "https://webapi.legistar.com/v1/olympia"),
                                       raw, input_format=fmt)
    assert result.status == "completed", result.public_dict()
    assert [row["original"] for row in result.data["records"]] == json.loads(raw)
    assert len(result.data["records"]) == 3
    assert all(row["normalized"]["value_name"] in {"Aye", "Present"} for row in result.data["records"])
    assert all(row["identity"]["external_id"] == str(row["original"][prefix + "Id"])
               for row in result.data["records"])
