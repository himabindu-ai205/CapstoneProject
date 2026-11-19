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


def test_pages_render_the_signal_and_hide_user_names(client, seeded):
    queue = client.get("/")
    assert queue.status_code == 200
    assert "When are DP charges levied?" in queue.text
    assert "Priya Shah" not in queue.text
    pulse = client.get("/pulse")
    assert "Recurring support signals" in pulse.text
    assert "fees.dp" in pulse.text
    approval = client.get("/approval")
    assert "append_doc" in approval.text and "promote_explainer" in approval.text
    assert "email_draft" in approval.text
