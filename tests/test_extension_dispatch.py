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
