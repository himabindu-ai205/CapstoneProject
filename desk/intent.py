import re

from desk.guards import has_pii

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
    "pii": "This desk cannot take a PAN, Aadhaar, passport number, phone number, or account number. Remove it and ask the question again.",
}


def _charge_on_a_sell(lowered: str) -> bool:
    if re.search(r"\bsell (?:this|my|the fund|these|it)\b", lowered):
        return False
    about_charges = re.search(r"\b(?:dp|charge|charges|fee|fees|levied|levy|brokerage|gst)\b", lowered)
    return bool(about_charges and re.search(r"\bsell\b", lowered))


def classify_intent(text: str) -> str:
    if has_pii(text):
        return "pii"
    lowered = text.lower()
    if any(phrase in lowered for phrase in _ADVICE):
        return "advice"
    if re.search(r"\bbuy\b", lowered) or re.search(r"\bhold\b", lowered):
        return "advice"
    if re.search(r"\bsell\b", lowered) and not _charge_on_a_sell(lowered):
        return "advice"
    if any(phrase in lowered for phrase in _PERFORMANCE):
        return "performance"
    return "factual"
