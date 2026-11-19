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


def strip_performance(text: str) -> str:
    kept = []
    for part in re.split(r"[.!?]", text):
        sentence = part.strip()
        if not sentence:
            continue
        lowered = sentence.lower()
        if "cagr" in lowered or "nav" in lowered or "return" in lowered:
            continue
        if _PERCENT.search(sentence):
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
    words = [word.lower() for word in re.findall(r"[A-Za-z0-9]+", query) if len(word) > 2]
    hits = []
    rows = conn.execute(
        "SELECT id, url, title, text, last_checked FROM corpus_chunks ORDER BY id"
    )
    for row in rows:
        text = row[3]
        if all(word in text.lower() for word in words):
            hits.append(
                {
                    "id": row[0],
                    "url": row[1],
                    "title": row[2],
                    "text": text,
                    "last_checked": row[4],
                }
            )
    return hits


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
