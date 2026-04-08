from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class RawArticle:
    """Raw article from a source plugin, before full-text extraction."""

    url: str
    title: str
    source_name: str
    author: str | None = None
    published_at: datetime | None = None
    summary: str | None = None


@dataclass
class NormalizedArticle:
    """Article with full text, content hash, and normalized fields for dedup."""

    id: UUID = field(default_factory=uuid4)
    url: str = ""
    title: str = ""
    title_normalized: str = ""
    raw_content: str = ""
    content_hash: str = ""
    source_name: str = ""
    author: str | None = None
    author_normalized: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class IngestionResult:
    """Summary of a single ingestion run."""

    fetched: int = 0
    extracted: int = 0
    new: int = 0
    embedded: int = 0
