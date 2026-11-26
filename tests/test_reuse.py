def test_sixth_question_copies_the_canonical_reply(conn, topics, csv_path):
    from desk.approval import decide, execute
    from desk.recurrence import record
    from desk.response import handle_question
    from desk.weekly import run_weekly
    from tests.fakes import ScriptedModel

    for i in range(5):
        record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    run_weekly(conn, csv_path, topics)
    actions = dict(conn.execute("SELECT kind, id FROM approval_actions"))
    decide(conn, actions["promote_explainer"], "approved")
    execute(conn, actions["promote_explainer"], {"doc": [], "mailbox": [], "canonical": []})
    calls = ScriptedModel()
    sixth = handle_question(conn, "When are DP charges levied again?", calls, topics)
    stored = conn.execute("SELECT reply_text FROM explainers WHERE status = 'canonical'").fetchone()[0]
    assert sixth["body"] == f"DP charges are levied on a sell. {stored}"
    assert sixth["reused_explainer_id"]
    assert calls.calls == 0
