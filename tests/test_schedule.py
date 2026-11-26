from datetime import datetime, timedelta, timezone

from desk.schedule import containing_week, csv_name, monday_sunday

CLOCK = timezone(timedelta(hours=8))


def test_a_question_counts_in_the_monday_sunday_week_that_contains_it():
    thursday = datetime(2026, 11, 26, 16, 0, tzinfo=CLOCK)
    start, end = containing_week(thursday)
    assert start == datetime(2026, 11, 23, 0, 0, 0, tzinfo=CLOCK)
    assert end == datetime(2026, 11, 29, 23, 59, 59, tzinfo=CLOCK)


def test_an_empty_corpus_loads_the_fixture_pages():
    import sqlite3

    from desk.db import init_db
    from desk.schedule import _ensure_corpus

    connection = sqlite3.connect(":memory:")
    init_db(connection)
    _ensure_corpus(connection)
    count = connection.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
    assert count == 3


def test_sunday_night_and_monday_morning_use_the_same_week():
    sunday_night = datetime(2026, 11, 15, 22, 30, tzinfo=CLOCK)
    monday_morning = datetime(2026, 11, 16, 9, 0, tzinfo=CLOCK)
    start, end = monday_sunday(sunday_night)
    assert start == datetime(2026, 11, 9, 0, 0, 0, tzinfo=CLOCK)
    assert end == datetime(2026, 11, 15, 23, 59, 59, tzinfo=CLOCK)
    assert csv_name(start, end) == "Playstore_2026-11-09_2026-11-15.csv"
    assert monday_sunday(monday_morning) == (start, end)


def test_week_file_is_written_before_filtering_and_the_weekly_steps(conn, topics, tmp_path):
    import csv

    from desk.schedule import run_sunday_night

    sunday_night = datetime(2026, 11, 15, 22, 30, tzinfo=CLOCK)

    def fetch(start, end):
        return [
            _row("old", "2026-11-01T10:00:00+08:00", "DP charges were taken on a sell order last week"),
            _row("short", "2026-11-10T10:00:00+08:00", "good app"),
            _row("hindi", "2026-11-11T10:00:00+08:00", "bahut hi Shandar Lagi groww app ki service"),
            _row("kept", "2026-11-12T10:00:00+08:00", "DP charges were taken on a sell order today"),
        ]

    result = run_sunday_night(conn, topics, now=sunday_night, fetch=fetch, data_dir=tmp_path)
    with open(result["csv_path"], encoding="utf-8-sig", newline="") as handle:
        stored = list(csv.DictReader(handle))
    ids = [row["review_id"] for row in stored]
    assert ids == ["short", "hindi", "kept"]
    assert stored[0]["user_name"] == "Priya Shah"
    assert "good app" in stored[0]["content"]
    kept_ids = [row[0] for row in conn.execute("SELECT review_id FROM reviews")]
    assert kept_ids == ["kept"]
    assert "Priya Shah" not in " ".join(row[0] for row in conn.execute("SELECT content FROM reviews"))
    window = conn.execute("SELECT window_start, window_end FROM pulses").fetchone()
    assert window[0] == "2026-11-09T00:00:00+08:00"
    assert window[1] == "2026-11-15T23:59:59+08:00"
    assert result["pulse_id"]


def _row(review_id: str, created_at: str, content: str) -> dict:
    return {
        "review_id": review_id,
        "created_at": created_at,
        "created_at_ist": created_at,
        "score": "1",
        "thumbs_up": "0",
        "app_version": "18.22.1",
        "user_name": "Priya Shah",
        "content": content,
        "developer_reply": "thanks",
        "developer_replied_at": created_at,
    }
