from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class BriefingArticle:
    """A snapshot of an article included in a briefing."""

    article_id: UUID
    title: str
    source_name: str
    rank: int
    display_score: float | None = None
    summary: str | None = None
    priority: str | None = None
    explanation: str | None = None
    url: str | None = None


@dataclass
class Briefing:
    """A generated briefing for a user."""

    id: UUID
    user_id: UUID
    status: str  # pending, complete, failed
    article_count: int = 0
    articles: list[BriefingArticle] = field(default_factory=list)
    executive_summary: str | None = None
    profile_version: int = 1
    generated_at: datetime | None = None
    created_at: datetime | None = None
