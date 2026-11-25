import csv
from pathlib import Path

from desk.pulse_view import build_pulse

COLUMNS = ["review_id", "created_at", "score", "content", "user_name"]


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_pulse_keeps_the_latest_four_weeks_and_drops_short_reviews(tmp_path: Path):
    rows = [
        _row("old", "2026-10-13T10:00:00+08:00", "1", "This older week should fall outside the four week window entirely"),
        _row("t1", "2026-10-19T10:00:00+08:00", "5", "Great trading experience on the option chain this week"),
        _row("w1", "2026-10-26T10:00:00+08:00", "1", "Cannot withdraw my funds from the app at all"),
        _row("p1", "2026-11-02T10:00:00+08:00", "2", "The upi payment failed again and again today"),
        _row("t2", "2026-11-09T10:00:00+08:00", "3", "The option chain is very laggy during market orders"),
        _row("short", "2026-11-09T11:00:00+08:00", "5", "good"),
        _row("named", "2026-11-09T12:00:00+08:00", "1", "PAN ABCDE1234F is stuck and the app will not proceed further"),
    ]
    for row in rows:
        row["user_name"] = "Priya Shah"
    _write(tmp_path / "playstore.csv", rows)

    pulse = build_pulse(tmp_path)
    assert pulse["subtitle"] == "9 Nov – 15 Nov 2026"
    assert pulse["week_button"] == "9 Nov – 15 Nov 2026"
    assert pulse["corpus_range"] == "12 Oct – 8 Nov 2026"
    assert pulse["corpus_count"] == 4
    assert pulse["corpus_note"] == "4 earlier weeks"
    assert pulse["this_count"] == 2
    assert "Priya Shah" not in str(pulse)
    assert "[PAN]" in pulse["themes"][0]["quote"] or any("[PAN]" in theme["quote"] for theme in pulse["themes"])
    assert "Oct 13" not in pulse["subtitle"]
    labels = [theme["label"] for theme in pulse["themes"]]
    assert "Trading & orders" in labels
    trading = next(theme for theme in pulse["themes"] if theme["label"] == "Trading & orders")
    assert trading["action"] == "Check order placement"
    assert [option["label"] for option in pulse["week_options"]] == [
        "9 Nov – 15 Nov 2026",
        "2 Nov – 8 Nov 2026",
        "26 Oct – 1 Nov 2026",
        "19 Oct – 25 Oct 2026",
    ]
    earlier = build_pulse(tmp_path, "2026-11-02")
    assert earlier["week_button"] == "2 Nov – 8 Nov 2026"
    assert earlier["this_count"] == 1
    assert earlier["subtitle"] == "2 Nov – 8 Nov 2026"
    assert earlier["corpus_range"] == "12 Oct – 1 Nov 2026"
    assert earlier["corpus_note"] == "3 earlier weeks"
    week_19 = build_pulse(tmp_path, "2026-10-19")
    assert week_19["corpus_range"] == "12 Oct – 18 Oct 2026"
    assert week_19["corpus_note"] == "1 earlier week"
    week_26 = build_pulse(tmp_path, "2026-10-26")
    assert week_26["corpus_range"] == "12 Oct – 25 Oct 2026"
    assert week_26["corpus_note"] == "2 earlier weeks"
    assert build_pulse(tmp_path, "not-a-week")["week_button"] == "9 Nov – 15 Nov 2026"


def _row(review_id: str, created_at: str, score: str, content: str) -> dict:
    return {
        "review_id": review_id,
        "created_at": created_at,
        "score": score,
        "content": content,
        "user_name": "",
    }
