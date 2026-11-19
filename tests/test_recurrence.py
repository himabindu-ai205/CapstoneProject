from desk.guards import sentence_count
from desk.recurrence import confusion_summary, record


def test_five_unknown_questions_do_not_signal(conn):
    for i in range(5):
        assert record(conn, f"u{i}", "factual", "topic.unknown", "hello", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00") is None
    assert conn.execute("SELECT COUNT(*) FROM recurrence").fetchone()[0] == 0


def test_fifth_fee_question_stores_a_two_sentence_summary(conn):
    signal = None
    for i in range(5):
        signal = record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    assert signal is not None
    assert signal["count"] == 5
    assert signal["item_ids"] == ["q0", "q1", "q2", "q3", "q4"]
    assert sentence_count(signal["confusion_summary"]) <= 2
    assert "DP" in signal["confusion_summary"]
    assert confusion_summary("fees.dp", ["When are DP charges levied?" * 1]).count(".") <= 2
