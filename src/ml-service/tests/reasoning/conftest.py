from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile(num_interests=2, **kwargs):
    defaults = dict(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
    )
    defaults.update(kwargs)

    if "interest_blocks" not in defaults:
        defaults["interest_blocks"] = [
            InterestBlock(
                label=f"Interest {i}",
                text=f"I care about topic {i}",
                embedding=[float(i * 0.1)] * 384,
            )
            for i in range(num_interests)
        ]
    return UserProfile(**defaults)


def _make_scored(**kwargs):
    defaults = dict(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
    )
    defaults.update(kwargs)
    return ScoredArticle(**defaults)


def _make_article(**kwargs):
    return make_normalized_article(**kwargs)
