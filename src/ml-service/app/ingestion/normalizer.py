import hashlib
import re
import unicodedata
from uuid import uuid4

from app.ingestion.models import NormalizedArticle, RawArticle


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace. Preserves non-Latin scripts."""
    text = unicodedata.normalize("NFKD", text)
    # Strip combining marks (accents) but keep base characters including non-Latin
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(text: str) -> str:
    """SHA-256 hash of normalized text content."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode()).hexdigest()


def normalize_article(raw: RawArticle, full_text: str) -> NormalizedArticle:
    """Convert a RawArticle + extracted full text into a NormalizedArticle."""
    return NormalizedArticle(
        id=uuid4(),
        url=raw.url,
        title=raw.title,
        title_normalized=normalize_text(raw.title),
        raw_content=full_text,
        content_hash=content_hash(full_text),
        source_name=raw.source_name,
        author=raw.author,
        author_normalized=normalize_text(raw.author) if raw.author else None,
        published_at=raw.published_at,
    )
