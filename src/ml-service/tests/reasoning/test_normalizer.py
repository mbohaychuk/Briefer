from uuid import uuid4

from conftest import make_normalized_article

from app.reasoning.models import ScoredArticle


def _make_scored(vector_score=None, rerank_score=None, llm_score=None, route=None):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=vector_score,
        rerank_score=rerank_score,
        llm_score=llm_score,
        route=route,
    )


def test_normalizer_uses_llm_score_when_available():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.5, rerank_score=0.6, llm_score=8),
        _make_scored(vector_score=0.7, rerank_score=0.8, llm_score=6),
        _make_scored(vector_score=0.9, rerank_score=0.9, llm_score=4),
    ]

    results = normalizer.normalize(articles)

    # Article with highest LLM score should rank first
    assert results[0].llm_score == 8
    assert results[0].display_score is not None


def test_normalizer_discounts_rerank_only():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.5, rerank_score=0.9, llm_score=None),
        _make_scored(vector_score=0.5, rerank_score=0.5, llm_score=8),
    ]

    results = normalizer.normalize(articles)

    # LLM-scored article should rank higher despite lower rerank score
    llm_article = next(a for a in results if a.llm_score == 8)
    rerank_article = next(a for a in results if a.llm_score is None)
    assert llm_article.display_score > rerank_article.display_score


def test_normalizer_discounts_vector_only():
    from app.reasoning.normalizer import ScoreNormalizer, VECTOR_DISCOUNT, _to_percentile

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.9, rerank_score=None, llm_score=None),
        _make_scored(vector_score=0.5, rerank_score=None, llm_score=None),
    ]

    results = normalizer.normalize(articles)

    # Both have display scores
    assert all(a.display_score is not None for a in results)
    # Verify the 0.70 discount is actually applied
    vector_scores = [0.9, 0.5]
    for a in results:
        expected = _to_percentile(a.vector_score, vector_scores) * VECTOR_DISCOUNT
        assert a.display_score == expected, (
            f"vector_score={a.vector_score}: expected {expected}, got {a.display_score}"
        )


def test_normalizer_imputes_clear_pass_on_missing_llm():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(rerank_score=0.9, llm_score=None, route="clear_pass"),
        _make_scored(rerank_score=0.5, llm_score=9, route="borderline"),
        _make_scored(rerank_score=0.4, llm_score=7, route="borderline"),
        _make_scored(rerank_score=0.3, llm_score=5, route="borderline"),
    ]

    results = normalizer.normalize(articles)

    # Clear-pass article should get imputed score at 75th percentile of LLM scores
    clear_pass = next(a for a in results if a.route == "clear_pass")
    assert clear_pass.display_score is not None
    # It should not rank below all borderline articles
    assert clear_pass.display_score > results[-1].display_score


def test_normalizer_sorts_by_display_score_descending():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(llm_score=3),
        _make_scored(llm_score=9),
        _make_scored(llm_score=6),
    ]

    results = normalizer.normalize(articles)

    scores = [a.display_score for a in results]
    assert scores == sorted(scores, reverse=True)


def test_normalizer_handles_single_article():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [_make_scored(llm_score=7)]

    results = normalizer.normalize(articles)

    assert len(results) == 1
    assert results[0].display_score is not None


def test_normalizer_handles_empty_list():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    results = normalizer.normalize([])
    assert results == []
