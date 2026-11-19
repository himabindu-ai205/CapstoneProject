import json
import sqlite3
import tempfile
from pathlib import Path

from desk.approval import decide, execute
from desk.corpus import build_corpus
from desk.db import init_db
from desk.response import edit_draft, handle_question
from desk.reviews import WINDOW_END, WINDOW_START
from desk.topics import Topic, extract_charge_topics
from desk.weekly import run_weekly
from tests.fakes import ScriptedModel

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "fixtures" / "pages"
DP_URL = "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied"
SCHEME_URL = "https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth"
DISPLAY_NAME = "Priya Shah"
FORBIDDEN = ("9876543210", "ABCDE1234F", DISPLAY_NAME)
TABLES = (
    "reviews",
    "queue_items",
    "drafts",
    "recurrence",
    "themes",
    "pulses",
    "explainers",
    "approval_actions",
    "audit_log",
    "traces",
)
QUESTIONS = (
    "When are DP charges levied?",
    "How do I withdraw money?",
    "Where do I see my demat number?",
    "What is the weather on Mars?",
    "Should I buy SBI Large Cap?",
    "What is the NAV of SBI Flexicap?",
    "My number is 9876543210",
)
REPHRASES = (
    "Which of these five funds should I buy?",
    "What CAGR did SBI Flexicap give?",
    "Call me on 9876543210",
    "My phone is 9876543210",
)


class CheckFailure(Exception):
    def __init__(self, check: str, case: str, detail: str):
        self.check = check
        self.case = case
        self.detail = detail
        super().__init__(f"{check}: {case}: {detail}")


def run_checks(conn: sqlite3.Connection, topics: list[Topic], csv_path: str) -> list[str]:
    lines = []
    try:
        _feasibility(conn, topics, csv_path)
        lines.append("feasibility: pass")
        _edits(conn)
        lines.append("correctness of edits: pass")
        _grounding(conn)
        lines.append("grounding and compliance: pass")
    except CheckFailure as failure:
        lines.append(f"{failure.check}: {failure.case}: {failure.detail}")
        raise
    return lines


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        build_corpus(conn, _pages(), "2026-11-13")
        csv_path = Path(folder) / "reviews.csv"
        _write_csv(csv_path)
        try:
            for line in run_checks(conn, _topics(conn), str(csv_path)):
                print(line)
        except CheckFailure as failure:
            print(f"{failure.check}: {failure.case}: {failure.detail}")
            return 1
    return 0


def _feasibility(conn: sqlite3.Connection, topics: list[Topic], csv_path: str) -> None:
    questions = QUESTIONS + REPHRASES
    for question in questions:
        handle_question(conn, question, ScriptedModel(), topics)
    drafts = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
    if drafts != len(questions):
        raise CheckFailure("feasibility", "draft-count", f"{drafts} drafts for {len(questions)} questions")
    missing = conn.execute(
        """
        SELECT queue_items.id FROM queue_items
        LEFT JOIN drafts ON drafts.queue_item_id = queue_items.id
        WHERE drafts.id IS NULL
        """
    ).fetchone()
    if missing is not None:
        raise CheckFailure("feasibility", "queue-outcome", f"queue item {missing[0]} has no draft")
    run_weekly(conn, csv_path, topics)
    pulse = conn.execute("SELECT word_count FROM pulses").fetchone()
    if pulse is None or pulse[0] > 250:
        raise CheckFailure("feasibility", "pulse-length", "pulse is missing or over 250 words")
    for row in conn.execute("SELECT id, review_ids, window_start, window_end FROM themes"):
        ids = json.loads(row[1] or "[]")
        if not ids or row[2] != WINDOW_START or row[3] != WINDOW_END:
            raise CheckFailure("feasibility", "theme-window", f"theme {row[0]} is missing ids or the file window")


def _edits(conn: sqlite3.Connection) -> None:
    draft_id = conn.execute("SELECT id FROM drafts ORDER BY rowid LIMIT 1").fetchone()[0]
    before = _snapshot(conn)
    edit_draft(conn, draft_id, "Edited sentence only.")
    after = _snapshot(conn)
    changed = _changed_tables(after, before)
    if changed != {"drafts", "audit_log"}:
        raise CheckFailure("correctness of edits", "edit-diff", f"tables changed: {sorted(changed)}")
    columns = [row[1] for row in conn.execute("PRAGMA table_info(drafts)")]
    body_at = columns.index("body")
    hash_at = columns.index("body_hash")
    before_drafts = {row[0]: row for row in before["drafts"]}
    for row in after["drafts"]:
        old = before_drafts[row[0]]
        if row[0] != draft_id and row != old:
            raise CheckFailure("correctness of edits", "edit-diff", f"draft {row[0]} changed")
        if row[0] == draft_id:
            if row[body_at] != "Edited sentence only.":
                raise CheckFailure("correctness of edits", "edit-body", "edited draft body did not change")
            same = [index for index in range(len(row)) if index not in (body_at, hash_at) and row[index] != old[index]]
            if same:
                raise CheckFailure("correctness of edits", "edit-diff", "edited draft changed a field other than body")
    if len(after["audit_log"]) != len(before["audit_log"]) + 1:
        raise CheckFailure("correctness of edits", "edit-diff", "edit did not write one audit row")
    action = conn.execute("SELECT id FROM approval_actions WHERE kind = 'append_doc'").fetchone()
    email = conn.execute("SELECT id, status FROM approval_actions WHERE kind = 'email_draft'").fetchone()
    if action is None or email is None:
        raise CheckFailure("correctness of edits", "weekly-actions", "append_doc or email_draft is missing")
    decide(conn, action[0], "approved")
    sink = {"doc": [], "mailbox": [], "canonical": []}
    execute(conn, action[0], sink)
    if not sink["doc"] or sink["mailbox"] or sink["canonical"]:
        raise CheckFailure("correctness of edits", "append-doc", "approving the pulse wrote another sink")
    status = conn.execute("SELECT status FROM approval_actions WHERE id = ?", (email[0],)).fetchone()[0]
    if status != "pending":
        raise CheckFailure("correctness of edits", "email-pending", f"email_draft is {status}")


def _grounding(conn: sqlite3.Connection) -> None:
    urls = {row[0] for row in conn.execute("SELECT url FROM corpus_chunks")}
    review_ids = {row[0] for row in conn.execute("SELECT review_id FROM reviews")}
    claims = []
    for draft_id, citation in conn.execute("SELECT id, citation_url FROM drafts WHERE citation_url IS NOT NULL AND citation_url != ''"):
        claims.append(("draft", draft_id, citation, urls))
    for theme_id, raw_ids in conn.execute("SELECT id, review_ids FROM themes"):
        for review_id in json.loads(raw_ids or "[]"):
            claims.append(("theme", theme_id, review_id, review_ids))
    if len(claims) < 1:
        raise CheckFailure("grounding and compliance", "claims", "no citation or review id to check")
    for kind, case, value, allowed in claims:
        if value not in allowed:
            raise CheckFailure("grounding and compliance", f"{kind}:{case}", f"{value} is not in the store")
    blob = _text_blob(conn)
    for forbidden in FORBIDDEN:
        if forbidden in blob:
            raise CheckFailure("grounding and compliance", "pii-scan", f"found {forbidden}")


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    snap = {}
    for table in TABLES:
        snap[table] = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    return snap


def _changed_tables(after: dict[str, list[tuple]], before: dict[str, list[tuple]]) -> set[str]:
    return {table for table in TABLES if after[table] != before[table]}


def _text_blob(conn: sqlite3.Connection) -> str:
    parts = []
    for table in TABLES:
        for row in conn.execute(f"SELECT * FROM {table}"):
            parts.extend(str(value) for value in row if value is not None)
    return "\n".join(parts)


def _pages() -> list[tuple[str, str]]:
    return [
        ("https://groww.in/pricing", (PAGES / "pricing.html").read_text(encoding="utf-8")),
        (DP_URL, (PAGES / "dp.html").read_text(encoding="utf-8")),
        (SCHEME_URL, (PAGES / "scheme.html").read_text(encoding="utf-8")),
    ]


def _topics(conn: sqlite3.Connection) -> list[Topic]:
    row = conn.execute("SELECT text FROM corpus_chunks WHERE url = ?", ("https://groww.in/pricing",)).fetchone()
    found = extract_charge_topics(row[0] if row else "")
    found += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    return found


def _write_csv(path: Path) -> None:
    lines = [
        "review_id,created_at,created_at_ist,score,thumbs_up,app_version,user_name,content,developer_reply,developer_replied_at",
        "r1,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charges were taken on a sell order today,,",
        "r2,2026-11-03T10:00:00+08:00,2026-11-03T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charges were taken on a sell order today,,",
        "r3,2026-11-04T10:00:00+08:00,2026-11-04T07:30:00+05:30,1,0,18.22.1,Priya Shah,PAN ABCDE1234F was charged on a sell order today,,",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
