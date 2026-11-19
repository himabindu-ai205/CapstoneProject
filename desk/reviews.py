import csv
import hashlib
import re
import sqlite3
from pathlib import Path

from desk.guards import redact

WINDOW_START = "2026-11-01T00:09:09+08:00"
WINDOW_END = "2026-11-11T11:29:18+08:00"
_MIN_WORDS = 8
# Hindi and Bengali words read in data/playstore.csv, including Latin spellings.
# English typos such as "treading" or "wrost" are not in this set.
_OTHER_LANGUAGE = frozenset(
    """
    aane aap achcha achha ager ageo amar bach bachane bahut baje bakwas baki
    banata bdha befkuf bekar bhai bhut bhuut bhi bnde boli bubu chahie chahiye
    chakkkar chalta chilo chor chuke daale dakho dange denge deoya dhng dicche
    dwara duba dusri ekdam eska etni fasa firse gache gahtiya gayee ggqanq
    ghata gya hai hajar hme hocche honge hona hota hoyeche humko isake isliye
    isme jab jaega jagah jaise jankari jinko jitna jua kabhi kai karna karne
    karoge kasam ke keval khub khush ki kiya kmmummm ko korchi korlam krte kuch
    kucch kya laga lagbhag lage lagi lagta lekin liya lootera maza mene mera
    mgr milta minnk muje nahin nahi nhi ora paise paisa paiso padega padh pahle
    pichle profe puchte pura rahe rahega raha rahta reha rupaye saaf saal sahi
    sath se shandar smz sobai soho thik trf tumhara ultopalta uska utna vadi
    vaha wala yahi yar yeh
    """.split()
)


def ingest_reviews(conn: sqlite3.Connection, csv_path: str) -> dict:
    file_bytes = Path(csv_path).read_bytes()
    digest = hashlib.sha256(file_bytes).hexdigest()
    count = 0
    with open(csv_path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            content = row.get("content") or ""
            if not _keep_review(content):
                continue
            conn.execute(
                """
                INSERT INTO reviews (
                    review_id, content, created_at, score, created_at_ist,
                    thumbs_up, app_version, source_file_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["review_id"],
                    redact(row.get("content") or ""),
                    row["created_at"],
                    _int(row.get("score")),
                    row.get("created_at_ist"),
                    _int(row.get("thumbs_up")),
                    row.get("app_version"),
                    digest,
                ),
            )
            count += 1
    conn.commit()
    return {"count": count, "source_file_hash": digest}


def query_reviews(conn: sqlite3.Connection, window_start: str, window_end: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT review_id, content, created_at FROM reviews
        WHERE created_at >= ? AND created_at <= ?
        ORDER BY created_at
        """,
        (window_start, window_end),
    )
    return [{"id": row[0], "quote": row[1], "date": row[2]} for row in rows]


def _keep_review(text: str) -> bool:
    if any(ch.isalpha() and not ch.isascii() for ch in text):
        return False
    tokens = _words(text)
    if len(tokens) < _MIN_WORDS:
        return False
    return not any(token in _OTHER_LANGUAGE for token in tokens)


def _words(text: str) -> list[str]:
    words = []
    for raw in text.split():
        token = raw.strip(".,!?;:\"'()[]{}…-–—/\\*|").lower()
        if re.search(r"[a-z0-9]", token):
            words.append(token)
    return words


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
