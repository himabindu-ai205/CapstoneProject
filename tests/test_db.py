import sqlite3

from desk.db import init_db


def test_schema_has_the_link_tables():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "corpus_chunks",
        "reviews",
        "queue_items",
        "drafts",
        "recurrence",
        "themes",
        "pulses",
        "explainers",
        "approval_actions",
        "audit_log",
        "traces",
    } <= names
    cols = {row[1] for row in conn.execute("PRAGMA table_info(recurrence)")}
    assert {
        "topic",
        "count",
        "window_start",
        "window_end",
        "item_ids",
        "confusion_summary",
        "fee_confusion_analysis",
    } <= cols
