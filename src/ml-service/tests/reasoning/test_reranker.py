from unittest.mock import MagicMock, patch
from uuid import UUID

from conftest import make_normalized_article
from tests.reasoning.conftest import _make_profile, _make_scored

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile
import numpy as np


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_scores_all_articles(mock_ce_cls):
    mock_model = MagicMock()
    # predict returns scores for each (query, doc) pair
    # 2 interests x 3 articles = 6 pairs
    mock_model.predict.return_value = np.array([0.5, 0.3, 0.7, 0.8, 0.2, 0.9])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored() for _ in range(3)]

    results = reranker.rerank(articles, profile)

    assert len(results) == 3
    assert all(r.rerank_score is not None for r in results)


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_keeps_best_interest_score(mock_ce_cls):
    mock_model = MagicMock()
    # 2 interests x 1 article = 2 pairs
    # Interest 0 gives 0.3, Interest 1 gives 0.9 — should keep 0.9
    mock_model.predict.return_value = np.array([0.3, 0.9])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored()]

    results = reranker.rerank(articles, profile)

    assert results[0].rerank_score == 0.9


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_builds_correct_pairs(mock_ce_cls):
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.5, 0.5])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile(interest_blocks=[
        InterestBlock(label="Role", text="Environmental policy analyst", embedding=[0.1] * 384),
        InterestBlock(label="Wildlife", text="Deer population management", embedding=[0.2] * 384),
    ])
    article = make_normalized_article(title="Deer Disease Found", raw_content="Full text about deer " * 30)
    articles = [ScoredArticle(article=article, vector_score=0.8)]

    reranker.rerank(articles, profile)

    pairs = mock_model.predict.call_args[0][0]
    # 2 interests x 1 article = 2 pairs
    assert len(pairs) == 2
    # Each pair is (interest_text, article_title + content[:512])
    assert pairs[0][0] == "Environmental policy analyst"
    assert pairs[1][0] == "Deer population management"
    assert pairs[0][1].startswith("Deer Disease Found\n")


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_preserves_vector_score(mock_ce_cls):
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.6, 0.4])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored(vector_score=0.75)]

    results = reranker.rerank(articles, profile)

    assert results[0].vector_score == 0.75
    assert results[0].rerank_score is not None


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_handles_empty_list(mock_ce_cls):
    mock_ce_cls.return_value = MagicMock()

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()

    results = reranker.rerank([], profile)
    assert results == []
