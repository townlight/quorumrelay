import json
from pathlib import Path

import pytest

from civic_data_connectors.models import Source
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.towncloud_public import listing_rows
from quorumrelay import create_engine

FIXTURE = Path(__file__).parent / "fixtures" / "towncloud-published-woodford.json"
PUBLISHED = "https://towncloud.io/go/woodford-vt/published_agendas.json"


def source(url=PUBLISHED):
    return Source(provider="towncloud", url=url)


def test_observed_published_rows_and_unknown_fields():
    content = FIXTURE.read_bytes()
    raw = json.loads(content)
    rows = listing_rows(source(), content)
    assert len(rows) == 115
    row, original, kind = rows[0]
    assert kind == "meeting" and row["external_id"] == "452"
    assert row["meeting_date"] == "2026-11-09" and row["source_start"] == "2026-11-09T17:15:00"
    assert row["time_zone_status"] == "unknown" and "body" not in row
    assert [d["kind"] for d in row["documents"]] == ["agenda", "minutes", "packet"]
    assert original == raw[0] and original["contactEmail"] == raw[0]["contactEmail"]


def test_ssr_response_uses_published_tenant_and_preserves_row():
    raw = json.loads(FIXTURE.read_bytes())[:1]
    raw[0]["future_field"] = {"unknown": [1, 2]}
    wrapper = json.dumps({"status": 200, "body": json.dumps(raw)})
    html = f'<script type="application/json" sveltekit:data-url="{PUBLISHED}">{wrapper}</script>'
    mapped = listing_rows(source("https://woodfordvt.org/agendas"), html.encode())
    assert mapped[0][1]["future_field"] == {"unknown": [1, 2]}
    assert listing_rows(source(), b"[]") == []


def test_rejects_other_tenant_or_unsafe_links_and_failed_embed():
    row = json.loads(FIXTURE.read_bytes())[0]
    row["agendaRead"] = row["agendaRead"].replace("woodford-vt", "other")
    with pytest.raises(ValueError, match="No dated"):
        listing_rows(source(), json.dumps([row]).encode())
    row["agendaRead"] = row["agendaRead"].replace("other", "woodford-vt")
    row["agendaDownload"] = "https://towncloud.io/go/other/agendas/452/PDF/get_agenda_document_link"
    row["minutesDownload"] = "http://towncloud.io/go/woodford-vt/agendas/452/minutes/get_agenda_document_link"
    row["agendaPdfPacketDownload"] = "https://127.0.0.1/go/woodford-vt/agendas/452/file"
    assert listing_rows(source(), json.dumps([row]).encode())[0][0]["documents"] == []
    wrapper = json.dumps({"status": 403, "body": "[]"})
    html = f'<script type="application/json" sveltekit:data-url="{PUBLISHED}">{wrapper}</script>'
    with pytest.raises(ValueError, match="not successful"):
        listing_rows(source("https://woodfordvt.org/agendas"), html.encode())


def test_refuses_unbound_or_multiple_embedded_sources():
    with pytest.raises(ValueError, match="Expected one"):
        listing_rows(source("https://woodfordvt.org/agendas"), b"<html></html>")
    wrapper = json.dumps({"status": 200, "body": "[]"})
    script = f'<script type="application/json" sveltekit:data-url="{PUBLISHED}">{wrapper}</script>'
    with pytest.raises(ValueError, match="Expected one"):
        listing_rows(source("https://woodfordvt.org/agendas"), (script + script).encode())


def test_real_engine_registration_handles_canonical_listing_and_ssr_source():
    engine=create_engine()
    canonical=engine.execute("discover",{"source":source().public_dict()},content=FIXTURE.read_bytes())
    assert canonical.status=="partial" and len(canonical.data["records"])==115
    assert canonical.data["records"][0]["identity"]["namespace"]=="//towncloud.io/go/woodford-vt"
    wrapper={"status":200,"body":FIXTURE.read_text(encoding="utf-8")}
    html=('<script type="application/json" sveltekit:data-url="'+PUBLISHED+'">'+json.dumps(wrapper)+'</script>').encode()
    ssr=engine.execute("discover",{"source":source("https://woodfordvt.org/agendas").public_dict()},content=html)
    assert len(ssr.data["records"])==115
    assert ssr.data["records"][0]["normalized"]==canonical.data["records"][0]["normalized"]


@pytest.mark.parametrize("url", [PUBLISHED, "https://woodfordvt.org/agendas"])
def test_configured_listing_replays_for_attachment_retrieval(url):
    raw = FIXTURE.read_bytes()
    if url != PUBLISHED:
        wrapper = json.dumps({"status": 200, "body": raw.decode()})
        raw = f'<script type="application/json" sveltekit:data-url="{PUBLISHED}">{wrapper}</script>'.encode()
    pdf = b"%PDF-1.7\nsynthetic TownCloud minutes"
    document_url = json.loads(FIXTURE.read_bytes())[0]["minutesDownload"]

    class Transport:
        def request(self, requested_url, **kwargs):
            assert requested_url == document_url
            assert "https://towncloud.io" in kwargs["allowed_origins"]
            return Response(requested_url, pdf, "application/pdf")

    engine = create_engine(provider_transport=Transport())
    listing = Source("towncloud", url, options={"download_origins": ["https://towncloud.io"]})
    discovered = engine.execute("discover", {"source": listing.public_dict()}, content=raw)
    record = discovered.data["records"][0]
    assert record["identity"]["external_id"] == "452"
    fetched = engine.fetch_attachment(listing, record, index=1, capture=raw)
    assert fetched.status == "completed", fetched.public_dict()
    assert fetched.data["attachment"]["citation_url"] == document_url
    assert fetched.data["attachment"]["byte_length"] == len(pdf)
