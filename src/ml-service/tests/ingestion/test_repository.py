from unittest.mock import MagicMock

from conftest import make_normalized_article

from app.ingestion.repository import ArticleRepository


def test_insert_executes_insert_sql():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    article = make_normalized_article()
    repo.insert(article)
    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "INSERT INTO articles" in sql
    assert "ON CONFLICT (url) DO NOTHING" in sql


def test_exists_by_url_returns_true_when_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1,)
    repo = ArticleRepository(conn)
    assert repo.exists_by_url("http://example.com") is True


def test_exists_by_url_returns_false_when_not_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    repo = ArticleRepository(conn)
    assert repo.exists_by_url("http://example.com") is False


def test_exists_by_content_hash_returns_true_when_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1,)
    repo = ArticleRepository(conn)
    assert repo.exists_by_content_hash("abc123") is True


def test_find_recent_for_dedup_returns_rows():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"title_normalized": "test title", "author_normalized": "test author"}
    ]
    repo = ArticleRepository(conn)
    rows = repo.find_recent_for_dedup(days=7)
    assert len(rows) == 1
    assert rows[0]["title_normalized"] == "test title"


def test_insert_batch_inserts_all_articles():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    articles = [make_normalized_article(), make_normalized_article()]
    repo.insert_batch(articles)
    assert conn.execute.call_count == 2
