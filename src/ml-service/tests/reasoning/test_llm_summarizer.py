from unittest.mock import MagicMock
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


def _make_scored():
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=0.8,
        llm_score=8,
        llm_explanation="Relevant",
        priority="important",
        route="borderline",
    )


def test_summarizer_generates_summary():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.return_value = (
        "This article discusses new environmental regulations that directly "
        "affect Alberta's oil and gas sector."
    )

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    results = summarizer.summarize(articles, profile)

    assert len(results) == 1
    assert "environmental regulations" in results[0].summary


def test_summarizer_includes_profile_context():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary text"

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    summarizer.summarize(articles, profile)

    prompt = mock_provider.generate.call_args[0][0]
    assert "Environmental policy" in prompt


def test_summarizer_handles_failure_gracefully():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception("Ollama timeout")

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    results = summarizer.summarize(articles, profile)

    # Article passes through even if summary fails
    assert len(results) == 1
    assert results[0].summary is None


def test_summarizer_handles_multiple_articles():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = [
        "Summary for article 1",
        "Summary for article 2",
        "Summary for article 3",
    ]

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored() for _ in range(3)]

    results = summarizer.summarize(articles, profile)

    assert len(results) == 3
    assert mock_provider.generate.call_count == 3
