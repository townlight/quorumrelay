"""Fresh-process 200 MiB artifact measurement; synthetic bytes, no network."""

import base64
import ctypes
import hashlib
import json
import random
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from civic_data_connectors import Engine  # noqa: E402
from civic_data_connectors.interchange import (  # noqa: E402
    cleanup_artifacts, open_artifact, register, stage_attachment,
)
from civic_data_connectors.models import OperationContext  # noqa: E402


class SyntheticPacket:
    def __init__(self, size):
        self.remaining, self.digest = size, hashlib.sha256()
        self.random = random.Random(20261111)

    def read(self, limit):
        size = min(limit, self.remaining)
        self.remaining -= size
        data = self.random.randbytes(size)
        self.digest.update(data)
        return data


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def peak_memory():
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    psapi, kernel = ctypes.WinDLL("psapi"), ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return counters.PeakWorkingSetSize


def main():
    started = time.perf_counter()
    size = 200 * 1024 * 1024
    engine = Engine()
    register(engine)
    context = OperationContext(authorization=frozenset({"export_attachments"}),
                               allowed_namespaces=frozenset({"city.example"}))
    packet = SyntheticPacket(size)
    stage_attachment(engine, "packet", packet, filename="packet.pdf",
                     citation_url="https://city.example/durable-packet", namespace="city.example",
                     context=context, max_bytes=size)
    captured = b'{"original":[null,false,0,"caf\xc3\xa9"]}'
    digest = hashlib.sha256(captured).hexdigest()
    bundle = {"schema_version": "2.0.0", "capture": {
        "sha256": digest, "byte_length": len(captured), "content_base64": base64.b64encode(captured).decode()},
        "records": [{"identity": {"provider": "legistar", "namespace": "city.example",
                                  "external_id": "1", "record_type": "meeting"},
                     "normalized": {"title": "Council packet"}, "capture_sha256": digest,
                     "source_url": "https://city.example", "original": {"unknown": [0, False, None]}}]}
    # Archive budget includes ZIP framing/metadata in addition to the exactly
    # 200 MiB packet; no parser cap or transfer cap is silently loosened.
    result = engine.execute("export", {"bundle": bundle, "stream": True, "attachment_ids": ["packet"],
                                      "bounds": {"transfer_bytes": 201 * 1024 * 1024}}, context=context)
    if result.status != "completed":
        raise AssertionError(result.public_dict())
    metadata, stream = open_artifact(engine, result.data["artifact_id"], context=context)
    with stream, zipfile.ZipFile(stream) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        attachment = manifest["attachments"][0]
        with archive.open(attachment["path"]) as member:
            actual = hashlib.file_digest(member, "sha256").hexdigest()
    if actual != packet.digest.hexdigest() or attachment["byte_length"] != size:
        raise AssertionError("The 200 MiB attachment changed.")
    elapsed = time.perf_counter() - started
    measured_peak = peak_memory()
    cleanup_artifacts(engine)
    print(json.dumps({"attachment_bytes": size, "archive_bytes": metadata["byte_length"],
                      "parser_bytes": 16 * 1024 * 1024, "transfer_bytes": 201 * 1024 * 1024,
                      "elapsed_seconds": round(elapsed, 3), "peak_working_set_bytes": measured_peak,
                      "sha256_match": True, "storage_mode": "optional-storeless-artifacts"}))


if __name__ == "__main__":
    main()
