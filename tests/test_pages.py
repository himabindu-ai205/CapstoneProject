import sqlite3

import pytest


@pytest.fixture
def seeded(conn, topics, csv_path, tmp_path):
    from desk.recurrence import record
    from desk.response import handle_question
    from desk.weekly import run_weekly
    from tests.fakes import ScriptedModel

    handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    for i in range(5):
        record(
            conn,
            f"q{i}",
            "factual",
            "fees.dp",
            "When are DP charges levied?",
            "2026-11-01T00:09:09+08:00",
            "2026-11-11T11:29:18+08:00",
        )
    run_weekly(conn, csv_path, topics)
    shared = sqlite3.connect(tmp_path / "pages.sqlite", check_same_thread=False)
    conn.backup(shared)
    shared.row_factory = sqlite3.Row
    return shared


@pytest.fixture
def client(seeded, topics):
    from fastapi.testclient import TestClient

    from desk.app import create_app
    from tests.fakes import ScriptedModel

    return TestClient(create_app(seeded, topics, ScriptedModel()))


def test_pulse_page_offers_append_doc_and_email_draft(client):
    page = client.get("/")
    assert "Append doc" in page.text
    assert "Email draft" in page.text
    assert 'action="/pulse/append-doc"' in page.text
    assert 'target="_blank"' in page.text
    assert 'action="/pulse/email-draft"' in page.text


def test_each_button_writes_one_google_tool(client, seeded):
    import os

    calls = []

    def record(name, arguments):
        calls.append((name, arguments))

    client.app.state.google_call = record
    os.environ["GOOGLE_DOC_ID"] = "doc-16"
    os.environ["PULSE_DRAFT_TO"] = "product@groww"
    try:
        appended = client.post("/pulse/append-doc", data={"week": "2026-11-16"}, follow_redirects=False)
        drafted = client.post("/pulse/email-draft", data={"week": "2026-11-16"}, follow_redirects=False)
    finally:
        os.environ.pop("GOOGLE_DOC_ID", None)
        os.environ.pop("PULSE_DRAFT_TO", None)

    assert appended.headers["location"] == "https://docs.google.com/document/d/doc-16/edit"
    assert drafted.headers["location"].endswith("notice=drafted")
    assert [name for name, _args in calls] == ["append_to_google_doc", "create_email_draft"]
    assert calls[0][1]["documentId"] == "doc-16"
    assert calls[0][1]["content"].startswith("\n\n")
    assert calls[0][1]["content"].endswith("\n")
    assert calls[1][1]["to"] == ["product@groww"]
    assert "send_email" not in [name for name, _args in calls]
    rows = seeded.execute("SELECT kind, status FROM approval_actions ORDER BY rowid").fetchall()
    assert [row["kind"] for row in rows[-2:]] == ["append_doc", "email_draft"]
    assert [row["status"] for row in rows[-2:]] == ["executed", "executed"]


def test_append_doc_waits_for_a_document_id(client, seeded):
    import os

    calls = []
    client.app.state.google_call = lambda name, arguments: calls.append(name)
    os.environ["GOOGLE_DOC_ID"] = ""
    try:
        response = client.post("/pulse/append-doc", data={"week": "2026-11-16"}, follow_redirects=False)
    finally:
        os.environ.pop("GOOGLE_DOC_ID", None)
    assert response.headers["location"].endswith("notice=need-doc")
    assert calls == []
    blank = seeded.execute(
        "SELECT COUNT(*) FROM approval_actions WHERE kind = 'append_doc' AND destination = ''"
    ).fetchone()[0]
    assert blank == 0


def test_pages_render_the_signal_and_hide_user_names(client, seeded):
    home = client.get("/")
    assert home.status_code == 200
    assert "Weekly Product Pulse" in home.text
    assert "Customer support" in home.text
    assert "Priya Shah" not in home.text
    pulse = client.get("/pulse")
    assert "Recurring support signals" in pulse.text
    assert "fees.dp" in pulse.text
    approval = client.get("/approval")
    assert "append_doc" in approval.text and "promote_explainer" in approval.text
    assert "email_draft" in approval.text
