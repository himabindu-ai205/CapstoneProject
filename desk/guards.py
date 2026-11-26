import re

_PAN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_AADHAAR = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_PASSPORT = re.compile(r"\b[A-Za-z]\d{7}\b")
_PHONE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
_ACCOUNT = re.compile(r"\b\d{10,18}\b")
# "my pan number is xyx" states a PAN even when the value is not ABCDE1234F.
_PAN_CLAIM = re.compile(
    r"(\b(?:my\s+)?pan(?:\s+card)?(?:\s+(?:number|no\.?))+\s*(?:is|:)\s*"
    r"|\bmy\s+pan(?:\s+card)?\s*(?:is|:)\s*)([A-Za-z0-9][A-Za-z0-9-]*)",
    re.IGNORECASE,
)
_AADHAAR_CLAIM = re.compile(
    r"(\b(?:my\s+)?aadha+r(?:\s+card)?(?:\s+(?:number|no\.?))+\s*(?:is|:)\s*"
    r"|\bmy\s+aadha+r(?:\s+card)?\s*(?:is|:)\s*)([A-Za-z0-9][A-Za-z0-9-]*)",
    re.IGNORECASE,
)
_PASSPORT_CLAIM = re.compile(
    r"(\b(?:my\s+)?passport(?:\s+(?:number|no\.?))+\s*(?:is|:)\s*"
    r"|\bmy\s+passport\s*(?:is|:)\s*)([A-Za-z0-9][A-Za-z0-9-]*)",
    re.IGNORECASE,
)
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


def has_pii(text: str) -> bool:
    return bool(
        _PAN.search(text)
        or _AADHAAR.search(text)
        or _PASSPORT.search(text)
        or _PHONE.search(text)
        or _ACCOUNT.search(text)
        or _PAN_CLAIM.search(text)
        or _AADHAAR_CLAIM.search(text)
        or _PASSPORT_CLAIM.search(text)
    )


def redact(text: str) -> str:
    cleaned = _PAN.sub("[PAN]", text)
    cleaned = _AADHAAR.sub("[AADHAAR]", cleaned)
    cleaned = _PASSPORT.sub("[PASSPORT]", cleaned)
    cleaned = _PAN_CLAIM.sub(r"\1[PAN]", cleaned)
    cleaned = _AADHAAR_CLAIM.sub(r"\1[AADHAAR]", cleaned)
    cleaned = _PASSPORT_CLAIM.sub(r"\1[PASSPORT]", cleaned)
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
