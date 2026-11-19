from mcp.server.fastmcp import FastMCP

from desk.db import connect, init_db
from desk.tools import corpus_search, reviews_query

mcp = FastMCP("support-desk")
DB_PATH = "data/desk.sqlite"


def _connection():
    conn = connect(DB_PATH)
    init_db(conn)
    return conn


@mcp.tool(name="corpus.search")
def corpus_search_tool(query: str) -> list[dict]:
    conn = _connection()
    try:
        return corpus_search(conn, query)
    finally:
        conn.close()


@mcp.tool(name="reviews.query")
def reviews_query_tool(window_start: str, window_end: str) -> list[dict]:
    conn = _connection()
    try:
        return reviews_query(conn, window_start, window_end)
    finally:
        conn.close()
