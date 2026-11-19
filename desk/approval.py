import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone

_SINKS = {
    "append_doc": "doc",
    "email_draft": "mailbox",
    "promote_explainer": "canonical",
}


def propose(conn: sqlite3.Connection, kind: str, destination: str, payload: str) -> str:
    action_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO approval_actions (id, kind, destination, payload, payload_hash, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """,
        (action_id, kind, destination, payload, _hash(payload)),
    )
    conn.commit()
    return action_id


def decide(conn: sqlite3.Connection, action_id: str, status: str) -> None:
    row = _load(conn, action_id)
    before = row["payload_hash"]
    conn.execute("UPDATE approval_actions SET status = ? WHERE id = ?", (status, action_id))
    _audit(conn, action_id, status, before, before)
    conn.commit()


def execute(conn: sqlite3.Connection, action_id: str, sink: dict) -> str:
    row = _load(conn, action_id)
    if row["status"] == "executed":
        _audit(conn, action_id, "noop", row["payload_hash"], row["payload_hash"])
        conn.commit()
        return ""
    if row["status"] != "approved" or row["payload_hash"] != _hash(row["payload"]):
        return ""
    sink[_SINKS[row["kind"]]].append(row["payload"])
    if row["kind"] == "promote_explainer":
        conn.execute(
            "UPDATE explainers SET status = 'canonical' WHERE id = ?",
            (row["payload"],),
        )
    conn.execute("UPDATE approval_actions SET status = 'executed' WHERE id = ?", (action_id,))
    conn.commit()
    return row["kind"]


def _load(conn: sqlite3.Connection, action_id: str) -> sqlite3.Row:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM approval_actions WHERE id = ?", (action_id,)).fetchone()
    if row is None:
        raise KeyError(action_id)
    return row


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def _audit(conn: sqlite3.Connection, entity_id: str, action: str, before_hash: str, after_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (entity_id, action, before_hash, after_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_id, action, before_hash, after_hash, datetime.now(timezone.utc).isoformat()),
    )
