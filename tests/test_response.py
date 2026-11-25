from tests.fakes import ScriptedModel

DP_URL = "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied"


def test_nav_question_is_the_fixed_refusal_and_does_not_call_the_model(conn, topics):
    from desk.intent import REFUSALS
    from desk.response import handle_question

    model = ScriptedModel()
    result = handle_question(conn, "What is the NAV of SBI Large Cap?", model, topics)
    assert result["intent"] == "performance"
    assert result["body"] == REFUSALS["performance"]
    assert result["outcome"] == "refusal"
    assert model.calls == 0
    stored = conn.execute("SELECT question FROM queue_items").fetchone()[0]
    assert "NAV" in stored  # performance text is not PII and is kept
    pan = handle_question(conn, "PAN ABCDE1234F where is my demat?", ScriptedModel(), topics)
    assert pan["body"] == REFUSALS["pii"]
    assert "ABCDE1234F" not in conn.execute("SELECT question FROM queue_items WHERE id = ?", (pan["queue_id"],)).fetchone()[0]
    trace = conn.execute("SELECT text FROM traces WHERE event_id = ?", (pan["queue_id"],)).fetchone()[0]
    assert trace is None


def test_not_covered_names_the_query(conn, topics):
    from desk.response import handle_question

    result = handle_question(conn, "What is the weather on Mars?", ScriptedModel(), topics)
    assert "not covered" in result["body"].lower()
    assert "weather" in result["body"].lower()


def test_grounded_draft_uses_only_a_returned_url(conn, topics):
    from desk.guards import sentence_count
    from desk.response import handle_question

    result = handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    assert result["citation_url"] == DP_URL
    assert sentence_count(result["body"]) <= 3
    assert "ungrounded" not in result["flags"]


def test_reviewer_uses_gemini_flags_and_refusals_skip_it(conn, topics):
    from desk.response import handle_question

    class FlagModel:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            assert "Draft:" in prompt
            return "scope, ungrounded"

    answer = ScriptedModel()
    reviewer = FlagModel()
    result = handle_question(conn, "When are DP charges levied?", answer, topics, reviewer)
    assert reviewer.calls == 1
    assert answer.calls == 1
    assert result["flags"] == "scope,ungrounded"

    refused = FlagModel()
    handle_question(conn, "What is the NAV of SBI Large Cap?", ScriptedModel(), topics, refused)
    assert refused.calls == 0
