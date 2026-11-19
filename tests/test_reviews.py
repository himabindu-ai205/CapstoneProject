import sqlite3
from pathlib import Path

from desk.db import init_db
from desk.reviews import WINDOW_END, WINDOW_START, ingest_reviews


def test_ingest_drops_name_and_redacts_pan(tmp_path: Path):
    csv_path = tmp_path / "reviews.csv"
    csv_path.write_text(
        "review_id,created_at,created_at_ist,score,thumbs_up,app_version,user_name,content,developer_reply,developer_replied_at\n"
        "r1,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charge on PAN ABCDE1234F was taken from the account,thanks,2026-11-02T11:00:00+08:00\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    ingest_reviews(conn, str(csv_path))
    row = conn.execute("SELECT review_id, content FROM reviews").fetchone()
    assert row[0] == "r1"
    assert "ABCDE1234F" not in row[1] and "[PAN]" in row[1]
    blob = " ".join("".join(map(str, r)) for r in conn.execute("SELECT * FROM reviews"))
    assert "Priya Shah" not in blob and "thanks" not in blob
    assert WINDOW_START == "2026-11-01T00:09:09+08:00"
    assert WINDOW_END == "2026-11-11T11:29:18+08:00"


def test_ingest_drops_short_and_non_english_reviews(tmp_path: Path):
    csv_path = tmp_path / "reviews.csv"
    csv_path.write_text(
        "review_id,created_at,created_at_ist,score,thumbs_up,app_version,user_name,content,developer_reply,developer_replied_at\n"
        "short,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,5,0,18.22.1,A,good app,,\n"
        "hindi,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,5,0,18.22.1,B,bahut hi Shandar Lagi groww app ki service,,\n"
        "devanagari,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,5,0,18.22.1,C,यह ऐप बिल्कुल अच्छा नहीं है क्योंकि पैसा कट गया,,\n"
        "kept,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,5,0,18.22.1,D,This app is easy to use for daily investing,,\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    result = ingest_reviews(conn, str(csv_path))
    stored = [row[0] for row in conn.execute("SELECT review_id FROM reviews")]
    assert stored == ["kept"]
    assert result["count"] == 1
