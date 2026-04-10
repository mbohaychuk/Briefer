from uuid import uuid4
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
    # Verify parameter tuple ordering matches SQL columns
    params = conn.execute.call_args[0][1]
    assert params == (
        str(article.id),
        article.url,
        article.content_hash,
        article.title,
        article.title_normalized,
        article.author,
        article.author_normalized,
        article.raw_content,
        article.source_name,
        article.published_at,
        article.fetched_at,
    )


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


def test_update_qdrant_point_ids():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    ids = [uuid4(), uuid4(), uuid4()]
    repo.update_qdrant_point_ids(ids)
    assert conn.execute.call_count == 3
    # Verify the SQL and params for each call
    for i, call_args in enumerate(conn.execute.call_args_list):
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "UPDATE articles SET qdrant_point_id" in sql
        assert params == (str(ids[i]), str(ids[i]))


def test_commit():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    repo.commit()
    conn.commit.assert_called_once()
