import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Topic:
    id: str
    label: str


def extract_charge_topics(pricing_text: str) -> list[Topic]:
    topics = []
    for line in pricing_text.splitlines():
        label = line.strip()
        if not label:
            continue
        if label.lower() == "dp charges":
            slug = "dp"
        else:
            words = re.findall(r"[a-z0-9]+", label.lower())
            slug = "_".join(words)
        topics.append(Topic(f"fees.{slug}", label))
    return topics


def assign_topic(text: str, topics: list[Topic]) -> str:
    lowered = text.lower()
    if "dp charge" in lowered or "depository" in lowered:
        return "fees.dp"
    for topic in topics:
        if topic.id == "fees.dp":
            continue
        if _label_matches(topic.label.lower(), lowered):
            return topic.id
    return "topic.unknown"


def _label_matches(label: str, lowered: str) -> bool:
    if label in lowered:
        return True
    text_words = re.findall(r"[a-z0-9]+", lowered)
    for label_word in label.split():
        if label_word in lowered:
            return True
        for word in text_words:
            if len(word) >= 4 and label_word.startswith(word):
                return True
    return False
