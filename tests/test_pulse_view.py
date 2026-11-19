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
    assert pulse["corpus_range"] == "19 Oct – 8 Nov 2026"
    assert pulse["corpus_count"] == 3
    assert pulse["this_count"] == 2
    assert "Priya Shah" not in str(pulse)
    assert "[PAN]" in pulse["themes"][0]["quote"] or any("[PAN]" in theme["quote"] for theme in pulse["themes"])
    assert "Oct 13" not in pulse["subtitle"]
    labels = [theme["label"] for theme in pulse["themes"]]
    assert "Trading & orders" in labels
    trading = next(theme for theme in pulse["themes"] if theme["label"] == "Trading & orders")
    assert trading["action"] == "Check order placement"


def _row(review_id: str, created_at: str, score: str, content: str) -> dict:
    return {
        "review_id": review_id,
        "created_at": created_at,
        "score": score,
        "content": content,
        "user_name": "",
    }
