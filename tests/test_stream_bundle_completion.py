"""The public stream SDK cannot confirm an interrupted final caller write."""

import io

import pytest

from quorumrelay import Bounds, OperationContext
from civic_data_connectors import interchange
from test_storage_search_imports import sample


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
def test_final_caller_write_does_not_return_a_success_manifest(monkeypatch, format, boundary):
    bundle, context, clock = sample(), OperationContext(), [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    baseline = io.BytesIO()
    manifest = interchange.write_bundle(bundle, baseline, format=format)
    expected_size = manifest["output"]["byte_length"]

    class InterruptedFinalWrite(io.BytesIO):
        def write(self, data):
            count = super().write(data)
            if self.tell() == expected_size:
                if boundary == "cancel":
                    context.cancellation.set()
                else:
                    clock[0] = 2.0
            return count

    output = InterruptedFinalWrite()
    error = InterruptedError if boundary == "cancel" else ValueError
    with pytest.raises(error):
        interchange.write_bundle(bundle, output, format=format, context=context,
                                 bounds=Bounds(deadline_seconds=1))
    # The caller owns and discards partial output on error, even if all bytes arrived.
    assert len(output.getvalue()) == expected_size
