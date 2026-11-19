# Support Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one FastAPI app that turns `data/playstore.csv` into a weekly pulse and answers Groww questions with cited drafts, joined by a recurring support signal whose fee confusion analysis becomes the reused explainer.

**Architecture:** One process owns SQLite, four MCP tool surfaces, and five server-rendered pages. The orchestrator is the entry of the response loop and the only caller of the intent router, the three agents, and the reviewer. The weekly loop has no orchestrator. It calls `reviews.query`, `corpus.search`, and `desk.state` itself, and it reads the signal the orchestrator stored at five repeats. Code guards and the approval gate sit outside the model. `publish` is called only by the approval gate.

**Tech Stack:** Python 3.12+, FastAPI, Jinja2, SQLite, MCP Python SDK, httpx, BeautifulSoup, pytest.

**Spec:** `docs/problemStatement.md` and `docs/architecture.md`. Executors read both. This plan argues from them.

## Global Constraints

- Corpus URLs, character for character, are the twelve in `docs/architecture.md` under "Official corpus". Fetch does not follow links. A citation must be one of those URLs returned by `corpus.search` on that run.
- Reviews path is `data/playstore.csv`. Working rows keep `review_id`, redacted `content`, `created_at`, `score`, `created_at_ist`, `thumbs_up`, `app_version`. `user_name`, `developer_reply`, and `developer_replied_at` are never inserted.
- Pulse window for this file is `2026-11-01T00:09:09+08:00` through `2026-11-11T11:29:18+08:00`. Every count states that window.
- Reply drafts are at most three sentences. The pulse is at most 250 words. The explainer is at most six bullets. Each explainer has two corpus links and a `last_checked` date copied from the chunks.
- `advice`, `performance`, and `pii` replies are the fixed strings in `desk/intent.py`. The model does not paraphrase them.
- The word "sell" inside "per sell transaction" is a fee fact from the DP article. The scope guard flags recommendation phrasing (`should i buy`, `should i sell`, `buy this`, `sell your`) and performance phrasing (`cagr`, `nav`, `returns`, `how much will i make`). It does not flag the phrase `per sell transaction`.
- Scheme-page chunks are stored only after return, CAGR, NAV, and percent-performance figures are removed.
- `topic.unknown` is stored on the queue item and never creates a recurring support signal.
- A recurring support signal at count 5 carries topic, count, window, queue item ids, and a confusion summary of at most two sentences. A fee topic also carries the fee confusion analysis on that same row. A review theme does not own a fee-confusion record.
- A fee theme with no recurring support signal stays a theme and does not open an explainer.
- The weekly job opens three pending actions, because approving one action must not trigger another: `append_doc` (pulse), `email_draft` (same pulse text), `promote_explainer` (the explainer on the fee signal). There is no send-mail tool.
- PII patterns: PAN `[A-Z]{5}[0-9]{4}[A-Z]`, Indian mobile `(?:\+91[\s-]?)?[6-9]\d{9}`, and digit runs of length 10 through 18. Replacements are `[PAN]`, `[PHONE]`, `[ACCOUNT]`. `pii` intent omits question text from traces.
- Logs, SQLite, traces, and HTML contain no raw PAN, phone, account number, or `user_name`.
- The orchestrator is the only entry of the response loop. On `advice`, `performance`, or `pii` it does not call `corpus.search`, `reviews.query`, or `desk.state` for the reply body. On a factual question the official agent calls `corpus.search`, the reviews agent calls `reviews.query`, and the canonical agent calls `desk.state`. The reviewer calls `desk.state` `put_draft`. At five repeats the orchestrator calls `desk.state` `put_signal`.
- The weekly loop does not call the orchestrator, the intent router, the three agents, or the reviewer.

## Review Focus

These are the inputs most likely to pass a happy-path build and still break the brief. Each one has a test on the task that owns the code.

- Five questions the topic list cannot name (`topic.unknown`) must not create a signal or a pulse block. Owned by Task 8.
- Approving the pulse doc must not write the email draft and must not mark the explainer canonical. Owned by Task 7.
- "What is the NAV of SBI Large Cap?" must be the performance refusal even though that scheme page is in the corpus. Owned by Task 9.
- Editing a reused draft must change only that draft body. The canonical explainer text stays byte-for-byte. Owned by Task 10.
- A Play Store `user_name`, and a PAN typed into a review or a question, must be absent from SQLite and from the trace file. Owned by Task 5 and Task 2.

## File map

| File | Responsibility |
| --- | --- |
| `requirements.txt` | Runtime and test dependencies |
| `desk/db.py` | Connection and schema |
| `desk/guards.py` | Redaction, scope, length |
| `desk/intent.py` | Closed intents and fixed refusals |
| `desk/topics.py` | Topic ids from corpus text |
| `desk/corpus.py` | Twelve-page build, performance strip, search |
| `desk/reviews.py` | CSV ingest and review query |
| `desk/approval.py` | Propose, decide, execute one action |
| `desk/publish.py` | Doc append and email draft, approval required |
| `desk/recurrence.py` | Count, confusion summary, signal |
| `desk/response.py` | `orchestrate` first, then the intent router, the guards, the three agents, and the reviewer |
| `desk/weekly.py` | Ingest, themes, fee analysis on the signal, pulse, three actions. No orchestrator |
| `desk/app.py` | FastAPI pages |
| `desk/templates/*.html` | Queue, pulse, sources, approval, explainers |
| `tests/test_*.py` | One file per task |
| `fixtures/pages/*.html` | Offline corpus pages for tests |
| `README.md` | Architecture, setup, sources, gate, link, evals, limits |

Tests use a temp SQLite file and `fixtures/pages`. They do not call Groww or a live model. `ModelClient` is a protocol. Tests pass `ScriptedModel`.

## Call flow

This is the order in `docs/architecture.md`. Implement it in Task 9 and Task 11.

**Response loop.** The queue calls `orchestrate`.

1. `orchestrate` calls the intent router. No MCP call.
2. `orchestrate` calls the guards to redact. No MCP call. A refusal uses `REFUSALS` and skips the agents.
3. For a factual question, `orchestrate` calls the three agents in parallel. The official agent calls `corpus.search`. The reviews agent calls `reviews.query`. The canonical agent calls `desk.state` for `explainers` and `recurrence`. Each result returns to `orchestrate`.
4. `orchestrate` merges in order: canonical `reply_text`, then a grounded official answer, then not covered with the `corpus.search` queries.
5. `orchestrate` attaches the routing note from the reviews result.
6. The reviewer calls the guards, then `desk.state` `put_draft`. The queue reads that row.
7. At five repeats of a real topic, `orchestrate` calls `desk.state` `put_signal`. It does not call `publish`.

**Weekly loop.** The trigger calls `run_weekly` directly.

1. `run_weekly` calls the guards to redact the CSV, then `reviews.query`, then `desk.state` to read signals, then `corpus.search` when a fee signal needs an explainer.
2. It writes themes, the fee confusion analysis, the explainer, and the pulse through `desk.state`.
3. It calls `propose` for `append_doc`, `email_draft`, and `promote_explainer`. It does not call `execute` or `publish`.

```python
class ModelClient(Protocol):
    def complete(self, prompt: str) -> str: ...
```

---

### Task 1: Schema

**Files:**
- Create: `requirements.txt`
- Create: `desk/__init__.py`
- Create: `desk/db.py`
- Create: `tests/conftest.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing
- Produces: `init_db(conn) -> None`, `connect(path: str) -> sqlite3.Connection`. Tables: `corpus_chunks`, `reviews`, `queue_items`, `drafts`, `recurrence`, `themes`, `pulses`, `explainers`, `approval_actions`, `audit_log`, `traces`.

- [ ] **Step 1: Write the failing test**

```python
import sqlite3
from desk.db import init_db

def test_schema_has_the_link_tables():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"corpus_chunks", "reviews", "queue_items", "drafts", "recurrence", "themes", "pulses", "explainers", "approval_actions", "audit_log", "traces"} <= names
    cols = {row[1] for row in conn.execute("PRAGMA table_info(recurrence)")}
    assert {"topic", "count", "window_start", "window_end", "item_ids", "confusion_summary", "fee_confusion_analysis"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_schema_has_the_link_tables -v`
Expected: FAIL with `ModuleNotFoundError: desk`

- [ ] **Step 3: Write minimal implementation**

`requirements.txt`:

```text
fastapi
uvicorn
jinja2
mcp
httpx
beautifulsoup4
pytest
```

`desk/db.py` creates the tables in Global Constraints. `recurrence.fee_confusion_analysis` is nullable JSON text. `explainers` has `signal_id`, `bullets`, `url_a`, `url_b`, `last_checked`, `reply_text`, `status`. `approval_actions.kind` is unconstrained text at the schema layer. `reviews` has no `user_name` column. `tests/conftest.py` provides a `conn` fixture that calls `init_db` on an in-memory connection and `build_corpus` with the Task 4 pages, a `topics` fixture from `extract_charge_topics("Brokerage\nDP charges\n")` plus withdraw and demat topics, and a `csv_path` fixture writing three reviews whose content is `DP charges were taken on a sell` and whose dates sit inside the window. Task 4 creates `build_corpus` before this fixture is used. Until Task 4 lands, `conftest.py` only opens `init_db`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py::test_schema_has_the_link_tables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt desk/__init__.py desk/db.py tests/conftest.py tests/test_db.py
git commit -m "Add the Support Desk SQLite schema."
```

### Task 2: Guards

**Files:**
- Create: `desk/guards.py`
- Test: `tests/test_guards.py`

**Interfaces:**
- Consumes: nothing
- Produces: `redact(text: str) -> str`, `scope_flag(text: str) -> str | None`, `sentence_count(text: str) -> int`, `word_count(text: str) -> int`, `bullet_count(text: str) -> int`

- [ ] **Step 1: Write the failing test**

```python
from desk.guards import bullet_count, redact, scope_flag, sentence_count, word_count

def test_redact_pan_phone_and_account():
    raw = "PAN ABCDE1234F phone 9876543210 account 1234567890123456"
    cleaned = redact(raw)
    assert "ABCDE1234F" not in cleaned
    assert "9876543210" not in cleaned
    assert "1234567890123456" not in cleaned
    assert "[PAN]" in cleaned and "[PHONE]" in cleaned and "[ACCOUNT]" in cleaned

def test_scope_allows_dp_sell_transaction_and_flags_advice():
    assert scope_flag("DP charges apply per sell transaction.") is None
    assert scope_flag("You should sell this fund.") == "scope"
    assert scope_flag("What is the NAV?") == "scope"

def test_caps():
    assert sentence_count("One. Two. Three.") == 3
    assert word_count("one two three") == 3
    assert bullet_count("- a\n- b\n- c") == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guards.py -v`
Expected: FAIL with `ModuleNotFoundError: desk.guards`

- [ ] **Step 3: Write minimal implementation**

`redact` applies the three patterns in Global Constraints, case-sensitive for PAN. `scope_flag` returns `"scope"` when the lowercased text matches `should i buy`, `should i sell`, `buy this`, `sell your`, `cagr`, `nav`, `returns`, or `how much will i make`. `per sell transaction` is not in that list. Sentences split on `[.!?]` after stripping whitespace. Words split on whitespace. Bullets are lines that start with `- `.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_guards.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/guards.py tests/test_guards.py
git commit -m "Enforce redaction, scope, and length in code."
```

### Task 3: Intent and topics

**Files:**
- Create: `desk/intent.py`
- Create: `desk/topics.py`
- Test: `tests/test_intent.py`

**Interfaces:**
- Consumes: `scope_flag` is not required here. Intent is lexical and runs before agents.
- Produces: `classify_intent(text: str) -> str` returning `pii`, `advice`, `performance`, or `factual`. `REFUSALS: dict[str, str]` with those three keys. `Topic(id: str, label: str)`. `assign_topic(text: str, topics: list[Topic]) -> str`. `extract_charge_topics(pricing_text: str) -> list[Topic]`.

- [ ] **Step 1: Write the failing test**

```python
from desk.intent import REFUSALS, classify_intent
from desk.topics import Topic, assign_topic, extract_charge_topics

def test_intent_order_pii_before_performance():
    assert classify_intent("My PAN is ABCDE1234F, what is the NAV?") == "pii"
    assert classify_intent("Should I buy SBI Large Cap?") == "advice"
    assert classify_intent("What is the CAGR of this fund?") == "performance"
    assert classify_intent("When are DP charges levied?") == "factual"
    assert REFUSALS["performance"].startswith("This desk states")
    assert "NAV" not in REFUSALS["performance"]

def test_topics_come_from_pricing_text_and_unknown_stays_unknown():
    topics = extract_charge_topics("Brokerage\nDP charges\n")
    topics += [Topic("payments.withdraw", "withdrawal"), Topic("account.demat", "demat")]
    assert assign_topic("Why was DP charged?", topics) == "fees.dp"
    assert assign_topic("How do I withdraw?", topics) == "payments.withdraw"
    assert assign_topic("The app logo is blue", topics) == "topic.unknown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intent.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`classify_intent` checks PAN, phone, and 10–18 digit runs first, then advice phrases, then performance phrases, else `factual`. `REFUSALS["advice"]` is `This desk states published Groww facts and does not recommend buying, selling, or holding.` `REFUSALS["performance"]` is `This desk states published Groww facts and does not give returns, NAV, or performance figures.` `REFUSALS["pii"]` is `This desk cannot take a PAN, phone number, or account number. Remove it and ask the question again.`

`extract_charge_topics` emits `Topic("fees." + slug, label)` for each non-empty line. The slug for `DP charges` is `dp`. Other lines slugify to lowercase words joined by `_`. `assign_topic` checks `fees.dp` when the text contains `dp charge` or `depository`, then other topic labels as case-insensitive substrings, else `topic.unknown`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/intent.py desk/topics.py tests/test_intent.py
git commit -m "Classify intent and topic before any agent runs."
```

### Task 4: Corpus build

**Files:**
- Create: `desk/corpus.py`
- Create: `fixtures/pages/pricing.html`
- Create: `fixtures/pages/dp.html`
- Create: `fixtures/pages/scheme.html`
- Test: `tests/test_corpus.py`

**Interfaces:**
- Consumes: `init_db`, `extract_charge_topics`
- Produces: `CORPUS_URLS: tuple[str, ...]`, `strip_performance(text: str) -> str`, `build_corpus(conn, pages: list[tuple[str, str]], fetched_on: str) -> None`, `search(conn, query: str) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
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
    hits = search(conn, "DP charges levied")
    assert hits and hits[0]["url"] == DP_URL
    assert hits[0]["last_checked"] == "2026-11-13"
    assert strip_performance("NAV 10") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_corpus.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`CORPUS_URLS` is the twelve URLs from the architecture table, in that order. `build_corpus` parses HTML with BeautifulSoup, gets visible text, and for any URL containing `/mutual-funds/` runs `strip_performance` first. `strip_performance` drops sentences containing `cagr`, `nav`, `return`, or a percent figure. Insert one chunk per page with the source URL unchanged, title from the first `h1` or the first line, topic id from `assign_topic` on the page text, and `last_checked`. Also insert a `topics` use at search time by storing `topic_id` on the chunk. `search` keeps chunks whose text contains every word of the query longer than two characters, and returns `id`, `url`, `title`, `text`, `last_checked`. It never fetches the network.

Save the three HTML strings above as the fixture files so later tasks load them from disk.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_corpus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/corpus.py fixtures/pages tests/test_corpus.py
git commit -m "Build the twelve-page corpus without performance figures."
```

### Task 5: Review ingest

**Files:**
- Create: `desk/reviews.py`
- Test: `tests/test_reviews.py`

**Interfaces:**
- Consumes: `init_db`, `redact`
- Produces: `WINDOW_START`, `WINDOW_END`, `ingest_reviews(conn, csv_path: str) -> dict`, `query_reviews(conn, window_start: str, window_end: str) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3
from pathlib import Path
from desk.db import init_db
from desk.reviews import WINDOW_END, WINDOW_START, ingest_reviews

def test_ingest_drops_name_and_redacts_pan(tmp_path: Path):
    csv_path = tmp_path / "reviews.csv"
    csv_path.write_text(
        "review_id,created_at,created_at_ist,score,thumbs_up,app_version,user_name,content,developer_reply,developer_replied_at\n"
        "r1,2026-11-02T10:00:00+08:00,2026-11-02T07:30:00+05:30,1,0,18.22.1,Priya Shah,DP charge on PAN ABCDE1234F,thanks,2026-11-02T11:00:00+08:00\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    ingest_reviews(conn, str(csv_path))
    row = conn.execute("SELECT review_id, content FROM reviews").fetchone()
    assert row[0] == "r1"
    assert "ABCDE1234F" not in row[1] and "[PAN]" in row[1]
    blob = " ".join("".join(map(str, r)) for r in conn.execute("SELECT * FROM reviews"))
    assert "Priya Shah" not in blob and "thanks" not in blob
    assert WINDOW_START == "2026-11-01T00:09:09+08:00"
    assert WINDOW_END == "2026-11-11T11:29:18+08:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reviews.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`ingest_reviews` reads the CSV with `csv.DictReader`, redacts `content`, and inserts `review_id`, redacted content, `created_at`, `score`, `created_at_ist`, `thumbs_up`, `app_version`, and a sha256 of the file bytes. It does not bind `user_name`, `developer_reply`, or `developer_replied_at`. `query_reviews` returns rows with `created_at` inside the inclusive window as `{id, quote, date}` where `quote` is `content` and `date` is `created_at`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reviews.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/reviews.py tests/test_reviews.py
git commit -m "Ingest reviews without display names or Play Store replies."
```

### Task 6: Read tools stay inside the stores

**Files:**
- Create: `desk/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `search`, `query_reviews`
- Produces: `corpus_search(conn, query: str) -> list[dict]`, `reviews_query(conn, window_start: str, window_end: str) -> list[dict]`. Both refuse a caller-supplied URL.

- [ ] **Step 1: Write the failing test**

```python
def test_corpus_search_rejects_a_caller_url(conn):
    import pytest
    from desk.tools import corpus_search
    with pytest.raises(ValueError):
        corpus_search(conn, "https://example.com/blog")
```

`conn` is a fixture that calls `init_db` and `build_corpus` with the Task 4 pages.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py::test_corpus_search_rejects_a_caller_url -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

If the query starts with `http://` or `https://`, raise `ValueError`. Otherwise call `search` or `query_reviews`. Register these two functions as MCP tools named `corpus.search` and `reviews.query` in `desk/mcp_server.py` only after this test passes. The tool wrappers call the same functions.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/tools.py desk/mcp_server.py tests/test_tools.py
git commit -m "Search the stored corpus and reviews only."
```

### Task 7: Approval gate

**Files:**
- Create: `desk/approval.py`
- Create: `desk/publish.py`
- Test: `tests/test_approval.py`

**Interfaces:**
- Consumes: `init_db`
- Produces: `propose(conn, kind: str, destination: str, payload: str) -> str`, `decide(conn, action_id: str, status: str) -> None`, `execute(conn, action_id: str, sink: dict) -> str`. `sink` has keys `doc`, `mailbox`, and `canonical`, each a `list[str]`. Returns the kind that ran. `publish.email_draft(conn, action_id, sink) -> None` raises `PermissionError` unless that action is approved.

- [ ] **Step 1: Write the failing test**

```python
def test_approving_the_pulse_does_not_write_mail_or_promote(conn):
    from desk.approval import decide, execute, propose
    doc, mail = propose(conn, "append_doc", "pulse.md", "Pulse body"), propose(conn, "email_draft", "product@groww", "Pulse body")
    explainer = propose(conn, "promote_explainer", "fees.dp", "explainer-id")
    decide(conn, doc, "approved")
    sink = {"doc": [], "mailbox": [], "canonical": []}
    assert execute(conn, doc, sink) == "append_doc"
    assert sink["doc"] == ["Pulse body"]
    assert sink["mailbox"] == []
    assert sink["canonical"] == []
    status = conn.execute("SELECT status FROM approval_actions WHERE id = ?", (mail,)).fetchone()[0]
    assert status == "pending"
    assert conn.execute("SELECT status FROM approval_actions WHERE id = ?", (explainer,)).fetchone()[0] == "pending"

def test_pending_email_is_refused(conn):
    import pytest
    from desk.approval import propose
    from desk.publish import email_draft
    action_id = propose(conn, "email_draft", "product@groww", "Pulse body")
    with pytest.raises(PermissionError):
        email_draft(conn, action_id, {"doc": [], "mailbox": [], "canonical": []})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_approval.py::test_approving_the_pulse_does_not_write_mail_or_promote -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`propose` inserts a row with `status='pending'` and `payload_hash = sha256(payload)`. `decide` sets `approved` or `rejected` and writes an audit row. `execute` loads that one id. It returns without writing when status is not `approved` or the hash differs. `append_doc` appends `payload` to `sink["doc"]` and sets `executed`. `email_draft` appends to `sink["mailbox"]`. `promote_explainer` appends the payload to `sink["canonical"]`. A second `execute` on an `executed` row writes an audit no-op and does not append again. `publish.append_doc` and `publish.email_draft` call `execute` and are the only writers. `email_draft` raises `PermissionError` when the row is pending, rejected, or the hash differs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_approval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/approval.py desk/publish.py tests/test_approval.py
git commit -m "Execute one approved action and leave the others waiting."
```

### Task 8: Recurring support signal

**Files:**
- Create: `desk/recurrence.py`
- Test: `tests/test_recurrence.py`

**Interfaces:**
- Consumes: `init_db`, `sentence_count`
- Produces: `record(conn, item_id: str, intent: str, topic: str, question: str, window_start: str, window_end: str) -> dict | None`. Returns the signal dict once `count >= 5`, else `None`. `confusion_summary(topic: str, questions: list[str]) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from desk.guards import sentence_count
from desk.recurrence import confusion_summary, record

def test_five_unknown_questions_do_not_signal(conn):
    for i in range(5):
        assert record(conn, f"u{i}", "factual", "topic.unknown", "hello", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00") is None
    assert conn.execute("SELECT COUNT(*) FROM recurrence").fetchone()[0] == 0

def test_fifth_fee_question_stores_a_two_sentence_summary(conn):
    signal = None
    for i in range(5):
        signal = record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    assert signal is not None
    assert signal["count"] == 5
    assert signal["item_ids"] == ["q0", "q1", "q2", "q3", "q4"]
    assert sentence_count(signal["confusion_summary"]) <= 2
    assert "DP" in signal["confusion_summary"]
    assert confusion_summary("fees.dp", ["When are DP charges levied?" * 1]).count(".") <= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recurrence.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`record` returns `None` immediately when `topic == "topic.unknown"` and does not insert. Otherwise it upserts the row for `(intent, topic, window_start, window_end)`, appends `item_id`, increments `count`, and rebuilds `confusion_summary`. The summary is two sentences: `Questions on {topic} are asking the same thing in this window.` and `They ask: {first question trimmed to 80 characters}.` `record` returns the row dict only when count is at least 5. It does not call publish.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recurrence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/recurrence.py tests/test_recurrence.py
git commit -m "Write a support signal at five repeats, with a confusion summary."
```

### Task 9: Response loop

**Files:**
- Create: `desk/response.py`
- Test: `tests/test_response.py`

**Interfaces:**
- Consumes: `classify_intent`, `REFUSALS`, `assign_topic`, `corpus_search`, `reviews_query`, `record`, `redact`, `scope_flag`, `sentence_count`
- Produces: `handle_question(conn, question: str, model: ModelClient, topics: list) -> dict`, which only inserts the queue row and calls `orchestrate`. Return keys: `queue_id`, `draft_id`, `intent`, `topic`, `body`, `citation_url`, `routing_note`, `flags`, `outcome`, `reused_explainer_id`.

`ScriptedModel.complete` returns the string `GROUNDED::{url}::{sentence}` when the prompt contains a retrieved URL, and `NOT_COVERED` otherwise. The official agent may use that string only when `url` is in the search hits.

- [ ] **Step 1: Write the failing test**

```python
def test_nav_question_is_the_fixed_refusal_and_does_not_call_the_model(conn, topics):
    from desk.intent import REFUSALS
    from desk.response import handle_question
    from tests.fakes import ScriptedModel
    model = ScriptedModel()
    result = handle_question(conn, "What is the NAV of SBI Large Cap?", model, topics)
    assert result["intent"] == "performance"
    assert result["body"] == REFUSALS["performance"]
    assert result["outcome"] == "refusal"
    assert model.calls == 0
    stored = conn.execute("SELECT question FROM queue_items").fetchone()[0]
    assert "NAV" in stored  # performance text is not PII and is kept
    pan = handle_question(conn, "PAN ABCDE1234F where is my demat?", ScriptedModel(), topics)
    assert pan["body"] == REFUSALS["pii"]
    assert "ABCDE1234F" not in conn.execute("SELECT question FROM queue_items WHERE id = ?", (pan["queue_id"],)).fetchone()[0]
    trace = conn.execute("SELECT text FROM traces WHERE event_id = ?", (pan["queue_id"],)).fetchone()[0]
    assert trace is None

def test_not_covered_names_the_query(conn, topics):
    from desk.response import handle_question
    result = handle_question(conn, "What is the weather on Mars?", ScriptedModel(), topics)
    assert "not covered" in result["body"].lower()
    assert "weather" in result["body"].lower()

def test_grounded_draft_uses_only_a_returned_url(conn, topics):
    from desk.guards import sentence_count
    from desk.response import handle_question
    result = handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    assert result["citation_url"] == DP_URL
    assert sentence_count(result["body"]) <= 3
    assert "ungrounded" not in result["flags"]
```

`DP_URL` is the constant from Task 4. `ScriptedModel` lives in `tests/fakes.py`:

```python
class ScriptedModel:
    def __init__(self):
        self.calls = 0
    def complete(self, prompt: str) -> str:
        self.calls += 1
        if "http" in prompt:
            url = [part for part in prompt.split() if part.startswith("http")][0]
            return f"GROUNDED::{url}::DP charges apply per sell transaction."
        return "NOT_COVERED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_response.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`handle_question` inserts the queue row and calls `orchestrate`. `orchestrate` is the only function that starts the response loop. Follow the call flow above.

1. Call `classify_intent` and `assign_topic`. Do not call MCP.
2. Call `redact`. For `advice`, `performance`, or `pii`, set the body to `REFUSALS[intent]`, skip the agents, and store a `pii` trace with `text` NULL. Do not call `corpus_search`, `reviews_query`, or `record` for the reply body.
3. For a factual question, run these three functions in parallel. Do not pass one function's output into the next.
   - `official_agent` calls `corpus_search`, then `model.complete`. It accepts a `GROUNDED` URL only when that URL is in the hits. Otherwise the note is `Not covered. Searched: {query}. Pages: {titles}.`
   - `reviews_agent` calls `reviews_query` for the file window and returns ids, quotes, and the window for the routing note. It does not call the model.
   - `canonical_agent` calls the explainer and recurrence reads on `desk.state`. On a canonical hit it returns `reply_text` and the explainer id. It does not call the model.
4. Merge in order: canonical `reply_text` with `reused_explainer_id`, then the grounded official answer and its one URL, then not covered with the `corpus_search` queries.
5. Attach the routing note: theme, review ids, window, recurrence count, and whether an explainer was reused.
6. The reviewer calls `scope_flag` and `sentence_count`, sets `ungrounded` when the citation is missing from the hits, then writes the draft with `put_draft`.
7. Call `record` from `orchestrate` after the draft is stored. `record` is `desk.state` `put_signal`. It writes a signal only at five repeats of a real topic. It does not call `publish`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_response.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/response.py tests/fakes.py tests/test_response.py
git commit -m "Answer each question with a cited draft or a fixed refusal."
```

### Task 10: Draft edit, approve, reject

**Files:**
- Modify: `desk/response.py`
- Test: `tests/test_draft_actions.py`

**Interfaces:**
- Consumes: `handle_question`, `init_db`
- Produces: `edit_draft(conn, draft_id: str, body: str) -> None`, `set_draft_status(conn, draft_id: str, status: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
def test_edit_changes_only_that_draft(conn, topics):
    from desk.response import edit_draft, handle_question, set_draft_status
    a = handle_question(conn, "When are DP charges levied?", ScriptedModel(), topics)
    b = handle_question(conn, "How do I withdraw money?", ScriptedModel(), topics)
    before_b = conn.execute("SELECT body FROM drafts WHERE queue_item_id = ?", (b["queue_id"],)).fetchone()[0]
    edit_draft(conn, a["draft_id"], "Edited sentence only.")
    assert conn.execute("SELECT body FROM drafts WHERE id = ?", (a["draft_id"],)).fetchone()[0] == "Edited sentence only."
    assert conn.execute("SELECT body FROM drafts WHERE queue_item_id = ?", (b["queue_id"],)).fetchone()[0] == before_b
    set_draft_status(conn, a["draft_id"], "rejected")
    assert conn.execute("SELECT status FROM queue_items WHERE id = ?", (b["queue_id"],)).fetchone()[0] != "rejected"
```

Add `test_edit_does_not_change_canonical_explainer`: insert an explainer row with `reply_text='CANONICAL'`, handle a fee question that reuses it, edit the draft, and assert `reply_text` is still `CANONICAL`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_draft_actions.py -v`
Expected: FAIL because `edit_draft` is missing, or FAIL the canonical assertion if edit rewrites the explainer.

- [ ] **Step 3: Write minimal implementation**

`edit_draft` updates `drafts.body` and `body_hash` for that id and writes one audit row. It does not update `explainers`, `recurrence`, or other drafts. `set_draft_status` sets that draft and its queue item to `approved` or `rejected` and writes one audit row. `handle_question` must return `draft_id`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_draft_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/response.py tests/test_draft_actions.py
git commit -m "Keep an edit, an approval, and a rejection on one draft."
```

### Task 11: Weekly loop

**Files:**
- Create: `desk/weekly.py`
- Test: `tests/test_weekly.py`
- Test: `tests/fixtures.py` if the corpus fixture helper is shared

**Interfaces:**
- Consumes: `ingest_reviews`, `assign_topic`, `record` results already in `recurrence`, `corpus_search`, `propose`, `word_count`, `bullet_count`
- Produces: `run_weekly(conn, csv_path: str, topics: list) -> dict` with keys `pulse_id`, `action_ids`, `theme_ids`, `explainer_id`.

- [ ] **Step 1: Write the failing test**

```python
def test_fee_theme_without_a_signal_does_not_open_an_explainer(conn, topics, csv_path):
    from desk.weekly import run_weekly
    result = run_weekly(conn, csv_path, topics)
    assert result["explainer_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM explainers").fetchone()[0] == 0
    themes = conn.execute("SELECT review_ids, window_start, window_end FROM themes").fetchall()
    assert themes
    assert all(row[0] not in ("", "[]") for row in themes)
    assert themes[0][1] == "2026-11-01T00:09:09+08:00"

def test_fee_signal_gets_the_analysis_and_the_pulse_copies_it(conn, topics, csv_path):
    from desk.recurrence import record
    from desk.weekly import run_weekly
    for i in range(5):
        record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    result = run_weekly(conn, csv_path, topics)
    analysis = conn.execute("SELECT fee_confusion_analysis FROM recurrence WHERE topic = 'fees.dp'").fetchone()[0]
    assert analysis and "fees.dp" in analysis
    pulse = conn.execute("SELECT body, word_count FROM pulses").fetchone()
    assert pulse[1] <= 250
    assert "fees.dp" in pulse[0] and "When are DP charges levied?"[:20] in pulse[0]
    bullets = conn.execute("SELECT bullets FROM explainers WHERE id = ?", (result["explainer_id"],)).fetchone()[0]
    assert bullet_count(bullets) <= 6
    kinds = {row[0] for row in conn.execute("SELECT kind FROM approval_actions")}
    assert kinds == {"append_doc", "email_draft", "promote_explainer"}
```

`csv_path` is a temp CSV of three reviews whose content is `DP charges were taken on a sell` and whose dates sit inside the window. The corpus fixture includes the pricing page and the DP article.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_weekly.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`run_weekly` does not call `orchestrate`, `classify_intent`, the three agents, or the reviewer. It calls `ingest_reviews`, sets the window constants, groups reviews by `assign_topic`, ranks groups by size, and keeps at most five themes. Review reads go through `reviews_query`. Explainer chunks go through `corpus_search`. Signals, themes, the pulse, and the explainer go through `desk.state`. The top three are marked `rank` 1–3. Each theme stores review ids, a quote that is a substring of `content`, and the window. Groups of `topic.unknown` may be a theme and never an explainer.

It loads recurrence rows with `count >= 5`, a non-empty `confusion_summary`, and a topic other than `topic.unknown`. For a `fees.*` row it writes `fee_confusion_analysis` JSON: `fee_topic`, `what_is_confused` (the summary plus one quote), `review_ids`, `quotes`, `window`, `corpus_urls` (the DP URL and the pricing URL when both chunks contain `DP`), and later `explainer_id`. The explainer bullets are the first six sentences of those chunks, each line prefixed with `- `. If fewer than two URLs support the text, `flags` on the explainer is `ungrounded` and `url_b` stays empty. `reply_text` is the first three sentences of the bullet text with the `- ` removed. This function does not call `ModelClient`.

The pulse body is assembled in code: a theme section with label, count, window, and quote, then the recurring-support-signals section copied from the signal row including the analysis JSON's `what_is_confused`, then three action lines that name the topic and do not add a fee amount. If `word_count` would exceed 250, shorten the theme quotes, never the signal block. Then `propose` the three actions. Do not `execute` any of them.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_weekly.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/weekly.py tests/test_weekly.py
git commit -m "Build the pulse and attach fee analysis to the support signal."
```

### Task 12: Reuse the approved explainer

**Files:**
- Modify: `desk/response.py`
- Modify: `desk/approval.py`
- Test: `tests/test_reuse.py`

**Interfaces:**
- Consumes: `execute` for `promote_explainer`, `handle_question`
- Produces: `promote_explainer` sets `explainers.status='canonical'` for the id in the payload. The next `handle_question` on that topic copies `reply_text`.

- [ ] **Step 1: Write the failing test**

```python
def test_sixth_question_copies_the_canonical_reply(conn, topics, csv_path):
    from desk.approval import decide, execute
    from desk.recurrence import record
    from desk.response import handle_question
    from desk.weekly import run_weekly
    from tests.fakes import ScriptedModel
    for i in range(5):
        record(conn, f"q{i}", "factual", "fees.dp", "When are DP charges levied?", "2026-11-01T00:09:09+08:00", "2026-11-11T11:29:18+08:00")
    run_weekly(conn, csv_path, topics)
    actions = dict(conn.execute("SELECT kind, id FROM approval_actions"))
    decide(conn, actions["promote_explainer"], "approved")
    execute(conn, actions["promote_explainer"], {"doc": [], "mailbox": [], "canonical": []})
    calls = ScriptedModel()
    sixth = handle_question(conn, "When are DP charges levied again?", calls, topics)
    stored = conn.execute("SELECT reply_text FROM explainers WHERE status = 'canonical'").fetchone()[0]
    assert sixth["body"] == stored
    assert sixth["reused_explainer_id"]
    assert calls.calls == 0
```

`ScriptedModel.calls` increments inside `complete`. The canonical path must not call it.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reuse.py -v`
Expected: FAIL because promote does not set `canonical`, or because the model was called.

- [ ] **Step 3: Write minimal implementation**

`execute` for `promote_explainer` sets that explainer's status to `canonical`. `canonical_agent` returns `reply_text` unchanged. `handle_question` uses it as the body and skips `model.complete`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reuse.py tests/test_response.py tests/test_approval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/response.py desk/approval.py tests/test_reuse.py
git commit -m "Reuse the approved explainer instead of drafting again."
```

### Task 13: Five pages

**Files:**
- Create: `desk/app.py`
- Create: `desk/templates/base.html`
- Create: `desk/templates/queue.html`
- Create: `desk/templates/pulse.html`
- Create: `desk/templates/sources.html`
- Create: `desk/templates/approval.html`
- Create: `desk/templates/explainers.html`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: the store functions from Tasks 9–12
- Produces: `GET /`, `GET /pulse`, `GET /sources`, `GET /approval`, `GET /explainers`, `POST /questions`, `POST /drafts/{id}`, `POST /approval/{id}`

- [ ] **Step 1: Write the failing test**

```python
def test_pages_render_the_signal_and_hide_user_names(client, seeded):
    queue = client.get("/")
    assert queue.status_code == 200
    assert "When are DP charges levied?" in queue.text
    assert "Priya Shah" not in queue.text
    pulse = client.get("/pulse")
    assert "Recurring support signals" in pulse.text
    assert "fees.dp" in pulse.text
    approval = client.get("/approval")
    assert "append_doc" in approval.text and "promote_explainer" in approval.text
    assert "email_draft" in approval.text
```

`seeded` runs the weekly fixture from Task 11. `client` is a FastAPI `TestClient`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pages.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Jinja templates extend `base.html`. Queue shows body, citation, flags, and buttons for edit, approve, and reject. Pulse shows themes with review ids and the window, then a heading `Recurring support signals` and, inside a fee signal, the fee confusion analysis. Sources lists chunk URL, title, and `last_checked` for the citation. Approval lists kind, destination, and the full payload with approve and reject forms. Explainers lists rows where status is `canonical`, both URLs, and the count of drafts with that `reused_explainer_id`. POST handlers call `handle_question`, `edit_draft`, `set_draft_status`, `decide`, and `execute`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/app.py desk/templates tests/test_pages.py
git commit -m "Serve the queue, pulse, sources, approval, and explainer pages."
```

### Task 14: Assembled evals

**Files:**
- Create: `tests/test_evals.py`
- Create: `evals/run_evals.py`

**Interfaces:**
- Consumes: `handle_question`, `run_weekly`, `edit_draft`, `set_draft_status`, `decide`, `execute`
- Produces: `python -m evals.run_evals` exits 0 when the three checks pass against a temp database.

- [ ] **Step 1: Write the failing test**

```python
def test_feasibility_edit_isolation_and_compliance(conn, topics, csv_path):
    questions = [
        "When are DP charges levied?",
        "How do I withdraw money?",
        "Where do I see my demat number?",
        "What is the weather on Mars?",
        "Should I buy SBI Large Cap?",
        "What is the NAV of SBI Flexicap?",
        "My number is 9876543210",
    ]
    for question in questions:
        handle_question(conn, question, ScriptedModel(), topics)
    outcomes = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
    assert outcomes == len(questions)
    run_weekly(conn, csv_path, topics)
    pulse = conn.execute("SELECT word_count FROM pulses").fetchone()[0]
    assert pulse <= 250
```

Extend the same test with the Task 10 edit diff, one approved `append_doc` that leaves `email_draft` pending, and a scan of every table plus `traces.text` for `9876543210`, `ABCDE1234F`, and a fixture display name. `evals/run_evals.py` calls this scenario and prints one line per check.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evals.py -v`
Expected: FAIL until the scan and the draft count both pass. If Task 13 already satisfies it, tighten the scan until a planted PAN in `traces.text` fails, then confirm the implementation stores NULL.

- [ ] **Step 3: Write minimal implementation**

`evals/run_evals.py` builds a temp database, loads `fixtures/pages`, runs the questions above plus four rephrases of the advice, performance, and phone questions, runs `run_weekly`, and checks the three brief headings: feasibility, correctness of edits, grounding and compliance. Grounding samples claims by reading draft citations and theme review ids and resolving each to a `corpus_chunks.url` or a `reviews.review_id`. Exit code is 1 when any check fails.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_evals.py evals/run_evals.py
git commit -m "Run feasibility, edit, and compliance checks on the assembled system."
```

### Task 15: README and local run

**Files:**
- Create: `README.md`
- Create: `desk/__main__.py`

**Interfaces:**
- Consumes: `app`, `build_corpus`, `run_weekly`
- Produces: `python -m desk` serves the app. `python -m desk.build_corpus` fetches the twelve URLs once. `python -m evals.run_evals` runs the checks.

- [ ] **Step 1: Write the failing test**

```python
def test_readme_covers_the_submission_points():
    text = open("README.md", encoding="utf-8").read().lower()
    for needle in ("approval", "recurring support", "fee confusion", "playstore.csv", "evals", "twelve", "known limit"):
        assert needle in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_readme.py::test_readme_covers_the_submission_points -v`
Expected: FAIL because `README.md` is missing

- [ ] **Step 3: Write minimal implementation**

`README.md` covers setup, the twelve source URLs, where the approval gate sits (`desk/approval.py`, three action kinds), how the loops connect (five repeats write the signal, the weekly job nests fee confusion analysis on that signal, approving `promote_explainer` makes `reply_text` canonical), the reviews path and window, how to run evals, and the known limits: English India reviews only, no 12 November rows, scheme performance figures are stripped, email is a draft. `__main__.py` starts uvicorn on `desk.app:app`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_readme.py tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md desk/__main__.py tests/test_readme.py
git commit -m "Document setup, the gate, the link, and the evals."
```

## Spec coverage

| Requirement | Task |
| --- | --- |
| Twelve-page corpus, no extra links, performance stripped | 4 |
| `data/playstore.csv` ingest, names and developer replies dropped | 5 |
| Weekly themes, ids, window, 250 words, top three of at most five | 11 |
| Fee explainer, six bullets, two links, last checked | 11 |
| Fee confusion analysis inside the recurring support signal | 8, 11 |
| Response loop starts at the orchestrator; weekly loop does not | 9, 11 |
| Five repeats appear in the pulse with a confusion summary | 8, 11 |
| Approved explainer reused, model not called again | 12 |
| Facts-only, refusals, PII redaction in code | 2, 3, 9 |
| One approval, one action, including email separate from the doc | 7, 11 |
| Five interface views | 13 |
| Feasibility, edit diffs, grounding and compliance | 14 |
| README submission points | 15 |

## Known limits to leave in the README

- The checked-in reviews are the English India feed through 11 November 2026. Hindi reviews are not in the file.
- Clustering is by corpus topic, so two wordings of DP charges share `fees.dp`. That is the "same question" key.
- A fee mentioned only in reviews, with fewer than five support questions, is a theme and not an explainer.
- The live corpus build needs network access. Tests use `fixtures/pages`.
