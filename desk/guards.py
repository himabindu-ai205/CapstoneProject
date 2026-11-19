import re

_PAN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_PHONE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
_ACCOUNT = re.compile(r"\b\d{10,18}\b")
_SCOPE_PHRASES = (
    "should i buy",
    "should i sell",
    "should buy",
    "should sell",
    "buy this",
    "sell your",
    "cagr",
    "nav",
    "returns",
    "how much will i make",
)


def redact(text: str) -> str:
    cleaned = _PAN.sub("[PAN]", text)
    cleaned = _PHONE.sub("[PHONE]", cleaned)
    return _ACCOUNT.sub("[ACCOUNT]", cleaned)


def scope_flag(text: str) -> str | None:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _SCOPE_PHRASES):
        return "scope"
    return None


def sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]", text.strip())
    return sum(1 for part in parts if part.strip())


def word_count(text: str) -> int:
    return len(text.split())


def bullet_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith("- "))
