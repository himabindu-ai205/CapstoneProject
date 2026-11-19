import sqlite3

from desk.approval import _hash, _load, execute


def append_doc(conn: sqlite3.Connection, action_id: str, sink: dict) -> str:
    return execute(conn, action_id, sink)


def email_draft(conn: sqlite3.Connection, action_id: str, sink: dict) -> None:
    row = _load(conn, action_id)
    if row["status"] != "approved" or row["payload_hash"] != _hash(row["payload"]):
        raise PermissionError("email_draft requires an approved action whose payload hash matches.")
    execute(conn, action_id, sink)
