import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

import httpx

GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

REQUESTS_PER_MINUTE = 30
REQUESTS_PER_DAY = 1000
TOKENS_PER_MINUTE = 8000
TOKENS_PER_DAY = 200_000
MAX_COMPLETION_TOKENS = 256


class GroqBudgetError(RuntimeError):
    pass


class GroqModel:
    """Chat client for Groq's free tier.

    A call is refused before it is sent when the prompt plus the completion
    cap would pass 8K tokens in the current minute or 200K in the current UTC day.
    """

    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None):
        self.api_key = api_key or os.environ["GROQ_API_KEY"]
        self.model = GROQ_MODEL
        self._http = http or httpx.Client(timeout=30)
        self._budget = _Budget()

    def complete(self, prompt: str) -> str:
        reserved = estimate_tokens(prompt) + MAX_COMPLETION_TOKENS
        entry = self._budget.reserve(reserved)
        try:
            response = self._http.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0,
                    "max_completion_tokens": MAX_COMPLETION_TOKENS,
                    "reasoning_effort": "low",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Reply with exactly one line. "
                                "If one listed page supports the answer, reply "
                                "GROUNDED::<that url>::<one sentence>. "
                                "Otherwise reply NOT_COVERED."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
        except Exception:
            self._budget.release(entry)
            raise
        if response.status_code != 200:
            self._budget.release(entry)
            raise RuntimeError(f"Groq returned {response.status_code}: {response.text[:300]}")
        payload = response.json()
        usage = payload.get("usage") or {}
        actual = usage.get("total_tokens")
        if isinstance(actual, int):
            self._budget.settle(entry, actual)
        content = payload["choices"][0]["message"].get("content") or ""
        if not content.strip():
            raise RuntimeError("Groq returned an empty completion.")
        return content.strip()


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


class _Budget:
    def __init__(self):
        self._lock = threading.Lock()
        self._minute: deque[list] = deque()
        self._day = _utc_day()
        self._day_requests = 0
        self._day_tokens = 0

    def reserve(self, tokens: int) -> list:
        with self._lock:
            self._roll_day()
            now = time.monotonic()
            self._trim(now)
            if tokens > TOKENS_PER_MINUTE:
                raise GroqBudgetError(
                    f"This call is about {tokens} tokens. The Groq free tier allows {TOKENS_PER_MINUTE} tokens per minute."
                )
            minute_tokens = sum(item[1] for item in self._minute)
            if len(self._minute) >= REQUESTS_PER_MINUTE:
                raise GroqBudgetError(f"Groq free tier allows {REQUESTS_PER_MINUTE} requests per minute.")
            if minute_tokens + tokens > TOKENS_PER_MINUTE:
                raise GroqBudgetError(
                    f"This minute already used {minute_tokens} tokens. {tokens} more would pass {TOKENS_PER_MINUTE}."
                )
            if self._day_requests >= REQUESTS_PER_DAY:
                raise GroqBudgetError(f"Groq free tier allows {REQUESTS_PER_DAY} requests per day.")
            if self._day_tokens + tokens > TOKENS_PER_DAY:
                raise GroqBudgetError(
                    f"Today already used {self._day_tokens} tokens. {tokens} more would pass {TOKENS_PER_DAY}."
                )
            entry = [now, tokens]
            self._minute.append(entry)
            self._day_requests += 1
            self._day_tokens += tokens
            return entry

    def settle(self, entry: list, actual: int) -> None:
        with self._lock:
            delta = actual - entry[1]
            entry[1] = actual
            self._day_tokens += delta

    def release(self, entry: list) -> None:
        with self._lock:
            if entry in self._minute:
                self._minute.remove(entry)
            self._day_requests = max(0, self._day_requests - 1)
            self._day_tokens = max(0, self._day_tokens - entry[1])

    def _trim(self, now: float) -> None:
        while self._minute and now - self._minute[0][0] >= 60:
            self._minute.popleft()

    def _roll_day(self) -> None:
        today = _utc_day()
        if today != self._day:
            self._day = today
            self._day_requests = 0
            self._day_tokens = 0


def _utc_day():
    return datetime.now(timezone.utc).date()


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REVIEWER_SYSTEM = (
    "You are the support-desk reviewer. "
    "Reply with one line only: CLEAR, or a comma-separated list using only "
    "scope, length, and ungrounded. Do not add a fact, a link, or a number."
)


class GeminiModel:
    """Reviewer client. The official draft stays on Groq."""

    def __init__(self, api_key: str | None = None, model: str | None = None, http: httpx.Client | None = None):
        self.api_key = api_key or os.environ["GEMINI_API_KEY"]
        self.model = model or os.environ.get("GEMINI_MODEL") or GEMINI_MODEL
        self._http = http or httpx.Client(timeout=30)

    def complete(self, prompt: str) -> str:
        response = self._http.post(
            GEMINI_URL.format(model=self.model),
            headers={"x-goog-api-key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": REVIEWER_SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 64,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"Gemini returned {response.status_code}: {response.text[:300]}")
        content = _gemini_text(response.json())
        if not content:
            raise RuntimeError("Gemini returned an empty completion.")
        return content


def load_env(path: str | None = None) -> None:
    env_path = path or str(_project_root() / ".env")
    try:
        text = open(env_path, encoding="utf-8").read()
    except OSError:
        return
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]


def _gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [part["text"] for part in parts if part.get("text") and not part.get("thought")]
    return "\n".join(texts).strip()
