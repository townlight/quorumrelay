"""Private read credentials never become durable public source configuration."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response


SECRET = "synthetic-private-legistar-read-token"
SOURCE = {"provider": "legistar", "url": "https://webapi.legistar.com/v1/city"}
EVENT = {"EventId": 7, "EventBodyName": "Council", "EventDate": "2026-11-11"}


@pytest.mark.parametrize("operation", ["discover", "detail"])
@pytest.mark.parametrize("failure", [None, "http", "exception"])
def test_private_legistar_token_works_without_public_source_or_error_leak(operation, failure):
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append((url, kwargs))
            assert parse_qs(urlsplit(url).query)["token"] == [SECRET]
            assert kwargs["allowed_origins"] == ("https://webapi.legistar.com",)
            if failure == "exception":
                raise RuntimeError("Private transport failed at " + url)
            body = [EVENT] if operation == "discover" else EVENT
            return Response(url, json.dumps(body).encode(), "application/json",
                            403 if failure == "http" else 200)

    engine = create_engine(provider_transport=Transport())
    context = OperationContext(credentials={"legistar_token": SECRET})
    request = {"source": SOURCE}
    if operation == "discover":
        request["bounds"] = {"date_from": "2026-11-01", "date_to": "2026-11-11", "max_records": 1}
        result = engine.execute("discover", request, context=context)
    else:
        result = engine.execute("fetch", {**request, "external_id": "7"}, context=context)
    assert calls
    assert result.status == ("failed" if failure else "completed")
    serialized = json.dumps(result.public_dict())
    assert SECRET not in serialized
    assert base64.b64encode(SECRET.encode()).decode() not in serialized
    assert SOURCE["url"] in serialized
    assert "?token=" not in serialized
    if result.coverage.get("checkpoint"):
        assert SECRET not in base64.urlsafe_b64decode(result.coverage["checkpoint"]).decode()


@pytest.mark.parametrize("key", [
    "token", "API_KEY", "access_token", "Password", "Authorization", "Cookie",
    "client_secret", "Credentials",
])
def test_identify_rejects_credential_query_key_without_echo(key):
    result = create_engine().execute("identify", {"url": SOURCE["url"] + f"?{key}={SECRET}"})
    assert result.status == "failed"
    assert SECRET not in json.dumps(result.public_dict())


def test_odata_continuation_key_is_not_a_credential_name():
    result = create_engine().execute("identify", {"url":
        "https://city.api.civicclerk.com/v1/Events?$skiptoken=public-continuation"})
    assert result.status == "completed"
    assert result.data["provider"] == "civicplus-select"


@pytest.mark.parametrize("key", [
    "token", "API_KEY", "access_token", "Password", "Authorization", "Cookie",
    "client_secret", "Credentials",
])
def test_source_rejects_query_and_nested_option_credentials_without_echo(key):
    for kwargs in (
        {"url": SOURCE["url"] + f"?{key}={SECRET}"},
        {"url": SOURCE["url"], "options": {"nested": [{"more": {key: SECRET}}]}},
    ):
        with pytest.raises(ValueError) as error:
            Source("legistar", **kwargs)
        assert SECRET not in str(error.value)
