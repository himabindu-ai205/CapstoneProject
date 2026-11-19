import sqlite3
from pathlib import Path

import pytest

from desk.corpus import build_corpus
from desk.db import init_db
from desk.topics import Topic, extract_charge_topics

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "fixtures" / "pages"
DP_URL = "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied"
SCHEME_URL = "https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth"


def _task_pages() -> list[tuple[str, str]]:
    return [
        ("https://groww.in/pricing", (PAGES / "pricing.html").read_text(encoding="utf-8")),
        (DP_URL, (PAGES / "dp.html").read_text(encoding="utf-8")),
        (SCHEME_URL, (PAGES / "scheme.html").read_text(encoding="utf-8")),
    ]


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    build_corpus(connection, _task_pages(), "2026-11-13")
    return connection


@pytest.fixture
def topics() -> list[Topic]:
    found = extract_charge_topics("Brokerage\nDP charges\n")
    found += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    return found


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "reviews.csv"
    lines = [
        "review_id,created_at,created_at_ist,score,thumbs_up,app_version,user_name,content,developer_reply,developer_replied_at",
        "r1,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charges were taken on a sell order today,,",
        "r2,2026-11-03T10:00:00+08:00,2026-11-03T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charges were taken on a sell order today,,",
        "r3,2026-11-04T10:00:00+08:00,2026-11-04T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charges were taken on a sell order today,,",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
