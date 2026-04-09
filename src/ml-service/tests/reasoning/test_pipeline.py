from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.cascade_router import RouteResult
from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Policy", embedding=[0.1] * 384),
        ],
    )


def _make_scored(route="borderline"):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=0.6,
        route=route,
    )


def _build_pipeline(**overrides):
    from app.reasoning.pipeline import ScoringPipeline

    defaults = {
        "retriever": MagicMock(),
        "reranker": MagicMock(),
        "router": MagicMock(),
        "scorer": MagicMock(),
        "summarizer": MagicMock(),
        "normalizer": MagicMock(),
        "repository": MagicMock(),
    }
    defaults.update(overrides)

    # Wire up sensible defaults
    if "retriever" not in overrides:
        defaults["retriever"].retrieve.return_value = [_make_scored()]
    if "reranker" not in overrides:
        defaults["reranker"].rerank.side_effect = lambda articles, profile: articles
    if "router" not in overrides:
        defaults["router"].route.return_value = RouteResult(
            clear_pass=[],
            borderline=[_make_scored()],
            safety_net=[],
        )
    if "scorer" not in overrides:
        scored = _make_scored()
        scored.llm_score = 8
        defaults["scorer"].score.return_value = [scored]
    if "summarizer" not in overrides:
        defaults["summarizer"].summarize.side_effect = lambda articles, profile: articles
    if "normalizer" not in overrides:
        defaults["normalizer"].normalize.side_effect = lambda articles: articles

    return ScoringPipeline(**defaults)


def test_pipeline_end_to_end():
    pipeline = _build_pipeline()
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.candidates_retrieved == 1
    assert result.reranked == 1
    assert result.llm_scored == 1
    assert result.user_id == profile.user_id


def test_pipeline_combines_router_outputs_for_scorer():
    router = MagicMock()
    clear = [_make_scored("clear_pass")]
    border = [_make_scored("borderline"), _make_scored("borderline")]
    safety = [_make_scored("safety_net")]
    router.route.return_value = RouteResult(
        clear_pass=clear, borderline=border, safety_net=safety
    )

    scorer = MagicMock()
    scorer.score.return_value = clear + border + safety

    pipeline = _build_pipeline(router=router, scorer=scorer)
    profile = _make_profile()
    pipeline.run(profile)

    # Scorer should receive all three lists combined
    scored_articles = scorer.score.call_args[0][0]
    assert len(scored_articles) == 4


def test_pipeline_stores_results():
    repository = MagicMock()

    pipeline = _build_pipeline(repository=repository)
    profile = _make_profile()
    pipeline.run(profile)

    repository.insert_batch.assert_called_once()
    repository.commit.assert_called_once()


def test_pipeline_handles_no_candidates():
    retriever = MagicMock()
    retriever.retrieve.return_value = []

    pipeline = _build_pipeline(retriever=retriever)
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.candidates_retrieved == 0
    assert result.stored == 0


def test_pipeline_handles_no_llm_passes():
    scorer = MagicMock()
    scorer.score.return_value = []

    pipeline = _build_pipeline(scorer=scorer)
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.llm_scored == 0
    assert result.summarized == 0


def test_pipeline_singleton():
    from app.reasoning.pipeline import get_scoring_pipeline, init_scoring_pipeline

    mock_pipeline = MagicMock()
    init_scoring_pipeline(mock_pipeline)

    assert get_scoring_pipeline() is mock_pipeline
