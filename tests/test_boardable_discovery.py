import base64
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from civic_data_connectors.models import Bounds, OperationContext, Source
from civic_data_connectors.providers.boardable import API_ORIGIN, API_PATH, discover_public
from civic_data_connectors.providers.contracts import Response


FIXTURES = Path(__file__).parent / "fixtures" / "boardable-discovery"
TENANT = "ventura-county-community-college-district"
ROOT_URL = f"https://site.boardable.com/{TENANT}/meetings"
LANDING = (FIXTURES / "tenant-landing.html").read_bytes()
PAGE_1 = (FIXTURES / "page-1.json").read_bytes()
PAGE_2 = (FIXTURES / "page-2.json").read_bytes()
EMPTY = (FIXTURES / "empty-page.synthetic.json").read_bytes()


def _empty_page(mode=False, page=1):
    payload = json.loads(EMPTY)
    payload["meta"]["current_page"] = page
    payload["links"]["next"] = None
    return json.dumps(payload, separators=(",", ":")).encode()


class FakeEngine:
    storage = None


class FakeTransport:
    def __init__(self, pages=None, *, callback=None, landing=LANDING):
        self.pages = pages or {}
        self.callback = callback
        self.landing = landing
        self.requests = []

    def request(self, url, *, method="GET", body=None, headers=None, byte_limit,
                deadline_seconds, allowed_origins, destination=None, allow_redirects=True):
        self.requests.append({"url": url, "method": method, "headers": dict(headers or {}),
                              "byte_limit": byte_limit, "allowed_origins": allowed_origins,
                              "allow_redirects": allow_redirects})
        if urlsplit(url).hostname == "site.boardable.com":
            response = Response(url, self.landing, "text/html", 200)
        else:
            parsed = urlsplit(url)
            assert parsed.hostname == "app.boardable.com"
            assert parsed.path == API_PATH
            query = parse_qs(parsed.query, keep_blank_values=True)
            mode = query["upcoming"][0] == "true"
            page = int(query["page"][0])
            content = self.pages.get((mode, page))
            if content is None:
                content = _empty_page(mode, page)
            response = Response(url, content, "application/json", 200)
        if self.callback:
            self.callback(url, response)
        return response


def _source(url=ROOT_URL, *, body=None, options=None):
    return Source("boardable", url, body=body, options=options or {})


def _discover(transport, *, source=None, bounds=None, context=None, record_types=None):
    source = source or _source()
    return discover_public(FakeEngine(), source, None, bounds or Bounds(), context or OperationContext(),
                           transport, record_types=record_types)


def _ids(result):
    return [record["identity"]["external_id"] for record in result.data["records"]]


def test_observed_page_one_and_two_keep_numeric_ids_raw_payloads_and_citations():
    transport = FakeTransport({(True, 1): PAGE_1, (True, 2): PAGE_2, (False, 1): EMPTY})
    result = _discover(transport, bounds=Bounds(max_pages=2, max_records=100))

    assert result.status == "partial"
    assert len(result.data["records"]) == 20
    assert result.data["records"][0]["identity"]["external_id"] == "472861"
    assert result.data["records"][0]["identity"]["derivation"] == "provider_identifier"
    assert result.data["records"][0]["original"]["slug"] == "938b9e-atac-november-12-2026"
    assert result.data["records"][0]["citation_urls"] == [
        ROOT_URL, f"https://site.boardable.com/{TENANT}/meetings/938b9e-atac-november-12-2026"]
    assert len(result.data["captures"]) == 2
    assert result.data["captures"][0]["sha256"] == "e429416b040df3b8e0818b1a509afdbe783c0e724abbaf1bd6d89a636c086aaa"
    assert result.data["captures"][1]["sha256"] == "35eb41d4b3dbf27edf658401d3de45e1cab13744217091f38b1ca1d96346528d"
    ids_page_1 = {record["identity"]["external_id"] for record in result.data["bundles"][0]["records"]}
    ids_page_2 = {record["identity"]["external_id"] for record in result.data["bundles"][1]["records"]}
    assert len(ids_page_1) == len(ids_page_2) == 10
    assert ids_page_1.isdisjoint(ids_page_2)
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["documents_and_agenda_items"] == "not_supplied_by_public_meeting_listing"
    api_calls = [item for item in transport.requests if urlsplit(item["url"]).hostname == "app.boardable.com"]
    assert [item["headers"]["SiteId"] for item in api_calls] == ["3", "3"]
    assert all(item["allowed_origins"] == (API_ORIGIN,) and not item["allow_redirects"] for item in api_calls)


def test_midpage_checkpoint_replays_same_hash_and_resumes_without_skipping_records():
    first = FakeTransport({(True, 1): PAGE_1})
    one = _discover(first, bounds=Bounds(max_pages=1, max_records=1))
    assert len(one.data["records"]) == 1
    token = one.coverage["checkpoint"]
    assert token
    checkpoint = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    assert [(task["mode"], task["page"], task["offset"]) for task in checkpoint["queue"]] == [
        (True, 1, 1), (False, 1, 0)]

    resumed = FakeTransport({(True, 1): PAGE_1, (True, 2): PAGE_2, (False, 1): EMPTY})
    two = discover_public(FakeEngine(), _source(), None, Bounds(max_pages=2, max_records=100,
        checkpoint=token), OperationContext(), resumed)
    combined = _ids(one) + _ids(two)
    assert len(combined) == 20
    assert len(set(combined)) == 20
    assert len(two.data["captures"]) == 2
    api_calls = [item for item in resumed.requests if urlsplit(item["url"]).hostname == "app.boardable.com"]
    assert len(api_calls) == 2
    assert [parse_qs(urlsplit(item["url"]).query)["page"][0] for item in api_calls] == ["1", "2"]
    state = json.loads(base64.urlsafe_b64decode(two.coverage["checkpoint"].encode("ascii")))
    assert [(task["mode"], task["page"]) for task in state["queue"]] == [(True, 3), (False, 1)]


def test_midpage_checkpoint_rejects_changed_provider_page_bytes():
    first = _discover(FakeTransport({(True, 1): PAGE_1}),
                      bounds=Bounds(max_pages=1, max_records=1))
    changed = json.loads(PAGE_1)
    changed["data"][0]["title"] += " changed"
    transport = FakeTransport({(True, 1): json.dumps(changed, separators=(",", ":")).encode()})
    resumed = discover_public(FakeEngine(), _source(), None,
        Bounds(max_pages=1, max_records=10, checkpoint=first.coverage["checkpoint"]),
        OperationContext(), transport)
    assert resumed.status == "failed"
    assert resumed.errors[0].code == "provider_page_failed"
    assert resumed.data["captures"] == []


def test_observed_empty_listing_exhausts_both_modes_without_claiming_catalog_complete():
    transport = FakeTransport({(True, 1): EMPTY, (False, 1): EMPTY})
    result = _discover(transport, bounds=Bounds(max_pages=2, max_records=10))
    assert result.status == "partial"
    assert result.data["records"] == []
    assert result.coverage["listing_exhausted"] is True
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["checkpoint"] is None
    assert len([item for item in transport.requests if urlsplit(item["url"]).hostname == "app.boardable.com"]) == 2


@pytest.mark.parametrize("next_url", [
    "https://attacker.invalid/api/public-sites/meetings?count=10&search=&group=&status=&sort=asc&upcoming=true&page=2",
    "https://app.boardable.com/api/public-sites/meetings?count=10&search=&group=&status=&sort=asc&upcoming=false&page=2",
    "https://app.boardable.com/api/public-sites/meetings?count=10&search=&group=&status=&sort=asc&upcoming=true&page=3",
])
def test_forged_next_links_are_rejected_before_following(next_url):
    payload = json.loads(PAGE_1)
    payload["links"]["next"] = next_url
    transport = FakeTransport({(True, 1): json.dumps(payload).encode()})
    result = _discover(transport, bounds=Bounds(max_pages=3))
    assert result.status == "failed"
    assert not result.data["captures"]
    requested_hosts = [urlsplit(item["url"]).hostname for item in transport.requests]
    assert requested_hosts == ["site.boardable.com", "app.boardable.com"]


@pytest.mark.parametrize("binding_change", ["body", "date", "principal", "record_type"])
def test_checkpoint_is_bound_to_source_filters_and_caller_scope(binding_change):
    initial = _discover(FakeTransport({(True, 1): PAGE_1}),
                        bounds=Bounds(max_pages=1, max_records=1))
    kwargs = {"source": _source(), "bounds": Bounds(max_pages=2, max_records=10,
                                                       checkpoint=initial.coverage["checkpoint"]),
              "context": OperationContext(), "record_types": None}
    if binding_change == "body":
        kwargs["source"] = _source(body="different")
    elif binding_change == "date":
        kwargs["bounds"] = Bounds(date_from="2026-11-12", max_pages=2, max_records=10,
                                   checkpoint=initial.coverage["checkpoint"])
    elif binding_change == "principal":
        kwargs["context"] = OperationContext(principal="other")
    else:
        kwargs["record_types"] = ["document"]
    transport = FakeTransport({(True, 1): PAGE_1})
    with pytest.raises(ValueError, match="checkpoint belongs"):
        _discover(transport, **kwargs)
    assert transport.requests == []


def test_caller_cannot_supply_or_spoof_public_site_id():
    transport = FakeTransport({(True, 1): PAGE_1})
    with pytest.raises(ValueError, match="unrecognized provider configuration"):
        _discover(transport, source=_source(options={"site_id": 999}))
    assert transport.requests == []


def test_public_site_id_must_match_the_configured_organization_slug():
    wrong_tenant = LANDING.replace(TENANT.encode(), b"different-public-organization")
    transport = FakeTransport({(True, 1): PAGE_1}, landing=wrong_tenant)
    result = _discover(transport)
    assert result.status == "failed"
    assert result.data["captures"] == []
    assert [urlsplit(item["url"]).hostname for item in transport.requests] == ["site.boardable.com"]


def test_page_response_byte_limit_is_enforced_even_if_transport_ignores_it():
    transport = FakeTransport({(True, 1): PAGE_1})
    result = _discover(transport, bounds=Bounds(parser_bytes=512, max_pages=1))
    assert result.status == "failed"
    assert result.errors[0].code == "provider_response_outside_contract"
    assert len(transport.requests) == 2


def test_cancellation_after_api_response_preserves_current_page_checkpoint():
    context = OperationContext()

    def cancel_after_api(url, response):
        if urlsplit(url).hostname == "app.boardable.com":
            context.cancellation.set()

    transport = FakeTransport({(True, 1): PAGE_1}, callback=cancel_after_api)
    result = _discover(transport, bounds=Bounds(max_pages=1), context=context)
    assert result.status == "cancelled"
    assert not result.data["captures"]
    assert result.coverage["checkpoint"]


def test_date_body_and_type_filters_keep_unknown_text_and_unknown_raw_fields():
    payload = json.loads(PAGE_1)
    rows = deepcopy(payload["data"][:4])
    rows[0]["description"] = ""
    rows[1]["description"] = "needle"
    rows[1]["meeting_extension"] = {"vendor_value": "preserve-me"}
    rows[2]["description"] = "other"
    rows[3]["description"] = "needle"
    for row in rows[:3]:
        row["start"]["date"] = "2026-11-12 16:00:00"
    rows[3]["start"]["date"] = "2026-11-13 16:00:00"
    payload["data"] = rows
    payload["meta"].update({"current_page": 1, "per_page": 10, "total": 4, "last_page": 1})
    payload["links"]["next"] = None
    content = json.dumps(payload, separators=(",", ":")).encode()
    transport = FakeTransport({(True, 1): content, (False, 1): EMPTY})
    result = _discover(transport, source=_source(body="needle"),
        bounds=Bounds(date_from="2026-11-12", date_to="2026-11-12", max_pages=2))
    assert [record["identity"]["external_id"] for record in result.data["records"]] == [
        str(rows[0]["id"]), str(rows[1]["id"]), str(rows[2]["id"])]
    assert result.coverage["unknown_body_records"] == [str(row["id"]) for row in rows[:3]]
    assert result.coverage["body_filter_status"] == "unknown_listing_description_is_not_mapped_as_body"
    assert result.coverage["filtered_records"] == 1
    assert result.data["records"][1]["original"]["meeting_extension"] == {"vendor_value": "preserve-me"}
    assert result.data["records"][1]["normalized"]["description"] == "needle"
    assert "body" not in result.data["records"][1]["normalized"]
    assert result.data["records"][1]["normalized"]["documents_availability"] == "not_supplied_by_meeting_listing"

    type_transport = FakeTransport({(True, 1): content, (False, 1): EMPTY})
    typed = _discover(type_transport, bounds=Bounds(max_pages=2), record_types=["document"])
    assert typed.data["records"] == []
    assert typed.coverage["unobserved_record_types"] == ["document"]
    assert typed.coverage["catalog_complete"] is False


def test_saved_additive_listing_parser_is_available_without_network():
    from quorumrelay import create_engine
    engine = create_engine()
    source = {"provider": "boardable", "url": ROOT_URL,
              "input_format": "boardable-public-meetings-json"}
    result = engine.execute("normalize", {"source": source}, content=PAGE_1)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"]) == 10
    assert base64.b64decode(result.data["capture"]["content_base64"]) == PAGE_1
    assert result.data["capture"]["original_values"] == json.loads(PAGE_1)
    assert result.data["records"][0]["original"] == json.loads(PAGE_1)["data"][0]
    assert result.data["records"][0]["identity"]["record_type"] == "meeting"
