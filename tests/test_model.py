import json

import httpx

from desk.model import GEMINI_MODEL, GROQ_MODEL, TOKENS_PER_MINUTE, GeminiModel, GroqBudgetError, GroqModel


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_complete_calls_gpt_oss_on_groq():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "GROUNDED::https://groww.in/pricing::See the pricing page."}}],
                "usage": {"total_tokens": 40},
            },
        )

    model = GroqModel(api_key="test-key", http=_client(handler))
    text = model.complete("When are DP charges levied?")
    assert text.startswith("GROUNDED::https://groww.in/pricing::")
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == GROQ_MODEL
    assert seen["body"]["max_completion_tokens"] == 256


def test_a_prompt_over_the_minute_budget_is_not_sent():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "NOT_COVERED"}}]})

    model = GroqModel(api_key="test-key", http=_client(handler))
    try:
        model.complete("x" * (TOKENS_PER_MINUTE * 4))
    except GroqBudgetError as error:
        assert "8000" in str(error)
    else:
        raise AssertionError("expected the minute token cap to refuse the call")
    assert calls["n"] == 0


def test_a_second_call_in_the_same_minute_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "NOT_COVERED"}}],
                "usage": {"total_tokens": TOKENS_PER_MINUTE},
            },
        )

    model = GroqModel(api_key="test-key", http=_client(handler))
    assert model.complete("short") == "NOT_COVERED"
    try:
        model.complete("again")
    except GroqBudgetError as error:
        assert "minute" in str(error).lower()
    else:
        raise AssertionError("expected the second call to be refused")


def test_reviewer_calls_gemini_flash():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "CLEAR"}]}}]},
        )

    model = GeminiModel(api_key="gemini-key", model="gemini-2.5-flash", http=_client(handler))
    assert model.complete("Draft: DP charges apply per sell.") == "CLEAR"
    assert seen["key"] == "gemini-key"
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert seen["body"]["generationConfig"]["temperature"] == 0
    assert "reviewer" in seen["body"]["systemInstruction"]["parts"][0]["text"].lower()
    assert model.model == GEMINI_MODEL
