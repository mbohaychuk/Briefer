from dataclasses import dataclass, field
from uuid import UUID

from app.ingestion.models import NormalizedArticle


@dataclass
class InterestBlock:
    """A single interest description with its embedding."""

    label: str
    text: str
    embedding: list[float] = field(default_factory=list)


@dataclass
class UserProfile:
    """A user's profile with embedded interest blocks."""

    user_id: UUID
    name: str
    interest_blocks: list[InterestBlock] = field(default_factory=list)


@dataclass
class ScoredArticle:
    """An article accumulating scores through the cascade."""

    article: NormalizedArticle
    vector_score: float | None = None
    rerank_score: float | None = None
    llm_score: float | None = None
    llm_explanation: str | None = None
    priority: str | None = None
    summary: str | None = None
    display_score: float | None = None
    route: str | None = None


@dataclass
class ScoringResult:
    """Summary of a single scoring run."""

    user_id: UUID | None = None
    candidates_retrieved: int = 0
    reranked: int = 0
    llm_scored: int = 0
    summarized: int = 0
    stored: int = 0
