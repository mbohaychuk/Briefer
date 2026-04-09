from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Environmental policy", embedding=[]),
        ],
    )


def _make_scored(route="borderline", rerank_score=0.5):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=rerank_score,
        route=route,
    )


def test_scorer_assigns_llm_score():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 8,
        "explanation": "Highly relevant to environmental policy",
        "priority": "important",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)

    assert len(results) == 1
    assert results[0].llm_score == 8
    assert results[0].llm_explanation == "Highly relevant to environmental policy"
    assert results[0].priority == "important"


def test_scorer_filters_below_threshold():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.side_effect = [
        {"score": 8, "explanation": "Relevant", "priority": "important"},
        {"score": 3, "explanation": "Not relevant", "priority": "routine"},
    ]

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored(), _make_scored()]

    results = scorer.score(articles, profile)

    assert len(results) == 1
    assert results[0].llm_score == 8


def test_scorer_logs_cascade_misses(caplog):
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 9,
        "explanation": "Very relevant but missed by reranker",
        "priority": "critical",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    safety_net_article = _make_scored(route="safety_net")

    import logging
    with caplog.at_level(logging.WARNING):
        results = scorer.score([safety_net_article], profile)

    assert len(results) == 1
    assert "CASCADE MISS" in caplog.text


def test_scorer_handles_malformed_json():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.side_effect = Exception("Invalid JSON")

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)

    # Article should be skipped on error, not crash
    assert len(results) == 0


def test_scorer_includes_profile_in_prompt():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 7, "explanation": "Relevant", "priority": "routine"
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    scorer.score(articles, profile)

    prompt = mock_provider.generate_json.call_args[0][0]
    assert "Environmental policy" in prompt
