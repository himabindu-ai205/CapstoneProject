def test_approving_the_pulse_does_not_write_mail_or_promote(conn):
    from desk.approval import decide, execute, propose

    doc, mail = propose(conn, "append_doc", "pulse.md", "Pulse body"), propose(conn, "email_draft", "product@groww", "Pulse body")
    explainer = propose(conn, "promote_explainer", "fees.dp", "explainer-id")
    decide(conn, doc, "approved")
    sink = {"doc": [], "mailbox": [], "canonical": []}
    assert execute(conn, doc, sink) == "append_doc"
    assert sink["doc"] == ["Pulse body"]
    assert sink["mailbox"] == []
    assert sink["canonical"] == []
    status = conn.execute("SELECT status FROM approval_actions WHERE id = ?", (mail,)).fetchone()[0]
    assert status == "pending"
    assert conn.execute("SELECT status FROM approval_actions WHERE id = ?", (explainer,)).fetchone()[0] == "pending"


def test_pending_email_is_refused(conn):
    import pytest
    from desk.approval import propose
    from desk.publish import email_draft

    action_id = propose(conn, "email_draft", "product@groww", "Pulse body")
    with pytest.raises(PermissionError):
        email_draft(conn, action_id, {"doc": [], "mailbox": [], "canonical": []})
