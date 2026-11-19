def test_corpus_search_rejects_a_caller_url(conn):
    import pytest
    from desk.tools import corpus_search

    with pytest.raises(ValueError):
        corpus_search(conn, "https://example.com/blog")
