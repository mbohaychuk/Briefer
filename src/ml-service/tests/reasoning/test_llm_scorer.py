from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

from conftest import make_normalized_article
from tests.reasoning.conftest import _make_profile, _make_scored

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


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
    profile = _make_profile(interest_blocks=[
        InterestBlock(label="Role", text="Environmental policy", embedding=[]),
    ])
    articles = [_make_scored()]

    scorer.score(articles, profile)

    prompt = mock_provider.generate_json.call_args[0][0]
    assert "Environmental policy" in prompt


def test_scorer_skips_incomplete_json():
    """Articles should be skipped when LLM returns JSON missing the 'score' key."""
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {"explanation": "no score"}

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)
    assert len(results) == 0


def test_scorer_handles_non_numeric_score():
    """Articles should be skipped when LLM returns a non-numeric score."""
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": "high",
        "explanation": "Very relevant",
        "priority": "routine",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)
    assert len(results) == 0


def test_scorer_clamps_out_of_range_score():
    """Scores above 10 should be clamped to 10."""
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 15,
        "explanation": "Extremely relevant",
        "priority": "routine",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)
    assert len(results) == 1
    assert results[0].llm_score == 10


def test_scorer_fixes_invalid_priority():
    """An invalid priority value should be corrected to 'routine'."""
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 8,
        "explanation": "Relevant article",
        "priority": "urgent",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)
    assert len(results) == 1
    assert results[0].priority == "routine"
