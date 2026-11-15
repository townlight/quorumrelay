import base64
import io
from pathlib import Path

import pytest
from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response

RAW = (Path(__file__).parent / "fixtures/municode-publish/effingham.html").read_bytes()
URL = "https://meetings.municode.com/PublishPage/index?cid=EFFINGHAM&ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=1"
FORMAT = "municode-publishpage-html"


def test_saved_publish_page_normalizes():
    result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), RAW, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"]) == 25
class Transport:
    def __init__(self, raw=RAW):
        self.raw = raw
        self.calls = []

    def request(self, url, **kwargs):
        assert url == URL
        assert kwargs["allowed_origins"] == ("https://meetings.municode.com",)
        self.calls.append((url, kwargs))
        return Response(url, self.raw, "text/html", 200)


def discover(transport=None, **bounds):
    transport = transport or Transport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": {"provider": "municode-meetings", "url": URL, "input_format": FORMAT}, "bounds": bounds})
    return result, transport


def test_selected_page_and_native_fields():
    result, transport = discover()
    assert result.status == "partial" and not result.errors and len(result.data["records"]) == 25
    assert len(transport.calls) == 1
    row = result.data["records"][0]
    assert row["identity"]["namespace"] == "//meetings.municode.com/cid/EFFINGHAM"
    assert row["identity"]["external_id"] == "4a737d59a401417fbd7fd597e964fdba"
    assert row["identity"]["derivation"] == "public_document_selector"
    assert "unverified" in row["identity"]["stability"]
    assert row["original"]["agenda"]["attributes"]["class"].endswith("agenda")
    assert row["original"]["agenda"]["elements"][1]["attributes"]["alt"].startswith("PDF Agenda")
    normalized = row["normalized"]
    assert normalized["meeting_date"] == "2026-11-17" and normalized["source_time"] == "5:00 PM"
    assert normalized["time_zone_status"] == "unknown" and "body" not in normalized
    assert normalized["location"] == "Effingham County Administrative Complex Meeting Chambers"
    assert {d["kind"] for d in normalized["documents"]} == {"agenda", "packet"}
    assert {(d["source_column"], d["format"]) for d in normalized["documents"]} == {
        ("agenda", "pdf"), ("packet", "pdf"), ("adahtmlagenda", "html"), ("adahtmlpacket", "html")}
    controls = result.data["bundles"][0]["extensions"]["publishpage_controls"]
    assert controls["selected"] == "1" and controls["options"] == list("1234567")
    assert len(controls["declared_links"]) == 2
    assert base64.b64decode(result.data["captures"][0]["content_base64"]) == RAW


def test_page_two_selection_and_tenant_namespace_stability():
    raw = RAW.replace(b'<option value="1" selected>', b'<option value="1">').replace(
        b'<option value="2" >', b'<option value="2" selected>')
    source = Source("municode-meetings", URL[:-1] + "2", input_format=FORMAT)
    result = create_engine().normalize(source, raw, input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    assert result.data["records"][0]["identity"]["namespace"] == "//meetings.municode.com/cid/EFFINGHAM"
    assert result.data["extensions"]["publishpage_controls"]["selected"] == "2"


@pytest.mark.parametrize("url", [URL + "&cid=OTHER", URL.replace("EFFINGHAM", "OTHER"),
    URL.replace("p=1", "p=2"), URL.replace("9639c19d", "11111111"),
    URL.replace("/PublishPage/index", "/api/meeting"), URL.replace("https:", "http:")])
def test_invalid_or_mismatched_page_context_rejected(url):
    result = create_engine().normalize(Source("municode-meetings", url, input_format=FORMAT), RAW, input_format=FORMAT)
    assert result.status == "failed"


@pytest.mark.parametrize("raw", [
    RAW.replace(b'me=4a737d59a401417fbd7fd597e964fdba&ip=true', b'me=11111111111111111111111111111111&ip=true', 1),
    RAW.replace(b'cc=EFFINGHAM&me=4a737d59a401417fbd7fd597e964fdba', b'cc=OTHER&me=4a737d59a401417fbd7fd597e964fdba', 1),
    RAW.replace(b'option value="1" selected', b'option value="1"', 1),
    RAW.replace(b'ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=7', b'ppid=11111111-1d1f-4201-b8ff-163a28a35f08&p=7', 1),
])
def test_conflicting_row_and_control_identities_rejected(raw):
    result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), raw, input_format=FORMAT)
    assert result.status == "failed"


def test_missing_ada_selector_and_duplicate_rows_rejected():
    import re

    first_row = re.search(rb'<tr>\s*<td scope="row" class="div-table-col meeting med".*?</tr>' , RAW, re.S).group()
    without_ada = re.sub(rb'<a href="https://meetings\.municode\.com/adaHtmlDocument/index\?[^"]+"[^>]*>.*?</a>' ,
                         b"", first_row, flags=re.S)
    for changed in (RAW.replace(first_row, without_ada, 1), RAW.replace(first_row, first_row + first_row, 1)):
        result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), changed,
                                           input_format=FORMAT)
        assert result.status == "failed"


def test_discover_date_filter_and_local_checkpoint():
    first, _ = discover(date_from="2026-11-01", date_to="2026-11-30", max_records=1)
    assert first.status == "partial" and len(first.data["records"]) == 1 and first.coverage["checkpoint"]
    second, _ = discover(date_from="2026-11-01", date_to="2026-11-30", max_records=100,
                         checkpoint=first.coverage["checkpoint"])
    assert second.status == "partial" and second.coverage["checkpoint"] is None
    assert all(r["normalized"]["meeting_date"].startswith("2026-11") for r in first.data["records"] + second.data["records"])
    assert set(r["identity"]["external_id"] for r in first.data["records"]).isdisjoint(
        r["identity"]["external_id"] for r in second.data["records"])


def test_unknown_safe_document_locator_has_no_guessed_format():
    import re

    changed = re.sub(rb'href="https://meetings.municode.com/d/f\?[^"]+"',
                     b'href="https://files.example.org/document"', RAW, count=1)
    result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), changed,
                                       input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    doc = result.data["records"][0]["normalized"]["documents"][0]
    assert doc["url"] == "https://files.example.org/document" and "format" not in doc


def test_pdf_filename_identity_disagreement_rejected():
    changed = RAW.replace(b'MEET-Agenda-4a737d59a401417fbd7fd597e964fdba.pdf',
                          b'MEET-Agenda-11111111111111111111111111111111.pdf', 1)
    result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), changed,
                                       input_format=FORMAT)
    assert result.status == "failed"


@pytest.mark.parametrize("replacement", [b"?u=&u=https://", b"?u=https://"])
def test_pdf_duplicate_u_including_blank_rejected(replacement):
    if replacement == b"?u=https://":
        changed = RAW.replace(b".pdf&n=Agenda-", b".pdf&u=&n=Agenda-", 1)
    else:
        changed = RAW.replace(b"?u=https://", replacement, 1)
    result = create_engine().normalize(Source("municode-meetings", URL, input_format=FORMAT), changed,
                                       input_format=FORMAT)
    assert result.status == "failed"


def test_changed_capture_rejected_on_local_checkpoint():
    first, _ = discover(max_records=1)
    resumed, _ = discover(Transport(RAW + b" "), max_records=1, checkpoint=first.coverage["checkpoint"])
    assert resumed.status == "failed" and resumed.errors and not resumed.data["records"]


def test_discover_bounds_and_cancel():
    result, _ = discover(transfer_bytes=len(RAW) - 1)
    assert result.status == "failed" and not result.data["records"] and result.coverage["checkpoint"]
    result, _ = discover(parser_bytes=len(RAW) - 1)
    assert result.status == "failed" and not result.data["records"]
    context = OperationContext()
    context.cancellation.set()
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": {"provider": "municode-meetings", "url": URL, "input_format": FORMAT}}, context=context)
    assert result.status == "cancelled" and transport.calls == []


def test_persist_reopen_and_neutral_formats(tmp_path):
    from civic_data_connectors.interchange import read_bundle, write_bundle
    from civic_data_connectors.storage import SQLiteStorage

    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=Transport())
    found = engine.execute("discover", {"source": {"provider": "municode-meetings", "url": URL, "input_format": FORMAT}})
    bundle = found.data["bundles"][0]
    saved = engine.execute("import_bundle", {"bundle": bundle, "persist": True, "coverage": found.coverage})
    assert saved.status in {"partial", "completed"}, saved.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    stored = reopened.storage.list("bundles", scope=OperationContext().scope)
    assert len(stored) == 1 and stored[0].value["extensions"] == bundle["extensions"]
    for fmt in ("json", "jsonl", "zip"):
        output = io.BytesIO()
        write_bundle(bundle, output, format=fmt)
        restored = read_bundle(output.getvalue(), format=fmt)
        assert restored["extensions"] == bundle["extensions"] and restored["records"] == bundle["records"]
        assert base64.b64decode(restored["capture"]["content_base64"]) == RAW


def test_account_api_exemption_is_exact():
    from civic_data_connectors.providers.account_api import is_account_api

    assert not is_account_api(Source("municode-meetings", URL, input_format=FORMAT))
    assert is_account_api(Source("municode-meetings", "https://meetings.municode.com/api/meeting", input_format=FORMAT))
    assert is_account_api(Source("municode-meetings", "https://meetings.municode.com/"))
