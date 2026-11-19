from desk.guards import bullet_count


def test_fee_theme_without_a_signal_does_not_open_an_explainer(conn, topics, csv_path):
    from desk.weekly import run_weekly

    result = run_weekly(conn, csv_path, topics)
    assert result["explainer_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM explainers").fetchone()[0] == 0
    themes = conn.execute("SELECT review_ids, window_start, window_end FROM themes").fetchall()
    assert themes
    assert all(row[0] not in ("", "[]") for row in themes)
    assert themes[0][1] == "2026-11-01T00:09:09+08:00"


def test_fee_signal_gets_the_analysis_and_the_pulse_copies_it(conn, topics, csv_path):
    from desk.recurrence import record
    from desk.weekly import run_weekly

    for i in range(5):
        record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    result = run_weekly(conn, csv_path, topics)
    analysis = conn.execute("SELECT fee_confusion_analysis FROM recurrence WHERE topic = 'fees.dp'").fetchone()[0]
    assert analysis and "fees.dp" in analysis
    pulse = conn.execute("SELECT body, word_count FROM pulses").fetchone()
    assert pulse[1] <= 250
    assert "fees.dp" in pulse[0] and "When are DP charges levied?"[:20] in pulse[0]
    bullets = conn.execute("SELECT bullets FROM explainers WHERE id = ?", (result["explainer_id"],)).fetchone()[0]
    assert bullet_count(bullets) <= 6
    kinds = {row[0] for row in conn.execute("SELECT kind FROM approval_actions")}
    assert kinds == {"append_doc", "email_draft", "promote_explainer"}
