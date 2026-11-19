import sqlite3

from desk.corpus import search
from desk.reviews import query_reviews


def corpus_search(conn: sqlite3.Connection, query: str) -> list[dict]:
    _reject_url(query)
    return search(conn, query)


def reviews_query(conn: sqlite3.Connection, window_start: str, window_end: str) -> list[dict]:
    _reject_url(window_start, window_end)
    return query_reviews(conn, window_start, window_end)


def _reject_url(*values: str) -> None:
    for value in values:
        if value.startswith("http://") or value.startswith("https://"):
            raise ValueError("Read tools do not accept a caller-supplied URL.")
