"""Live article extraction tests — verify trafilatura works on real article URLs.

Run with: pytest tests/integration/test_live_extraction.py -v -m integration
"""

import json
import logging

import pytest

from app.ingestion.extractor import FullTextExtractor
from app.ingestion.normalizer import normalize_article
from app.ingestion.plugins.rss_plugin import RssPlugin

logger = logging.getLogger(__name__)

FEEDS_PATH = "feeds.json"

# How many articles per feed to sample for extraction
SAMPLE_SIZE = 3


def _load_feeds():
    with open(FEEDS_PATH) as f:
        return json.load(f)["feeds"]


@pytest.fixture(scope="module")
def sample_articles():
    """Fetch articles and sample a few from each feed for extraction testing."""
    feeds = _load_feeds()
    samples = []
    for feed_config in feeds:
        plugin = RssPlugin([feed_config])
        articles = plugin.fetch()
        for article in articles[:SAMPLE_SIZE]:
            samples.append(article)
    logger.info("Sampled %d articles for extraction testing", len(samples))
    return samples


@pytest.fixture(scope="module")
def extractor():
    return FullTextExtractor()


# --- Extraction tests ---


@pytest.mark.integration
@pytest.mark.slow
def test_extraction_succeeds_on_most_articles(sample_articles, extractor):
    """trafilatura should extract content from the majority of real articles."""
    successes = 0
    failures = []

    for article in sample_articles:
        text = extractor.extract(article.url)
        if text:
            successes += 1
        else:
            failures.append((article.source_name, article.url))

    total = len(sample_articles)
    ratio = successes / total if total else 0
    logger.info("Extraction success: %d/%d (%.0f%%)", successes, total, ratio * 100)

    for source, url in failures:
        logger.warning("  FAILED: [%s] %s", source, url)

    assert ratio >= 0.5, (
        f"Only {ratio:.0%} extraction success rate — trafilatura struggling with these sources"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_extracted_content_has_substance(sample_articles, extractor):
    """Extracted text should be meaningful article content, not boilerplate."""
    min_length = 200  # A real article should have at least a few paragraphs
    short_articles = []

    for article in sample_articles:
        text = extractor.extract(article.url)
        if text and len(text) < min_length:
            short_articles.append((article.source_name, article.url, len(text)))

    for source, url, length in short_articles:
        logger.warning("  SHORT (%d chars): [%s] %s", length, source, url)

    # Allow some short articles but flag if too many
    if sample_articles:
        short_ratio = len(short_articles) / len(sample_articles)
        assert short_ratio < 0.3, (
            f"{short_ratio:.0%} of articles are suspiciously short after extraction"
        )


@pytest.mark.integration
@pytest.mark.slow
def test_extraction_per_source(extractor):
    """Test extraction reliability per source — identifies problematic sources."""
    feeds = _load_feeds()
    results = []

    for feed_config in feeds:
        plugin = RssPlugin([feed_config])
        articles = plugin.fetch()[:SAMPLE_SIZE]
        successes = 0
        for article in articles:
            text = extractor.extract(article.url)
            if text and len(text) >= 100:
                successes += 1

        total = len(articles)
        ratio = successes / total if total else 0
        results.append((feed_config["name"], successes, total, ratio))
        logger.info(
            "  %-30s %d/%d extracted (%.0f%%)",
            feed_config["name"], successes, total, ratio * 100,
        )

    # Every source should have at least some extraction success
    for name, successes, total, ratio in results:
        if total > 0:
            assert ratio > 0, (
                f"Source '{name}' has 0% extraction rate — may need a different plugin"
            )


@pytest.mark.integration
@pytest.mark.slow
def test_normalization_of_real_articles(sample_articles, extractor):
    """Test the full normalize_article pipeline on real extracted content."""
    normalized_count = 0

    for article in sample_articles[:5]:
        text = extractor.extract(article.url)
        if not text:
            continue

        normalized = normalize_article(article, text)
        assert normalized.url == article.url
        assert normalized.title == article.title
        assert normalized.title_normalized, "Normalized title should not be empty"
        assert normalized.raw_content == text
        assert normalized.content_hash, "Content hash should not be empty"
        assert normalized.source_name == article.source_name
        normalized_count += 1

    assert normalized_count > 0, "Failed to normalize any real articles"
    logger.info("Successfully normalized %d real articles", normalized_count)
