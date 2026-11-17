"""A public HTTP 200 challenge page cannot establish an empty Simbli catalog."""

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.simbli import HOST, LIST


def test_http_200_challenge_is_failed_not_complete_empty_discovery():
    class Challenge:
        def __init__(self):
            self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, b'<html><iframe src="/_Incapsula_Resource?synthetic=1">'
                b'Request unsuccessful. Incapsula incident ID: synthetic</iframe></html>', "text/html")

    transport = Challenge()
    source = Source("simbli", HOST + LIST + "?S=36030321")
    result = create_engine(provider_transport=transport).discover(source, bounds=Bounds(max_pages=1))
    assert result.status == "failed", result.public_dict()
    assert result.errors and not result.data["records"]
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["checkpoint"] is None
    assert transport.calls == [source.url]
