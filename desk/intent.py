import re

_PAN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_PHONE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
_ACCOUNT = re.compile(r"\b\d{10,18}\b")
_ADVICE = (
    "should i",
    "which of these funds",
    "buy this",
    "sell your",
    "portfolio",
)
_PERFORMANCE = (
    "cagr",
    "nav",
    "returns",
    "profit",
    "how much will i make",
)

REFUSALS = {
    "advice": "This desk states published Groww facts and does not recommend buying, selling, or holding.",
    "performance": "This desk states published Groww facts and does not give returns or performance figures.",
    "pii": "This desk cannot take a PAN, phone number, or account number. Remove it and ask the question again.",
}


def classify_intent(text: str) -> str:
    if _PAN.search(text) or _PHONE.search(text) or _ACCOUNT.search(text):
        return "pii"
    lowered = text.lower()
    if any(phrase in lowered for phrase in _ADVICE):
        return "advice"
    if re.search(r"\bbuy\b", lowered) or re.search(r"\bhold\b", lowered):
        return "advice"
    if re.search(r"\bsell\b", lowered) and "per sell" not in lowered:
        return "advice"
    if any(phrase in lowered for phrase in _PERFORMANCE):
        return "performance"
    return "factual"
