from tests.fakes import ScriptedModel


def test_edit_changes_only_that_draft(conn, topics):
    from desk.response import edit_draft, handle_question, set_draft_status

    a = handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    b = handle_question(conn, "How do I withdraw money?", ScriptedModel(), topics)
    before_b = conn.execute("SELECT body FROM drafts WHERE queue_item_id = ?", (b["queue_id"],)).fetchone()[0]
    edit_draft(conn, a["draft_id"], "Edited sentence only.")
    assert conn.execute("SELECT body FROM drafts WHERE id = ?", (a["draft_id"],)).fetchone()[0] == "Edited sentence only."
    assert conn.execute("SELECT body FROM drafts WHERE queue_item_id = ?", (b["queue_id"],)).fetchone()[0] == before_b
    set_draft_status(conn, a["draft_id"], "rejected")
    assert conn.execute("SELECT status FROM queue_items WHERE id = ?", (b["queue_id"],)).fetchone()[0] != "rejected"


def test_edit_does_not_change_canonical_explainer(conn, topics):
    from desk.response import edit_draft, handle_question

    conn.execute(
        """
        INSERT INTO explainers (id, topic, bullets, reply_text, status)
        VALUES ('e1', 'fees.dp', '- DP charges apply per sell transaction.', 'CANONICAL', 'canonical')
        """
    )
    conn.commit()
    result = handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    assert result["body"] == "CANONICAL"
    assert result["reused_explainer_id"] == "e1"
    edit_draft(conn, result["draft_id"], "Edited sentence only.")
    assert conn.execute("SELECT reply_text FROM explainers WHERE id = 'e1'").fetchone()[0] == "CANONICAL"
    assert conn.execute("SELECT body FROM drafts WHERE id = ?", (result["draft_id"],)).fetchone()[0] == "Edited sentence only."
