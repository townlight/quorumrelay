import importlib.util
from pathlib import Path

from civic_data_connectors import Engine, OperationContext, OperationResult


def connector():
    spec = importlib.util.spec_from_file_location("sample_connector",
                                                 Path(__file__).parents[1] / "examples/example_connector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExampleConnector()


def test_example_extension_discovery_and_identification_need_no_transport_changes():
    plugin = connector()
    owner = Engine(connectors=(plugin,))
    request = {"source": {"provider": plugin.provider, "url": "https://example.org", "namespace": "//example.org"}}
    assert owner.execute("discover", request).status == "completed"
    assert owner.execute("identify", {"provider": plugin.provider, "url": "https://example.org"}).status == "completed"
    context = OperationContext(allowed_operations=frozenset({"discover"}),
                               allowed_namespaces=frozenset({"//other.example"}))
    assert owner.execute("discover", request, context=context).errors[0].code == "permission_denied"


def test_extension_hooks_cannot_skip_shared_write_plan_authorization():
    plugin = connector()
    plugin.plan_write = lambda *args: OperationResult("completed", {"should_not_be_called": True})
    owner = Engine(connectors=(plugin,))
    result = owner.execute("plan_write", {"source": {"provider": plugin.provider, "url": "https://example.org"}})
    assert result.status == "unsupported"


def test_optional_discovery_hook_receives_the_original_request():
    plugin = connector()
    received = []

    def discover_request(source, request, bounds, context):
        received.append((source, request, bounds, context))
        return OperationResult("completed", {"requested": request["record_types"]})

    plugin.discover_request = discover_request
    owner = Engine(connectors=(plugin,))
    context = OperationContext()
    request = {"source": {"provider": plugin.provider, "url": "https://example.org",
                           "namespace": "//example.org"}, "record_types": ["document"]}
    result = owner.execute("discover", request, context=context)
    assert result.data == {"requested": ["document"]}
    assert received[0][1] is request and received[0][3] is context


def test_optional_discovery_hook_must_accept_the_declared_arguments():
    from civic_data_connectors.extensions import check_connector

    plugin = connector()
    plugin.discover_request = lambda: None
    assert check_connector(plugin) == [
        "discover_request must accept the 4 positional arguments declared by Connector"]
