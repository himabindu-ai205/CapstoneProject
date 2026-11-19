import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_chunks (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    topic_id TEXT,
    text TEXT NOT NULL,
    last_checked TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    score INTEGER,
    created_at_ist TEXT,
    thumbs_up INTEGER,
    app_version TEXT,
    source_file_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_items (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    intent TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    queue_item_id TEXT NOT NULL,
    body TEXT NOT NULL,
    citation_url TEXT,
    routing_note TEXT,
    flags TEXT,
    reused_explainer_id TEXT,
    body_hash TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recurrence (
    id TEXT PRIMARY KEY,
    intent TEXT NOT NULL,
    topic TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    count INTEGER NOT NULL,
    item_ids TEXT NOT NULL,
    confusion_summary TEXT,
    fee_confusion_analysis TEXT
);

CREATE TABLE IF NOT EXISTS themes (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    topic_id TEXT,
    review_ids TEXT NOT NULL,
    quotes TEXT,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    rank INTEGER,
    pulse_id TEXT
);

CREATE TABLE IF NOT EXISTS pulses (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    model_id TEXT,
    signals_block TEXT,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS explainers (
    id TEXT PRIMARY KEY,
    signal_id TEXT,
    topic TEXT NOT NULL,
    bullets TEXT NOT NULL,
    url_a TEXT,
    url_b TEXT,
    last_checked TEXT,
    reply_text TEXT,
    status TEXT NOT NULL,
    flags TEXT
);

CREATE TABLE IF NOT EXISTS approval_actions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    destination TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_hash TEXT,
    after_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    intent TEXT,
    tool_names TEXT,
    text TEXT
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
