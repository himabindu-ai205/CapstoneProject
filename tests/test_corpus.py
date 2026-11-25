import sqlite3

from desk.corpus import CORPUS_URLS, build_corpus, search, strip_performance
from desk.db import init_db

DP_URL = "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied"
SCHEME_URL = "https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth"


def test_twelve_urls_and_no_performance_left_in_chunks():
    assert len(CORPUS_URLS) == 12
    assert DP_URL in CORPUS_URLS
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    pages = [
        ("https://groww.in/pricing", "<h1>Pricing</h1><p>Brokerage</p><p>DP charges</p>"),
        (DP_URL, "<h1>When are DP charges levied?</h1><p>DP charges apply per sell transaction.</p>"),
        (SCHEME_URL, "<p>Category: Large Cap. Expense ratio 0.9. CAGR 18% over 5 years. NAV 92.</p>"),
    ]
    build_corpus(conn, pages, "2026-11-13")
    scheme = conn.execute("SELECT text FROM corpus_chunks WHERE url = ?", (SCHEME_URL,)).fetchone()[0]
    assert "CAGR" not in scheme and "NAV" not in scheme and "18%" not in scheme
    assert "Expense ratio" in scheme
    kept = strip_performance("Expense ratio\n0.85%\nExit load 1% if redeemed within 1 year. CAGR 12%.")
    assert "0.85%" in kept and "Exit load" in kept and "12%" not in kept
    hits = search(conn, "DP charges levied")
    assert hits and hits[0]["url"] == DP_URL
    assert hits[0]["last_checked"] == "2026-11-13"
    assert strip_performance("NAV 10") == ""
