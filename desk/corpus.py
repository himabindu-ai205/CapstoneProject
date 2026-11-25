import re
import sqlite3

from bs4 import BeautifulSoup

from desk.topics import assign_topic, extract_charge_topics

CORPUS_URLS = (
    "https://groww.in/pricing",
    "https://groww.in/help",
    "https://groww.in/help/mutual-funds",
    "https://groww.in/help/payments",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied",
    "https://groww.in/help/my-account/payments/how-do-i-withdraw-money-from-my-groww-account-2",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/sx-demat-account/where-can-i-see-my-demat-account-number",
    "https://groww.in/mutual-funds/sbi-large-cap-direct-plan-growth",
    "https://groww.in/mutual-funds/sbi-flexicap-fund-direct-growth",
    "https://groww.in/mutual-funds/sbi-elss-tax-saver-fund-direct-growth",
    "https://groww.in/mutual-funds/sbi-contra-fund-direct-growth",
    "https://groww.in/mutual-funds/sbi-small-midcap-fund-direct-growth",
)

_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_STOP = frozenset(
    """
    how much the what is are for per and of does do can you your when where which
    this that with from was were who why will about into than then them they our not
    in on to it be or an at by if up as am we me my no so
    """.split()
)


def content_words(query: str) -> list[str]:
    return [
        word.lower()
        for word in re.findall(r"[A-Za-z0-9]+", query)
        if len(word) > 1 and word.lower() not in _STOP
    ]


def strip_performance(text: str) -> str:
    kept = []
    pieces = re.split(r"[\n]+|(?<!\d)[.!?](?:\s|$)|(?<=\d)[.!?](?=\s|$)", text)
    for part in pieces:
        sentence = part.strip()
        if not sentence:
            continue
        lowered = sentence.lower()
        if "cagr" in lowered or "nav" in lowered or "return" in lowered:
            continue
        if _PERCENT.search(sentence):
            previous = kept[-1].lower() if kept else ""
            labeled = "expense" in lowered or "exit load" in lowered
            follows_label = previous in {"expense ratio", "exit load"} or previous.startswith("exit load")
            if labeled or follows_label:
                kept.append(sentence)
            continue
        kept.append(sentence)
    if not kept:
        return ""
    return ". ".join(kept) + "."


def build_corpus(conn: sqlite3.Connection, pages: list[tuple[str, str]], fetched_on: str) -> None:
    parsed = [(url, html, _page_text(url, html)) for url, html in pages]
    topics = []
    for url, html, _text in parsed:
        if url.rstrip("/") == "https://groww.in/pricing":
            topics.extend(extract_charge_topics(_charge_text(html)))
    for url, html, text in parsed:
        conn.execute(
            "INSERT INTO corpus_chunks (url, title, topic_id, text, last_checked) VALUES (?, ?, ?, ?, ?)",
            (url, _title(html, text), assign_topic(text, topics), text, fetched_on),
        )
    conn.commit()


def search(conn: sqlite3.Connection, query: str) -> list[dict]:
    words = content_words(query)
    if not words:
        return []
    rows = list(
        conn.execute(
            "SELECT id, url, title, text, last_checked FROM corpus_chunks ORDER BY id"
        )
    )
    docs = [(f"{row[1]} {row[2]}".lower(), f"{row[1]} {row[2]} {row[3]}".lower(), row) for row in rows]
    idf = {}
    for word in words:
        found = sum(1 for _title, doc, _row in docs if word in doc)
        idf[word] = 1 / found if found else 0
    scored = []
    for title, doc, row in docs:
        present = [word for word in words if word in doc]
        if not present:
            continue
        score = sum(idf[word] for word in present)
        score += sum(1 for word in present if word in title)
        scored.append((score, len(row[3]), row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "id": row[0],
            "url": row[1],
            "title": row[2],
            "text": row[3],
            "last_checked": row[4],
        }
        for _score, _length, row in scored[:3]
    ]


def _page_text(url: str, html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    if "/mutual-funds/" in url:
        return strip_performance(text)
    return text


def _charge_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    lines = [node.get_text(" ", strip=True) for node in soup.find_all("p")]
    if lines:
        return "\n".join(lines)
    return soup.get_text("\n", strip=True)


def _title(html: str, text: str) -> str:
    heading = BeautifulSoup(html, "html.parser").find("h1")
    if heading is not None:
        title = heading.get_text(" ", strip=True)
        if title:
            return title
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
