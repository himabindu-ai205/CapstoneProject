import json
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from desk.approval import decide, execute
from desk.db import init_db
from desk.pulse_view import build_pulse, default_data_dir
from desk.response import edit_draft, handle_question, set_draft_status
from desk.topics import Topic, extract_charge_topics

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


class PlainModel:
    def complete(self, prompt: str) -> str:
        if "http" in prompt:
            url = next(part for part in prompt.split() if part.startswith("http"))
            return f"GROUNDED::{url}::See the cited Groww page."
        return "NOT_COVERED"


def _live_model():
    from desk.model import load_env

    load_env()
    if not os.environ.get("GROQ_API_KEY"):
        return PlainModel()
    from desk.model import GroqModel

    return GroqModel()


def _live_reviewer():
    from desk.model import load_env

    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from desk.model import GeminiModel

    return GeminiModel()


def create_app(
    conn: sqlite3.Connection | None = None,
    topics: list[Topic] | None = None,
    model=None,
    reviewer=None,
) -> FastAPI:
    if conn is None:
        conn = _open_default()
    conn.row_factory = sqlite3.Row
    if topics is None:
        topics = _default_topics(conn)

    if model is None:
        model = _live_model()
        if reviewer is None:
            reviewer = _live_reviewer()

    @asynccontextmanager
    async def lifespan(_application):
        count = conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
        if not count:
            try:
                from datetime import datetime

                from desk.build_corpus import build_live, http_get
                from desk.schedule import CLOCK

                build_live(conn, http_get, datetime.now(CLOCK).date().isoformat())
            except Exception:
                pass
        yield

    application = FastAPI(lifespan=lifespan)
    application.state.conn = conn
    application.state.topics = topics
    application.state.model = model
    application.state.reviewer = reviewer
    application.state.sink = {"doc": [], "mailbox": [], "canonical": []}

    def render(request: Request, name: str, **context):
        return TEMPLATES.TemplateResponse(request, name, context)

    @application.get("/")
    def home(request: Request, week: str = ""):
        return render(request, "ui_pulse.html", pulse=build_pulse(default_data_dir(), week or None))

    @application.post("/questions")
    def post_question(question: str = Form("")):
        handle_question(conn, question, application.state.model, topics, application.state.reviewer)
        return RedirectResponse("/", status_code=303)

    @application.post("/ui/ask")
    def ui_ask(question: str = Form("")):
        try:
            result = handle_question(
                conn, question, application.state.model, topics, application.state.reviewer
            )
        except Exception:
            return {
                "body": "The desk could not complete that lookup. Try again in a moment.",
                "source": "",
            }
        return {"body": result["body"], "source": result.get("citation_url") or ""}

    @application.post("/drafts/{draft_id}")
    def post_draft(
        draft_id: str,
        body: str | None = Form(None),
        status: str | None = Form(None),
    ):
        if status in ("approved", "rejected"):
            set_draft_status(conn, draft_id, status)
        elif body is not None:
            edit_draft(conn, draft_id, body)
        return RedirectResponse("/", status_code=303)

    @application.get("/pulse")
    def pulse(request: Request):
        return render(
            request,
            "pulse.html",
            page="pulse",
            themes=_themes(conn),
            signals=_signals(conn),
            pulses=_pulses(conn),
        )

    @application.get("/sources")
    def sources(request: Request):
        return render(request, "sources.html", page="sources", chunks=_cited_chunks(conn))

    @application.get("/approval")
    def approval(request: Request):
        return render(request, "approval.html", page="approval", actions=_actions(conn))

    @application.post("/approval/{action_id}")
    def post_approval(action_id: str, status: str = Form(...)):
        if status in ("approved", "rejected"):
            decide(conn, action_id, status)
        if status == "approved":
            execute(conn, action_id, application.state.sink)
        return RedirectResponse("/approval", status_code=303)

    @application.get("/explainers")
    def explainers(request: Request):
        return render(request, "explainers.html", page="explainers", rows=_canonical(conn))

    @application.get("/ui")
    def ui_home():
        return RedirectResponse("/#pulse", status_code=302)

    @application.get("/ui/pulse")
    def ui_pulse():
        return RedirectResponse("/#pulse", status_code=302)

    @application.get("/ui/support")
    def ui_support():
        return RedirectResponse("/#support", status_code=302)

    return application


def __getattr__(name: str):
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(name)


def _open_default() -> sqlite3.Connection:
    path = Path(os.environ.get("DESK_DB", "data/desk.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _default_topics(conn: sqlite3.Connection) -> list[Topic]:
    row = conn.execute(
        "SELECT text FROM corpus_chunks WHERE url = ?",
        ("https://groww.in/pricing",),
    ).fetchone()
    found = extract_charge_topics(row["text"] if row else "")
    found += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    return found


def _themes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT label, topic_id, review_ids, quotes, window_start, window_end, rank
        FROM themes
        ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank
        """
    ).fetchall()
    themes = []
    for row in rows:
        item = dict(row)
        item["review_ids"] = _load_json(item["review_ids"], [])
        themes.append(item)
    return themes


def _signals(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT topic, count, window_start, window_end, item_ids, confusion_summary, fee_confusion_analysis
        FROM recurrence
        WHERE count >= 5 AND topic != 'topic.unknown'
        ORDER BY topic
        """
    ).fetchall()
    signals = []
    for row in rows:
        item = dict(row)
        item["item_ids"] = _load_json(item["item_ids"], [])
        item["analysis"] = _load_json(item["fee_confusion_analysis"], None)
        signals.append(item)
    return signals


def _pulses(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT body, word_count, window_start, window_end, status FROM pulses"
    ).fetchall()
    return [dict(row) for row in rows]


def _cited_chunks(conn: sqlite3.Connection) -> list[dict]:
    urls: list[str] = []
    for row in conn.execute(
        "SELECT citation_url FROM drafts WHERE citation_url IS NOT NULL AND citation_url != ''"
    ):
        urls.append(row["citation_url"])
    for row in conn.execute("SELECT url_a, url_b FROM explainers"):
        for url in (row["url_a"], row["url_b"]):
            if url:
                urls.append(url)
    seen = []
    for url in urls:
        if url not in seen:
            seen.append(url)
    chunks = []
    for url in seen:
        row = conn.execute(
            "SELECT url, title, last_checked FROM corpus_chunks WHERE url = ? ORDER BY id LIMIT 1",
            (url,),
        ).fetchone()
        if row is None:
            chunks.append({"url": url, "title": "", "last_checked": ""})
        else:
            chunks.append(dict(row))
    return chunks


def _actions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, kind, destination, payload, status FROM approval_actions ORDER BY rowid"
    ).fetchall()
    return [dict(row) for row in rows]


def _canonical(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, topic, url_a, url_b, reply_text, last_checked,
               (SELECT COUNT(*) FROM drafts WHERE reused_explainer_id = explainers.id) AS reuse_count
        FROM explainers
        WHERE status = 'canonical'
        ORDER BY topic
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _load_json(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
