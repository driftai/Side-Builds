from app.parser import parse_sheet, summarize_sheet


def test_mixed_sheet():
    events = parse_sheet("ab [Cd] -- {ef}|g")
    kinds = [event.kind for event in events]
    assert "chord" in kinds
    assert kinds.count("pause") >= 2
    assert any(event.kind == "fast" for event in events)


def test_summary():
    summary = summarize_sheet("abc [de] --")
    assert summary["notes"] == 3
    assert summary["chords"] == 1
    assert summary["pauses"] >= 1
