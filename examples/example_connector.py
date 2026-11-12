"""Synthetic connector showing transport-independent extension registration."""

from civic_data_connectors import Engine, OperationResult
from civic_data_connectors.extensions import check_connector


class ExampleConnector:
    provider = "example-fixture"

    def capabilities(self):
        return {"discovery": "synthetic fixture", "write": "requires shared WriteAdapter registration"}

    def identify(self, url):
        return OperationResult("completed", {"provider": self.provider, "url": url})

    def discover(self, source, bounds, context):
        return OperationResult("completed", {"source": source.public_dict(), "records": []},
                               coverage={"sources": [source.public_dict()], "scope": "synthetic fixture"})

    def fetch(self, source, request, bounds, context):
        return OperationResult.unsupported("fetch")

    def parse(self, source, content, input_format, bounds, context):
        return OperationResult.unsupported("parse")

    def native_search(self, source, query, bounds, context):
        return OperationResult.unsupported("native_search")

    def export(self, source, request, context):
        return OperationResult.unsupported("provider_export")

    def plan_write(self, source, request, context):
        return OperationResult.unsupported("plan_write", reason="Register a shared WriteAdapter for supported writes.")

    def commit_write(self, source, request, context):
        return OperationResult.unsupported("commit_write", reason="Writes cannot bypass shared plan/receipt state.")


def main():
    connector = ExampleConnector()
    assert not check_connector(connector)
    engine = Engine(connectors=(connector,))
    result = engine.execute("discover", {"source": {"provider": connector.provider, "url": "https://example.org"}})
    assert result.status == "completed"
    print(result.public_dict())


if __name__ == "__main__":
    main()
