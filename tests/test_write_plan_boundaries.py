"""Do not persist an approval plan after preflight cancellation or expiry."""
import pytest

from civic_data_connectors import writes, write_adapters
from test_client_write_response_bounds import wistia_update


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_last_provider_preflight_cannot_complete_cancelled_or_expired_plan(tmp_path, monkeypatch, boundary):
    engine, caller, vendor, source, change = wistia_update(tmp_path)
    original = vendor.send
    clock = [0.0]

    def ends_preflight(url, **options):
        response = original(url, **options)
        if boundary == "cancel":
            caller.cancellation.set()
        else:
            clock[0] = 2.0
        return response

    vendor.send = ends_preflight
    monkeypatch.setattr(writes, "monotonic", lambda: clock[0])
    monkeypatch.setattr(write_adapters, "monotonic", lambda: clock[0])
    result = engine.execute("plan_write", {"source": source, "changes": [change],
        "bounds": {"deadline_seconds": 1}}, context=caller)
    assert result.status == ("cancelled" if boundary == "cancel" else "failed"), result.public_dict()
    assert result.data is None
    assert not list(engine.storage.list("write_plans", scope=caller.scope))
    assert len(vendor.calls) == 1 and vendor.calls[0][0] == "GET"
    if boundary == "deadline":
        assert result.errors[0].code == "deadline_exceeded"
