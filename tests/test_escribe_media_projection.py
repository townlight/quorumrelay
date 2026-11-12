import json

from quorumrelay import Source, create_engine

SOURCE = Source("escribe", "https://pub-oakville.escribemeetings.com/meetingscalendarview.aspx?Expanded=Council")


def test_supplied_calendar_video_maps_player_citation_and_raw_unknowns_without_changing_baseline():
    raw = {"ID": "captured-meeting", "MeetingName": "Council", "StartDate": "2026/11/10 09:30:00",
        "HasVideo": True, "MeetingDocumentLink": [
            {"Type": "Video", "Title": "Video", "Url": "./Players/ISIStandAlonePlayer.aspx?Id=captured-meeting",
             "HasVideo": True, "unknown": {"value": "retained"}},
            {"Type": "Agenda", "Title": "Agenda", "Url": "/FileStream.ashx?DocumentId=1"}]}
    content = json.dumps({"d": [raw]}).encode()
    engine = create_engine()
    baseline = engine.normalize(SOURCE, content, input_format="escribe-calendar-json")
    assert baseline.status == "completed", baseline.public_dict()
    assert "recordings" not in baseline.data["records"][0]["normalized"]
    result = engine.execute("discover", {"source": SOURCE.public_dict()}, content=content)
    row = result.data["records"][0]
    recording = row["normalized"]["recordings"][0]
    assert recording["url"] == "https://pub-oakville.escribemeetings.com/Players/ISIStandAlonePlayer.aspx?Id=captured-meeting"
    assert recording["source_fields"] == raw["MeetingDocumentLink"][0]
    assert "video_url" not in recording
    assert row["normalized"]["source_status"] == {"HasVideo": True}
    assert any(r["relation"] == "recording" and r["value"] == recording for r in row["relationships"])
    assert row["original"] == raw
    assert len(row["normalized"]["documents"]) == 2  # Preserve legacy citations.
