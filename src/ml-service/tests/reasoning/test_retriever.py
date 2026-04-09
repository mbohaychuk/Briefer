from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile(num_interests=2):
    blocks = [
        InterestBlock(
            label=f"Interest {i}",
            text=f"I care about topic {i}",
            embedding=[float(i * 0.1)] * 384,
        )
        for i in range(num_interests)
    ]
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=blocks,
    )


def _make_qdrant_hit(article_id, score):
    hit = MagicMock()
    hit.id = str(article_id)
    hit.score = score
    hit.payload = {
        "title": "Test Article",
        "source_name": "Test Source",
        "url": f"http://example.com/{article_id}",
        "published_at": "2026-04-08T12:00:00+00:00",
    }
    return hit


def test_retriever_queries_per_interest_vector():
    from app.reasoning.retriever import ArticleRetriever

    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = []
    mock_conn = MagicMock()

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=3)
    retriever.retrieve(profile)

    assert mock_qdrant.search.call_count == 3


def test_retriever_deduplicates_across_interests():
    from app.reasoning.retriever import ArticleRetriever

    article_id = uuid4()
    mock_qdrant = MagicMock()
    # Same article returned by both interest queries, different scores
    mock_qdrant.search.side_effect = [
        [_make_qdrant_hit(article_id, 0.7)],
        [_make_qdrant_hit(article_id, 0.9)],
    ]

    article = make_normalized_article(id=article_id)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "id": str(article_id),
            "url": article.url,
            "title": article.title,
            "title_normalized": article.title_normalized,
            "raw_content": article.raw_content,
            "content_hash": article.content_hash,
            "source_name": article.source_name,
            "author": article.author,
            "author_normalized": article.author_normalized,
            "published_at": article.published_at,
            "fetched_at": article.fetched_at,
        }
    ]

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=2)
    results = retriever.retrieve(profile)

    # Should be deduplicated to 1 article with the highest score
    assert len(results) == 1
    assert results[0].vector_score == 0.9


def test_retriever_returns_scored_articles():
    from app.reasoning.retriever import ArticleRetriever

    id1 = uuid4()
    id2 = uuid4()
    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = [
        _make_qdrant_hit(id1, 0.8),
        _make_qdrant_hit(id2, 0.6),
    ]

    a1 = make_normalized_article(id=id1)
    a2 = make_normalized_article(id=id2)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "id": str(id1), "url": a1.url, "title": a1.title,
            "title_normalized": a1.title_normalized, "raw_content": a1.raw_content,
            "content_hash": a1.content_hash, "source_name": a1.source_name,
            "author": a1.author, "author_normalized": a1.author_normalized,
            "published_at": a1.published_at, "fetched_at": a1.fetched_at,
        },
        {
            "id": str(id2), "url": a2.url, "title": a2.title,
            "title_normalized": a2.title_normalized, "raw_content": a2.raw_content,
            "content_hash": a2.content_hash, "source_name": a2.source_name,
            "author": a2.author, "author_normalized": a2.author_normalized,
            "published_at": a2.published_at, "fetched_at": a2.fetched_at,
        },
    ]

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=1)
    results = retriever.retrieve(profile)

    assert len(results) == 2
    assert all(isinstance(r, ScoredArticle) for r in results)
    assert results[0].vector_score == 0.8


def test_retriever_handles_empty_results():
    from app.reasoning.retriever import ArticleRetriever

    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = []
    mock_conn = MagicMock()

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=1)
    results = retriever.retrieve(profile)

    assert results == []
