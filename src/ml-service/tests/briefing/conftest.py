from uuid import UUID

from app.briefing.models import Briefing, BriefingArticle
from app.reasoning.models import InterestBlock, UserProfile


TEST_USER_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
TEST_BRIEFING_ID = UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


def _make_profile(**kwargs):
    defaults = dict(
        user_id=TEST_USER_ID,
        name="Test User",
        interest_blocks=[
            InterestBlock(
                label="Primary Role",
                text="Environmental analyst for Alberta",
                embedding=[0.1] * 384,
            ),
        ],
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _make_briefing_article(rank=1, **kwargs):
    defaults = dict(
        article_id=UUID("c3d4e5f6-a7b8-9012-cdef-123456789012"),
        title="Test Article",
        source_name="Test Source",
        rank=rank,
        display_score=0.85,
        summary="This article is relevant because...",
        priority="important",
        explanation="Relates to environmental policy",
        url="http://example.com/article",
    )
    defaults.update(kwargs)
    return BriefingArticle(**defaults)


def _make_briefing_articles(count=3):
    from uuid import uuid4

    return [
        _make_briefing_article(
            rank=i + 1,
            article_id=uuid4(),
            title=f"Article {i + 1}",
            display_score=0.9 - (i * 0.1),
        )
        for i in range(count)
    ]
