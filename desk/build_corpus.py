import os
from datetime import datetime
from pathlib import Path

import httpx

from desk.corpus import CORPUS_URLS, build_corpus
from desk.db import connect, init_db
from desk.schedule import CLOCK


def fetch_pages(get) -> list[tuple[str, str]]:
    return [(url, get(url)) for url in CORPUS_URLS]


def build_live(conn, get, fetched_on: str) -> int:
    count = conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
    if count:
        return count
    pages = fetch_pages(get)
    build_corpus(conn, pages, fetched_on)
    return len(pages)


def http_get(url: str) -> str:
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.text


def main() -> None:
    path = Path(os.environ.get("DESK_DB", "data/desk.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(str(path))
    init_db(conn)
    stored = build_live(conn, http_get, datetime.now(CLOCK).date().isoformat())
    print(stored)


if __name__ == "__main__":
    main()
