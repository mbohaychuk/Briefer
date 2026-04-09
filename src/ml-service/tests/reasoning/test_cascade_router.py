import random
from uuid import uuid4

from conftest import make_normalized_article

from app.reasoning.models import ScoredArticle


def _make_scored(rerank_score):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.5,
        rerank_score=rerank_score,
    )


def test_router_clear_pass_takes_top_n():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=3, safety_net_count=2)
    articles = [_make_scored(score) for score in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]]

    result = router.route(articles)

    assert len(result.clear_pass) == 3
    # Top 3 by rerank_score
    scores = [a.rerank_score for a in result.clear_pass]
    assert scores == [0.9, 0.8, 0.7]


def test_router_borderline_between_thresholds():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=2, safety_net_count=1)
    # 10 articles with evenly spaced scores
    articles = [_make_scored(i / 10) for i in range(10, 0, -1)]

    result = router.route(articles)

    # Clear pass = top 2 (1.0, 0.9)
    assert len(result.clear_pass) == 2
    # Borderline = between 30th and 70th percentile (excluding clear-pass)
    # All borderline articles should have scores in the middle range
    for a in result.borderline:
        assert a not in result.clear_pass


def test_router_safety_net_samples_from_rejected():
    from app.reasoning.cascade_router import CascadeRouter

    random.seed(42)  # Deterministic for testing
    router = CascadeRouter(clear_pass_count=2, safety_net_count=3)
    articles = [_make_scored(i / 20) for i in range(20, 0, -1)]

    result = router.route(articles)

    assert len(result.safety_net) <= 3
    # Safety net articles should NOT overlap with clear_pass or borderline
    safety_ids = {id(a) for a in result.safety_net}
    clear_ids = {id(a) for a in result.clear_pass}
    border_ids = {id(a) for a in result.borderline}
    assert safety_ids.isdisjoint(clear_ids)
    assert safety_ids.isdisjoint(border_ids)


def test_router_sets_route_on_articles():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=2, safety_net_count=1)
    articles = [_make_scored(score) for score in [0.9, 0.8, 0.5, 0.2, 0.1]]

    result = router.route(articles)

    for a in result.clear_pass:
        assert a.route == "clear_pass"
    for a in result.borderline:
        assert a.route == "borderline"
    for a in result.safety_net:
        assert a.route == "safety_net"


def test_router_handles_fewer_articles_than_clear_pass():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=5, safety_net_count=3)
    articles = [_make_scored(0.9), _make_scored(0.8)]

    result = router.route(articles)

    # All articles become clear_pass when fewer than count
    assert len(result.clear_pass) == 2
    assert len(result.borderline) == 0
    assert len(result.safety_net) == 0


def test_router_handles_empty_list():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=5, safety_net_count=3)
    result = router.route([])

    assert result.clear_pass == []
    assert result.borderline == []
    assert result.safety_net == []
