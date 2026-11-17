"""Native public search reuses fresh controls and private scoped Novus cursors."""

from dataclasses import replace
from urllib.parse import parse_qs

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from test_novus_discovery import PAGES, SOURCE

PREFIX = "ctl00$ContentPlaceHolder1$SearchAgendasMeetings$"


class SearchTransport:
    def __init__(self):
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["allow_redirects"] is False
        if kwargs["method"] == "POST":
            form = parse_qs(kwargs["body"].decode(), keep_blank_values=True)
            assert form[PREFIX + "ctl02"] == ["Board"]
            assert form[PREFIX + "imageButtonSearch.x"] == ["10"]
            assert form["__EVENTTARGET"] == [""]
            assert "synthetic-session" in kwargs["headers"]["Cookie"]
        return Response(url, PAGES[0], "text/html", set_cookie_headers=(
            "session=synthetic-session; Path=/; Secure; HttpOnly",))


def request(**kwargs):
    return {"native": True, "source": SOURCE.public_dict(), "query": {"terms": ["Board"], "limit": 1},
            "bounds": {"max_pages": 1, **kwargs}}


def test_fresh_search_exact_metadata_and_query_scoped_midpage_retry():
    transport = SearchTransport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request())
    assert first.status == "partial", first.public_dict()
    assert len(first.data["hits"]) == 1
    assert len(transport.calls) == 2
    token = first.coverage["checkpoint"]
    assert token and "synthetic-session" not in token
    continued = engine.execute("search", request(checkpoint=token))
    retry = engine.execute("search", request(checkpoint=token))
    assert [r["identity"] for r in continued.data["records"]] == [r["identity"] for r in retry.data["records"]]
    assert first.data["records"] != continued.data["records"]
    changed = request(checkpoint=token)
    changed["query"]["terms"] = ["Other"]
    assert engine.execute("search", changed).status == "failed"
    assert engine.execute("search", request(checkpoint=token),
                          context=OperationContext(client_id="another")).status == "failed"


def test_revoked_search_and_changed_public_form_fail_closed():
    engine = create_engine(provider_transport=SearchTransport())
    assert engine.execute("search", request(), context=OperationContext(allowed_operations=())).status == "failed"

    class Changed(SearchTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            return replace(response, content=response.content.replace(b'imageButtonSearch', b'unknownControl'))

    assert create_engine(provider_transport=Changed()).execute("search", request()).status == "failed"


@pytest.mark.parametrize("bounds", [{"transfer_bytes": 100}, {"parser_bytes": 100}])
def test_search_request_response_bounds(bounds):
    result = create_engine(provider_transport=SearchTransport()).execute("search", request(**bounds))
    assert result.status == "failed"


def test_provider_date_validation_failure_does_not_become_empty_success():
    class InvalidDates(SearchTransport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if kwargs["method"] == "POST":
                return replace(response, content=response.content + b"TO date must be after FROM date")
            return response

    result = create_engine(provider_transport=InvalidDates()).execute("search", request())
    assert result.status == "failed"
    assert result.errors
