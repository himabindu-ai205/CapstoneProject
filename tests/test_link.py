def test_a_pricing_question_adds_one_sentence_to_the_reused_answer():
    from desk.response import _with_question_sentence

    rates = (
        "₹3.5 per sell transaction for men and ₹3.25 per sell transaction for women. "
        "Groww charges ₹16.5 per sell transaction, or ₹0 if the sell value is under ₹100. "
        "An 18% GST applies to the total of Depository and Groww charges."
    )
    body = _with_question_sentence("Is the depository charge listed on the pricing page?", rates)
    assert body.startswith("Yes, the depository charge is listed on the pricing page. ")
    assert rates in body


def test_five_repeats_reach_the_pulse_and_the_approved_explainer_is_reused(conn, topics):
    import sqlite3

    from desk.approval import decide, execute
    from desk.app import _support_signals
    from desk.recurrence import record
    from desk.response import handle_question
    from desk.weekly import sync_fee_explainers
    from tests.fakes import ScriptedModel

    window = ("2026-11-23T00:00:00+08:00", "2026-11-29T23:59:59+08:00")
    for i in range(4):
        assert record(conn, f"q{i}", "factual", "fees.dp", "How much is the DP charge per sell?", *window) is None
    assert sync_fee_explainers(conn, topics) == []

    signal = record(conn, "q4", "factual", "fees.dp", "How much is the DP charge per sell?", *window)
    assert signal["count"] == 5
    opened = sync_fee_explainers(conn, topics)
    assert opened
    conn.row_factory = sqlite3.Row
    assert _support_signals(conn, "2026-11-16T00:00:00+08:00", "2026-11-22T23:59:59+08:00") == []
    shown = _support_signals(conn, *window)
    assert shown[0]["topic"] == "fees.dp"
    assert shown[0]["count"] == 5
    assert shown[0]["explainer_status"] == "pending"
    assert "How much is the DP charge per sell" in shown[0]["confusion_summary"]

    action_id = conn.execute(
        "SELECT id FROM approval_actions WHERE kind = 'promote_explainer'"
    ).fetchone()[0]
    decide(conn, action_id, "approved")
    execute(conn, action_id, {"doc": [], "mailbox": [], "canonical": []})

    calls = ScriptedModel()
    sixth = handle_question(conn, "Why was a DP charge taken from my wallet?", calls, topics)
    stored = conn.execute("SELECT reply_text FROM explainers WHERE status = 'canonical'").fetchone()[0]
    assert sixth["body"].startswith("A DP charge is taken when shares are sold. ")
    assert stored in sixth["body"]
    assert sixth["reused_explainer_id"]
    assert calls.calls == 0
