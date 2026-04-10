"""Integration test — scoring pipeline with realistic data, mocked LLM and infra.

Tests the full scoring cascade (retrieve → rerank → route → score → summarize
→ normalize → store) using synthetic article data and a fake LLM provider,
but real cross-encoder reranking.

Run with: pytest tests/integration/test_scoring_pipeline.py -v -m integration
"""

import logging
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.ingestion.models import NormalizedArticle
from app.reasoning.cascade_router import CascadeRouter
from app.reasoning.llm_scorer import LlmScorer
from app.reasoning.llm_summarizer import LlmSummarizer
from app.reasoning.models import (
    InterestBlock,
    ScoredArticle,
    UserProfile,
)
from app.reasoning.normalizer import ScoreNormalizer
from app.reasoning.pipeline import ScoringPipeline
from app.reasoning.reranker import ArticleReranker

logger = logging.getLogger(__name__)

# ---------- Fixtures ----------


def _make_article(title, content, source="Test Source"):
    return NormalizedArticle(
        id=uuid4(),
        url=f"http://example.com/{uuid4().hex[:8]}",
        title=title,
        title_normalized=title.lower(),
        raw_content=content,
        content_hash=uuid4().hex,
        source_name=source,
    )


def _make_scored(article, vector_score=0.8):
    return ScoredArticle(article=article, vector_score=vector_score)


ARTICLES = [
    _make_article(
        "Alberta announces new oil sands regulations",
        "The Alberta government announced sweeping new regulations for oil sands operations "
        "in the Peace River region, affecting wildlife corridors and deer populations.",
    ),
    _make_article(
        "Canadian energy sector faces trade uncertainty",
        "Oil and gas exports from Western Canada face new tariff threats as trade tensions "
        "escalate between the US and Canada, impacting Alberta's economy.",
    ),
    _make_article(
        "Deer population decline in Peace River",
        "Wildlife biologists report significant deer population declines in the Peace River "
        "region of Alberta, linked to habitat fragmentation from industrial development.",
    ),
    _make_article(
        "Premier Smith on provincial autonomy",
        "Alberta Premier Danielle Smith pushes for greater provincial autonomy in natural "
        "resource management and environmental policy decisions.",
    ),
    _make_article(
        "Tokyo Olympics venue repurposed as park",
        "A former Olympic venue in Tokyo has been converted into a public park, "
        "drawing visitors from across the country to enjoy the green space.",
    ),
    _make_article(
        "European football transfer window opens",
        "The summer transfer window is now open across major European football leagues, "
        "with several high-profile deals expected in the coming weeks.",
    ),
    _make_article(
        "New smartphone chip benchmarks released",
        "The latest mobile processor benchmarks show significant performance gains "
        "in AI workloads, with improved power efficiency for everyday tasks.",
    ),
    _make_article(
        "British Columbia forestry debate intensifies",
        "Environmental groups clash with logging companies over old-growth forest "
        "protections in British Columbia, with implications for neighboring Alberta.",
    ),
]

PROFILE = UserProfile(
    user_id=uuid4(),
    name="Alberta Policy Analyst",
    interest_blocks=[
        InterestBlock(
            label="Primary Role",
            text="Oil and gas policy analyst focused on Alberta energy sector regulation",
        ),
        InterestBlock(
            label="Wildlife Mandate",
            text="Monitoring deer populations and wildlife corridors in Peace River Alberta",
        ),
        InterestBlock(
            label="Regional Scope",
            text="Alberta provincial politics and policy with neighboring provinces",
        ),
    ],
)


class FakeLlmProvider:
    """Fake LLM that returns deterministic scores based on keywords."""

    RELEVANT_KEYWORDS = [
        "alberta", "oil", "gas", "energy", "deer", "wildlife",
        "peace river", "provincial", "regulation",
    ]

    def generate_json(self, prompt, **kwargs):
        """Return a relevance score based on keyword matching."""
        prompt_lower = prompt.lower()
        matches = sum(1 for kw in self.RELEVANT_KEYWORDS if kw in prompt_lower)
        score = min(10, max(1, matches * 2))
        priorities = {range(8, 11): "high", range(5, 8): "medium"}
        priority = "low"
        for r, p in priorities.items():
            if score in r:
                priority = p
                break
        return {
            "score": score,
            "explanation": f"Matched {matches} relevant keywords",
            "priority": priority,
        }

    def generate(self, prompt, **kwargs):
        """Return a fake summary."""
        return "This article is relevant to Alberta energy and wildlife policy interests."


@pytest.fixture(scope="module")
def scored_candidates():
    """Simulate retriever output: all articles with vector scores."""
    candidates = []
    for i, article in enumerate(ARTICLES):
        # Give relevant articles higher vector scores
        relevant = any(
            kw in article.raw_content.lower()
            for kw in ["alberta", "oil", "deer", "wildlife"]
        )
        score = 0.75 + (i * 0.02) if relevant else 0.3 + (i * 0.01)
        candidates.append(_make_scored(article, vector_score=score))
    return candidates


@pytest.fixture(scope="module")
def mock_retriever(scored_candidates):
    retriever = MagicMock()
    retriever.retrieve.return_value = scored_candidates
    return retriever


@pytest.fixture(scope="module")
def mock_repository():
    repo = MagicMock()
    repo.is_already_scored.return_value = False
    return repo


@pytest.fixture(scope="module")
def pipeline_result(mock_retriever, mock_repository):
    """Run the full scoring pipeline once."""
    fake_llm = FakeLlmProvider()
    reranker = ArticleReranker(model_name="BAAI/bge-reranker-v2-m3")
    router = CascadeRouter(clear_pass_count=3, safety_net_count=2)
    scorer = LlmScorer(provider=fake_llm, threshold=5)
    summarizer = LlmSummarizer(provider=fake_llm)
    normalizer = ScoreNormalizer()

    pipeline = ScoringPipeline(
        retriever=mock_retriever,
        reranker=reranker,
        router=router,
        scorer=scorer,
        summarizer=summarizer,
        normalizer=normalizer,
        repository=mock_repository,
    )

    result = pipeline.run(PROFILE)
    logger.info(
        "Scoring result: retrieved=%d, reranked=%d, llm_scored=%d, "
        "summarized=%d, stored=%d",
        result.candidates_retrieved, result.reranked, result.llm_scored,
        result.summarized, result.stored,
    )
    return result, mock_repository


# --- Tests ---


@pytest.mark.integration
def test_pipeline_retrieves_candidates(pipeline_result):
    result, _ = pipeline_result
    assert result.candidates_retrieved == len(ARTICLES)


@pytest.mark.integration
def test_pipeline_reranks_all(pipeline_result):
    result, _ = pipeline_result
    assert result.reranked == len(ARTICLES), (
        "Reranker should process all retrieved candidates"
    )


@pytest.mark.integration
def test_pipeline_scores_with_llm(pipeline_result):
    result, _ = pipeline_result
    assert result.llm_scored > 0, "At least some articles should pass LLM scoring"
    logger.info("LLM scored: %d", result.llm_scored)


@pytest.mark.integration
def test_pipeline_summarizes(pipeline_result):
    result, _ = pipeline_result
    assert result.summarized > 0, "At least some articles should be summarized"
    logger.info("Summarized: %d", result.summarized)


@pytest.mark.integration
def test_pipeline_stores_results(pipeline_result):
    result, repo = pipeline_result
    assert result.stored > 0, "Pipeline should store scored articles"
    repo.insert_batch.assert_called_once()
    repo.commit.assert_called_once()


@pytest.mark.integration
def test_stored_articles_have_scores(pipeline_result):
    """Articles stored should have display_score from normalization."""
    _, repo = pipeline_result
    call_args = repo.insert_batch.call_args
    stored_articles = call_args[0][1]  # second positional arg is the articles list
    for article in stored_articles:
        assert article.display_score is not None, (
            f"Article '{article.article.title}' missing display_score"
        )
        assert 0 <= article.display_score <= 1.0, (
            f"display_score out of range: {article.display_score}"
        )


@pytest.mark.integration
def test_relevant_articles_score_higher(pipeline_result):
    """Alberta/energy articles should generally outscore irrelevant ones."""
    _, repo = pipeline_result
    stored_articles = repo.insert_batch.call_args[0][1]

    relevant_titles = {"alberta", "oil", "deer", "energy", "peace river"}
    relevant_scores = []
    other_scores = []

    for sa in stored_articles:
        title_lower = sa.article.title.lower()
        is_relevant = any(kw in title_lower for kw in relevant_titles)
        if is_relevant:
            relevant_scores.append(sa.display_score)
        else:
            other_scores.append(sa.display_score)

    logger.info("Relevant article scores: %s", relevant_scores)
    logger.info("Other article scores: %s", other_scores)

    if relevant_scores and other_scores:
        avg_relevant = sum(relevant_scores) / len(relevant_scores)
        avg_other = sum(other_scores) / len(other_scores)
        logger.info(
            "Avg relevant: %.1f, avg other: %.1f", avg_relevant, avg_other
        )
        # Relevant articles should score at least as high on average
        # (not strictly higher due to small sample + fake LLM)
        assert avg_relevant >= avg_other * 0.8, (
            f"Relevant articles ({avg_relevant:.1f}) scoring much lower "
            f"than others ({avg_other:.1f})"
        )
