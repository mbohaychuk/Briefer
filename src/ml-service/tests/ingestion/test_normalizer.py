from datetime import datetime, timezone

from app.ingestion.models import RawArticle
from app.ingestion.normalizer import content_hash, normalize_article, normalize_text


def test_normalize_text_lowercases():
    assert normalize_text("Hello World") == "hello world"


def test_normalize_text_strips_punctuation():
    assert normalize_text("hello, world! test.") == "hello world test"


def test_normalize_text_collapses_whitespace():
    assert normalize_text("hello   world  test") == "hello world test"


def test_normalize_text_strips_accents():
    assert normalize_text("café résumé") == "cafe resume"


def test_content_hash_deterministic():
    assert content_hash("Hello World") == content_hash("Hello World")


def test_content_hash_case_insensitive():
    assert content_hash("Hello World") == content_hash("hello world")


def test_content_hash_differs_for_different_text():
    assert content_hash("Hello") != content_hash("World")


def test_normalize_article_populates_all_fields():
    raw = RawArticle(
        url="http://example.com/article",
        title="Breaking News: Test Article!",
        source_name="Test Source",
        author="John Doe",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
    )
    result = normalize_article(raw, "Full article text content here.")

    assert result.url == raw.url
    assert result.title == raw.title
    assert result.title_normalized == "breaking news test article"
    assert result.author_normalized == "john doe"
    assert result.raw_content == "Full article text content here."
    assert len(result.content_hash) == 64  # SHA-256 hex
    assert result.id is not None


def test_normalize_article_handles_none_author():
    raw = RawArticle(url="http://example.com", title="Title", source_name="Src")
    result = normalize_article(raw, "Article text.")
    assert result.author_normalized is None
