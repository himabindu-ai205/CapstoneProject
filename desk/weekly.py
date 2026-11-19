import re
import uuid
from collections import defaultdict

from desk.approval import propose
from desk.corpus import CORPUS_URLS
from desk.guards import word_count
from desk.reviews import WINDOW_END, WINDOW_START, ingest_reviews
from desk.state import put_explainer, put_fee_analysis, put_pulse, put_theme, read_signals
from desk.tools import corpus_search, reviews_query
from desk.topics import Topic, assign_topic

_PRICING_URL = CORPUS_URLS[0]
_DP_URL = CORPUS_URLS[4]


def run_weekly(
    conn,
    csv_path: str,
    topics: list[Topic],
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict:
    window_start = window_start or WINDOW_START
    window_end = window_end or WINDOW_END
    ingested = ingest_reviews(conn, str(csv_path))
    reviews = reviews_query(conn, window_start, window_end)
    groups = _group(reviews, topics)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))[:5]
    signals = read_signals(conn)
    labels = {topic.id: topic.label for topic in topics}

    explainer_id = None
    blocks = []
    for signal in signals:
        if signal["topic"].startswith("fees."):
            opened = _open_explainer(conn, signal, groups.get(signal["topic"], []), labels)
            blocks.append(opened["block"])
            if explainer_id is None:
                explainer_id = opened["id"]
        else:
            blocks.append(_signal_block(signal, signal["confusion_summary"]))

    theme_rows = []
    for index, (topic_id, rows) in enumerate(ranked):
        theme_rows.append(
            {
                "label": labels.get(topic_id, topic_id),
                "topic_id": topic_id,
                "review_ids": [row["id"] for row in rows],
                "quote": rows[0]["quote"],
                "rank": index + 1 if index < 3 else None,
            }
        )
    signal_block = "\n".join(blocks)
    named = signals[0]["topic"] if signals else (theme_rows[0]["topic_id"] if theme_rows else "support")
    body = _fit_pulse(theme_rows, signal_block, _actions(named), window_start, window_end)
    pulse_id = put_pulse(conn, body, word_count(body), window_start, window_end, ingested["source_file_hash"], signal_block)
    theme_ids = [
        put_theme(
            conn,
            row["label"],
            row["topic_id"],
            row["review_ids"],
            row["quote"],
            window_start,
            window_end,
            row["rank"],
            pulse_id,
        )
        for row in theme_rows
    ]
    action_ids = [
        propose(conn, "append_doc", "pulse.md", body),
        propose(conn, "email_draft", "product@groww", body),
    ]
    if explainer_id is not None:
        action_ids.append(propose(conn, "promote_explainer", named, explainer_id))
    return {
        "pulse_id": pulse_id,
        "action_ids": action_ids,
        "theme_ids": theme_ids,
        "explainer_id": explainer_id,
    }


def _group(reviews: list[dict], topics: list[Topic]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for review in reviews:
        groups[assign_topic(review["quote"], topics)].append(review)
    return groups


def _open_explainer(conn, signal: dict, reviews: list[dict], labels: dict[str, str]) -> dict:
    hits = corpus_search(conn, labels.get(signal["topic"], signal["topic"]))
    supporting = _supporting_hits(hits)
    urls = [hit["url"] for hit in supporting]
    sentences = []
    for hit in supporting:
        for sentence in _sentences(hit["text"]):
            if len(sentences) < 6:
                sentences.append(sentence)
    bullets = "\n".join(f"- {sentence}" for sentence in sentences)
    explainer_id = str(uuid.uuid4())
    quote = reviews[0]["quote"] if reviews else ""
    what = f"{signal['confusion_summary']} {quote}".strip()
    analysis = {
        "fee_topic": signal["topic"],
        "what_is_confused": what,
        "review_ids": [review["id"] for review in reviews],
        "quotes": [review["quote"] for review in reviews],
        "window": {"start": signal["window_start"], "end": signal["window_end"]},
        "corpus_urls": urls,
        "explainer_id": explainer_id,
    }
    put_fee_analysis(conn, signal["id"], analysis)
    put_explainer(
        conn,
        explainer_id,
        signal["id"],
        signal["topic"],
        bullets,
        urls[0] if urls else None,
        urls[1] if len(urls) > 1 else None,
        supporting[0]["last_checked"] if supporting else None,
        _reply_text(sentences),
        None if len(urls) >= 2 else "ungrounded",
    )
    return {"id": explainer_id, "block": _signal_block(signal, what)}


def _supporting_hits(hits: list[dict]) -> list[dict]:
    by_url = {hit["url"]: hit for hit in hits if "DP" in hit["text"]}
    ordered = []
    for url in (_DP_URL, _PRICING_URL):
        if url in by_url:
            ordered.append(by_url[url])
    ordered.extend(hit for url, hit in by_url.items() if url not in (_DP_URL, _PRICING_URL))
    return ordered


def _signal_block(signal: dict, detail: str) -> str:
    return (
        "Recurring support signals\n"
        f"{signal['topic']} count {signal['count']}. "
        f"Window {signal['window_start']} through {signal['window_end']}.\n"
        f"{detail}"
    )


def _actions(topic: str) -> str:
    return "\n".join(
        (
            f"Review the {topic} questions in this window.",
            f"Clarify the published {topic} help text.",
            f"Watch {topic} questions again next week.",
        )
    )


def _fit_pulse(theme_rows: list[dict], signal_block: str, actions: str, window_start: str, window_end: str) -> str:
    quotes = [row["quote"] for row in theme_rows]
    body = _pulse_body(theme_rows, quotes, signal_block, actions, window_start, window_end)
    while word_count(body) > 250 and any(" " in quote for quote in quotes):
        quotes = [quote.rsplit(" ", 1)[0] if " " in quote else quote for quote in quotes]
        body = _pulse_body(theme_rows, quotes, signal_block, actions, window_start, window_end)
    return body


def _pulse_body(
    theme_rows: list[dict],
    quotes: list[str],
    signal_block: str,
    actions: str,
    window_start: str,
    window_end: str,
) -> str:
    lines = []
    for row, quote in zip(theme_rows, quotes):
        if row["rank"] is None:
            continue
        lines.append(
            f"{row['label']}: {len(row['review_ids'])} reviews. "
            f"Window {window_start} through {window_end}. {quote}"
        )
    parts = ["\n".join(lines)]
    if signal_block:
        parts.append(signal_block)
    parts.append(actions)
    return "\n".join(part for part in parts if part).strip()


def _sentences(text: str) -> list[str]:
    return [" ".join(part.split()) for part in re.split(r"[.!?]", text) if part.strip()]


def _reply_text(sentences: list[str]) -> str:
    chosen = sentences[:3]
    if not chosen:
        return ""
    return ". ".join(chosen) + "."
