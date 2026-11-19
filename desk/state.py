import json
import sqlite3
import uuid


def read_signals(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, intent, topic, window_start, window_end, count, item_ids, confusion_summary
        FROM recurrence
        WHERE count >= 5
          AND topic != 'topic.unknown'
          AND confusion_summary IS NOT NULL
          AND confusion_summary != ''
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "intent": row[1],
            "topic": row[2],
            "window_start": row[3],
            "window_end": row[4],
            "count": row[5],
            "item_ids": json.loads(row[6]),
            "confusion_summary": row[7],
        }
        for row in rows
    ]


def put_fee_analysis(conn: sqlite3.Connection, signal_id: str, analysis: dict) -> None:
    conn.execute(
        "UPDATE recurrence SET fee_confusion_analysis = ? WHERE id = ?",
        (json.dumps(analysis), signal_id),
    )
    conn.commit()


def put_theme(
    conn: sqlite3.Connection,
    label: str,
    topic_id: str,
    review_ids: list[str],
    quote: str,
    window_start: str,
    window_end: str,
    rank: int | None,
    pulse_id: str,
) -> str:
    theme_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO themes (
            id, label, topic_id, review_ids, quotes, window_start, window_end, rank, pulse_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (theme_id, label, topic_id, json.dumps(review_ids), quote, window_start, window_end, rank, pulse_id),
    )
    conn.commit()
    return theme_id


def put_explainer(
    conn: sqlite3.Connection,
    explainer_id: str,
    signal_id: str,
    topic: str,
    bullets: str,
    url_a: str | None,
    url_b: str | None,
    last_checked: str | None,
    reply_text: str,
    flags: str | None,
) -> str:
    conn.execute(
        """
        INSERT INTO explainers (
            id, signal_id, topic, bullets, url_a, url_b, last_checked, reply_text, status, flags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (explainer_id, signal_id, topic, bullets, url_a, url_b, last_checked, reply_text, flags),
    )
    conn.commit()
    return explainer_id


def put_pulse(
    conn: sqlite3.Connection,
    body: str,
    word_count: int,
    window_start: str,
    window_end: str,
    input_hash: str,
    signals_block: str,
) -> str:
    pulse_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO pulses (
            id, body, word_count, window_start, window_end, input_hash, model_id, signals_block, status
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 'pending')
        """,
        (pulse_id, body, word_count, window_start, window_end, input_hash, signals_block),
    )
    conn.commit()
    return pulse_id
