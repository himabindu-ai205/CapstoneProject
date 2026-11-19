import sqlite3

from desk.build_corpus import build_live, fetch_pages
from desk.corpus import CORPUS_URLS
from desk.db import init_db


def test_fetch_reads_each_of_the_twelve_urls_once():
    seen = []

    def get(url: str) -> str:
        seen.append(url)
        return "<html><h1>Page</h1><p>DP charges</p></html>"

    pages = fetch_pages(get)
    assert seen == list(CORPUS_URLS)
    assert len(pages) == 12


def test_a_second_build_does_not_fetch():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    calls = {"n": 0}

    def get(url: str) -> str:
        calls["n"] += 1
        return "<html><h1>Pricing</h1><p>Brokerage</p><p>DP charges</p></html>"

    assert build_live(conn, get, "2026-11-13") == 12
    assert build_live(conn, get, "2026-11-14") == 12
    assert calls["n"] == 12
