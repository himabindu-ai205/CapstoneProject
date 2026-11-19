import json
import sqlite3
import uuid


def confusion_summary(topic: str, questions: list[str]) -> str:
    first = questions[0][:80].rstrip(".!?") if questions else ""
    return (
        f"Questions on {topic} are asking the same thing in this window "
        f"They ask: {first}."
    )


def record(
    conn: sqlite3.Connection,
    item_id: str,
    intent: str,
    topic: str,
    question: str,
    window_start: str,
    window_end: str,
) -> dict | None:
    if topic == "topic.unknown":
        return None
    row = conn.execute(
        """
        SELECT id, item_ids, count, confusion_summary FROM recurrence
        WHERE intent = ? AND topic = ? AND window_start = ? AND window_end = ?
        """,
        (intent, topic, window_start, window_end),
    ).fetchone()
    if row is None:
        signal_id = str(uuid.uuid4())
        item_ids = [item_id]
        count = 1
        summary = confusion_summary(topic, [question])
        conn.execute(
            """
            INSERT INTO recurrence (
                id, intent, topic, window_start, window_end, count, item_ids, confusion_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (signal_id, intent, topic, window_start, window_end, count, json.dumps(item_ids), summary),
        )
    else:
        signal_id = row[0]
        item_ids = json.loads(row[1])
        item_ids.append(item_id)
        count = row[2] + 1
        summary = confusion_summary(topic, [_first_question(row[3], question)])
        conn.execute(
            """
            UPDATE recurrence
            SET count = ?, item_ids = ?, confusion_summary = ?
            WHERE id = ?
            """,
            (count, json.dumps(item_ids), summary, signal_id),
        )
    conn.commit()
    if count < 5:
        return None
    return {
        "id": signal_id,
        "intent": intent,
        "topic": topic,
        "window_start": window_start,
        "window_end": window_end,
        "count": count,
        "item_ids": item_ids,
        "confusion_summary": summary,
    }


def _first_question(summary: str | None, fallback: str) -> str:
    marker = "They ask: "
    if summary and marker in summary:
        return summary.split(marker, 1)[1].strip().rstrip(".")
    return fallback
