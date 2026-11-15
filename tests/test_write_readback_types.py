"""Coordinator checks for typed native JSON write readbacks."""
import pytest
from urllib.parse import parse_qs

from civic_data_connectors import Engine
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.writes import register
from test_write_providers import DocumentedNetwork, make_engine, response, run


class AlteredNetwork(DocumentedNetwork):
    def __init__(self, value):
        super().__init__("legistar")
        self.value = value

    def legistar(self, parsed, method, fields):
        if method == "GET" and "$filter" in parse_qs(parsed.query) and self.value is not None:
            return response([{**row, "EventAgendaStatusId": self.value} for row in self.rows.values()])
        if method == "GET" and parsed.path in self.rows:
            row = dict(self.rows[parsed.path])
            if self.value is not None:
                row["EventAgendaStatusId"] = self.value
            return response(row)
        return super().legistar(parsed, method, fields)


@pytest.mark.parametrize("value", [True, 1.0])
def test_event_integer_readback_type_mismatch_reconciles_without_replay(tmp_path, value):
    network = AlteredNetwork(value)
    engine, context, _, source = make_engine(tmp_path, "legistar", ["event:create"], network)
    change = {"key": "event", "entity": "event", "operation": "create", "fields": {
        "EventDate": "2026-11-15", "EventAgendaStatusId": 1}}
    result, approval = run(engine, context, source, change)
    assert result.data["items"][0]["state"] == "uncertain"
    reopened = Engine(storage=SQLiteStorage(tmp_path / "provider.sqlite"))
    register(reopened, default_adapters(network))
    assert reopened.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    network.value = None
    assert reopened.execute("commit_write", approval, context=context).data["items"][0]["state"] == "succeeded"
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_documented_number_accepts_equal_integer_and_float(tmp_path):
    class NumericNetwork(DocumentedNetwork):
        def legistar(self, parsed, method, fields):
            if method == "GET" and parsed.path in self.rows:
                return response({**self.rows[parsed.path], "MatterCost": 1.0})
            return super().legistar(parsed, method, fields)

    network = NumericNetwork("legistar")
    engine, context, _, source = make_engine(tmp_path, "legistar", ["matter:create"], network)
    change = {"key": "matter", "entity": "matter", "operation": "create", "meeting_id": "9", "fields": {
        "MatterTypeId": 1, "MatterStatusId": 2, "MatterBodyId": 3, "MatterCost": 1}}
    result, _ = run(engine, context, source, change)
    assert result.data["items"][0]["state"] == "succeeded"
