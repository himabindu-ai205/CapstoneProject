import hashlib
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Protocol

from desk.guards import redact, scope_flag, sentence_count
from desk.intent import REFUSALS, classify_intent
from desk.recurrence import record
from desk.reviews import WINDOW_END, WINDOW_START
from desk.corpus import content_words
from desk.tools import corpus_search, reviews_query
from desk.topics import Topic, assign_topic

_REFUSALS = ("advice", "performance", "pii")


class ModelClient(Protocol):
    def complete(self, prompt: str) -> str: ...


def handle_question(
    conn: sqlite3.Connection,
    question: str,
    model: ModelClient,
    topics: list[Topic],
    reviewer: ModelClient | None = None,
) -> dict:
    queue_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO queue_items (id, question, intent, topic, status, created_at)
        VALUES (?, ?, 'pending', 'topic.unknown', 'pending', ?)
        """,
        (queue_id, question, _now()),
    )
    conn.commit()
    return orchestrate(conn, queue_id, question, model, topics, reviewer)


def orchestrate(
    conn: sqlite3.Connection,
    queue_id: str,
    question: str,
    model: ModelClient,
    topics: list[Topic],
    reviewer: ModelClient | None = None,
) -> dict:
    intent = classify_intent(question)
    topic = assign_topic(question, topics)
    redacted = redact(question)
    conn.execute(
        "UPDATE queue_items SET question = ?, intent = ?, topic = ? WHERE id = ?",
        (redacted, intent, topic, queue_id),
    )
    if intent in _REFUSALS:
        body = REFUSALS[intent]
        conn.execute(
            "INSERT INTO traces (event_id, intent, tool_names, text) VALUES (?, ?, '', NULL)",
            (queue_id, intent),
        )
        draft_id = _put_draft(conn, queue_id, body, None, "", "", None)
        conn.commit()
        return _result(queue_id, draft_id, intent, topic, body, None, "", "", "refusal", None)

    canonical = _canonical_agent(conn, topic)
    reviews = _reviews_agent(conn)
    if canonical["reply_text"]:
        official = {"hits": [{"url": url} for url in canonical["urls"]]}
    else:
        official = _official_agent(conn, redacted, model)
    if canonical["reply_text"]:
        body = canonical["reply_text"]
        citation = canonical["url"]
        reused = canonical["explainer_id"]
        outcome = "reused"
    elif official["covered"]:
        body = official["body"]
        citation = official["citation_url"]
        reused = None
        outcome = "draft"
    else:
        body = official["body"]
        citation = None
        reused = None
        outcome = "not_covered"
    routing_note = _routing_note(topic, reviews, canonical["count"], reused)
    flags = review_draft(body, citation, official["hits"], reviewer)
    draft_id = _put_draft(conn, queue_id, body, citation, routing_note, flags, reused)
    conn.commit()
    record(conn, queue_id, intent, topic, redacted, WINDOW_START, WINDOW_END)
    return _result(queue_id, draft_id, intent, topic, body, citation, routing_note, flags, outcome, reused)


def _official_agent(conn: sqlite3.Connection, query: str, model: ModelClient) -> dict:
    hits = corpus_search(conn, query)
    urls = [hit["url"] for hit in hits]
    prompt = query if not urls else (
        "Use GROUNDED::<url>::<one sentence copied from that page>, or NOT_COVERED.\n"
        f"{query}\n" + "\n".join(f"{hit['url']} {_best_line(query, hit['text'])}" for hit in hits)
    )
    raw = model.complete(prompt)
    page_url, page_sentence = _best_supported(query, hits) if hits else ("", "")
    needed = [word for word in content_words(query) if word in page_sentence.lower()]
    grounded = _grounded_sentence(raw, urls)
    if grounded is not None:
        url, sentence = grounded
        if (
            url == page_url
            and _supported(sentence, hits)
            and _covers(sentence, needed)
            and len(sentence) <= len(page_sentence) + 80
        ):
            return {"body": sentence, "citation_url": url, "hits": hits, "covered": True}
    if hits:
        return {"body": page_sentence, "citation_url": page_url, "hits": hits, "covered": True}
    titles = _titles(conn, hits)
    body = f"Not covered. Searched: {query}. Pages: {', '.join(titles)}."
    return {"body": body, "citation_url": None, "hits": hits, "covered": False}


def _reviews_agent(conn: sqlite3.Connection) -> dict:
    rows = reviews_query(conn, WINDOW_START, WINDOW_END)
    return {
        "ids": [row["id"] for row in rows],
        "quotes": [row["quote"] for row in rows],
        "window": f"{WINDOW_START} through {WINDOW_END}",
    }


def _canonical_agent(conn: sqlite3.Connection, topic: str) -> dict:
    row = conn.execute(
        """
        SELECT id, reply_text, url_a, url_b FROM explainers
        WHERE topic = ? AND status = 'canonical'
        LIMIT 1
        """,
        (topic,),
    ).fetchone()
    count_row = conn.execute(
        """
        SELECT count FROM recurrence
        WHERE topic = ? AND window_start = ? AND window_end = ?
        """,
        (topic, WINDOW_START, WINDOW_END),
    ).fetchone()
    count = count_row[0] if count_row else 0
    if row is None or not row[1]:
        return {"reply_text": None, "explainer_id": None, "url": None, "urls": [], "count": count}
    urls = [url for url in (row[2], row[3]) if url]
    return {
        "reply_text": row[1],
        "explainer_id": row[0],
        "url": row[2],
        "urls": urls,
        "count": count,
    }


_REVIEW_FLAGS = ("scope", "length", "ungrounded")


def review_draft(body: str, citation: str | None, hits: list[dict], reviewer: ModelClient | None = None) -> str:
    coded = _code_flags(body, citation, hits)
    if reviewer is None:
        return coded
    try:
        parsed = _parse_flags(reviewer.complete(_review_prompt(body, citation, hits)))
    except Exception:
        return coded
    if parsed is None:
        return coded
    return parsed


def _code_flags(body: str, citation: str | None, hits: list[dict]) -> str:
    flags = []
    if scope_flag(body):
        flags.append("scope")
    if sentence_count(body) > 3:
        flags.append("length")
    hit_urls = {hit["url"] for hit in hits}
    if citation and citation not in hit_urls:
        flags.append("ungrounded")
    return ",".join(flags)


def _review_prompt(body: str, citation: str | None, hits: list[dict]) -> str:
    urls = " ".join(hit["url"] for hit in hits) or "(none)"
    cited = citation or "(none)"
    return (
        "Review this draft. Flag scope when it recommends a buy or sell, or states a return, NAV, or CAGR. "
        "Flag length when it has more than three sentences. "
        "Flag ungrounded when the citation is not one of the allowed source URLs. "
        "A missing citation is not ungrounded.\n"
        f"Citation: {cited}\n"
        f"Allowed source URLs: {urls}\n"
        f"Draft: {body}"
    )


def _parse_flags(raw: str) -> str | None:
    line = raw.strip().splitlines()[-1].strip().lower().rstrip(".")
    if line == "clear":
        return ""
    tokens = [part.strip() for part in line.split(",") if part.strip()]
    if not tokens or any(token not in _REVIEW_FLAGS for token in tokens):
        return None
    return ",".join(name for name in _REVIEW_FLAGS if name in tokens)


def edit_draft(conn: sqlite3.Connection, draft_id: str, body: str) -> None:
    before = conn.execute("SELECT body_hash FROM drafts WHERE id = ?", (draft_id,)).fetchone()[0]
    after = _hash(body)
    conn.execute("UPDATE drafts SET body = ?, body_hash = ? WHERE id = ?", (body, after, draft_id))
    _audit(conn, draft_id, "edit", before, after)
    conn.commit()


def set_draft_status(conn: sqlite3.Connection, draft_id: str, status: str) -> None:
    queue_id, body_hash = conn.execute(
        "SELECT queue_item_id, body_hash FROM drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))
    conn.execute("UPDATE queue_items SET status = ? WHERE id = ?", (status, queue_id))
    _audit(conn, draft_id, status, body_hash, body_hash)
    conn.commit()


def _audit(conn: sqlite3.Connection, entity_id: str, action: str, before_hash: str, after_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (entity_id, action, before_hash, after_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_id, action, before_hash, after_hash, _now()),
    )


def _put_draft(
    conn: sqlite3.Connection,
    queue_id: str,
    body: str,
    citation: str | None,
    routing_note: str,
    flags: str,
    reused: str | None,
) -> str:
    draft_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO drafts (
            id, queue_item_id, body, citation_url, routing_note, flags,
            reused_explainer_id, body_hash, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        (draft_id, queue_id, body, citation, routing_note, flags, reused, _hash(body)),
    )
    return draft_id


def _grounded_sentence(raw: str, urls: list[str]) -> tuple[str, str] | None:
    if not raw.startswith("GROUNDED::"):
        return None
    _, url, sentence = raw.split("::", 2)
    if url not in urls:
        return None
    return url, sentence


def _best_line(query: str, text: str) -> str:
    words = content_words(query)
    lines = [line.strip() for line in re.split(r"[\n]+|(?<!\d)\.(?!\d)", text) if line.strip()]
    if not lines:
        return " ".join(text.split())[:400]

    def score(line: str) -> float:
        lowered = line.lower()
        matched = [word for word in words if word in lowered]
        if not matched:
            return 0
        total = 0.0
        for word in matched:
            freq = sum(1 for other in lines if word in other.lower())
            total += 1 / freq
        return total

    def has_figure(i: int) -> bool:
        blob = lines[i] if i + 1 >= len(lines) else f"{lines[i]} {lines[i + 1]}"
        return bool(re.search(r"\d|₹|%", blob))

    numbered = [i for i in range(len(lines)) if score(lines[i]) and has_figure(i)]
    pool = numbered or list(range(len(lines)))
    index = max(pool, key=lambda i: (score(lines[i]), -i))
    window = []
    if index > 0 and (score(lines[index - 1]) or lines[index - 1].endswith(":")):
        window.append(lines[index - 1])
    window.append(lines[index])
    for line in lines[index + 1 : index + 8]:
        lowered = line.lower()
        if "cagr" in lowered or "nav" in lowered or "return" in lowered:
            break
        if score(line) == 0 and not re.search(r"\d|₹|%", line):
            break
        window.append(line)
        if len(" ".join(window)) > 420:
            break
    gst_line = next(
        (
            line
            for line in lines[index : index + 12]
            if "gst" in line.lower() and re.search(r"\d", line)
        ),
        "",
    )
    if gst_line and gst_line not in window:
        window.append(gst_line)
    return " ".join(window)[:500]


def _covers(sentence: str, words: list[str]) -> bool:
    lowered = sentence.lower()
    return all(word in lowered for word in words)


def _best_supported(query: str, hits: list[dict]) -> tuple[str, str]:
    hit = hits[0]
    return hit["url"], _best_line(query, hit["text"])


def _supported(sentence: str, hits: list[dict]) -> bool:
    needle = " ".join(sentence.lower().split())
    if not needle:
        return False
    for hit in hits:
        if needle in " ".join(hit["text"].lower().split()):
            return True
    return False


def _titles(conn: sqlite3.Connection, hits: list[dict]) -> list[str]:
    if hits:
        return [hit["title"] for hit in hits]
    return [row[0] for row in conn.execute("SELECT title FROM corpus_chunks ORDER BY id")]


def _routing_note(topic: str, reviews: dict, count: int, reused: str | None) -> str:
    ids = ",".join(reviews["ids"])
    reused_label = "yes" if reused else "no"
    return (
        f"theme={topic}; review_ids={ids}; window={reviews['window']}; "
        f"recurrence={count}; reused={reused_label}"
    )


def _result(
    queue_id: str,
    draft_id: str,
    intent: str,
    topic: str,
    body: str,
    citation: str | None,
    routing_note: str,
    flags: str,
    outcome: str,
    reused: str | None,
) -> dict:
    return {
        "queue_id": queue_id,
        "draft_id": draft_id,
        "intent": intent,
        "topic": topic,
        "body": body,
        "citation_url": citation,
        "routing_note": routing_note,
        "flags": flags,
        "outcome": outcome,
        "reused_explainer_id": reused,
    }


def _hash(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
