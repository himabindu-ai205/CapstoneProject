import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from desk.db import connect, init_db
from desk.topics import Topic, extract_charge_topics
from desk.weekly import run_weekly

CLOCK = timezone(timedelta(hours=8))
CSV_COLUMNS = (
    "review_id",
    "created_at",
    "created_at_ist",
    "score",
    "thumbs_up",
    "app_version",
    "user_name",
    "content",
    "developer_reply",
    "developer_replied_at",
)


def containing_week(now: datetime) -> tuple[datetime, datetime]:
    moment = now.astimezone(CLOCK) if now.tzinfo else now.replace(tzinfo=CLOCK)
    monday = moment.date() - timedelta(days=moment.weekday())
    sunday = monday + timedelta(days=6)
    start = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=CLOCK)
    end = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=CLOCK)
    return start, end


def monday_sunday(now: datetime) -> tuple[datetime, datetime]:
    moment = now.astimezone(CLOCK) if now.tzinfo else now.replace(tzinfo=CLOCK)
    if moment.weekday() == 6:
        sunday = moment.date()
    else:
        sunday = moment.date() - timedelta(days=moment.weekday() + 1)
    monday = sunday - timedelta(days=6)
    start = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=CLOCK)
    end = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=CLOCK)
    return start, end


def csv_name(start: datetime, end: datetime) -> str:
    return f"Playstore_{start.date().isoformat()}_{end.date().isoformat()}.csv"


def run_sunday_night(conn, topics: list[Topic], *, now: datetime, fetch, data_dir: Path) -> dict:
    start, end = monday_sunday(now)
    window_start = start.isoformat(timespec="seconds")
    window_end = end.isoformat(timespec="seconds")
    rows = [row for row in fetch(start, end) if window_start <= row["created_at"] <= window_end]
    path = Path(data_dir) / csv_name(start, end)
    _write_csv(path, rows)
    processed = run_weekly(conn, str(path), topics, window_start, window_end)
    return {
        "csv_path": str(path),
        "window_start": window_start,
        "window_end": window_end,
        **processed,
    }


def main() -> None:
    from desk.playstore_fetch import fetch_playstore_reviews

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(data_dir / "desk.sqlite")
    init_db(conn)
    _ensure_corpus(conn)
    topics = _topics(conn)
    result = run_sunday_night(
        conn,
        topics,
        now=datetime.now(CLOCK),
        fetch=fetch_playstore_reviews,
        data_dir=data_dir,
    )
    print(result["csv_path"])
    print(result["window_start"], result["window_end"])
    print(result["pulse_id"])


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _ensure_corpus(conn) -> None:
    from desk.corpus import build_corpus

    count = conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
    if count:
        return
    pages = Path("fixtures") / "pages"
    listing = [
        ("https://groww.in/pricing", "pricing.html"),
        (
            "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied",
            "dp.html",
        ),
        ("https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth", "scheme.html"),
    ]
    loaded = []
    for url, name in listing:
        file = pages / name
        if file.exists():
            loaded.append((url, file.read_text(encoding="utf-8")))
    if loaded:
        build_corpus(conn, loaded, datetime.now(CLOCK).date().isoformat())


def _topics(conn) -> list[Topic]:
    row = conn.execute(
        "SELECT text FROM corpus_chunks WHERE url = ?",
        ("https://groww.in/pricing",),
    ).fetchone()
    found = extract_charge_topics(row[0] if row else "")
    found += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    return found


if __name__ == "__main__":
    main()
