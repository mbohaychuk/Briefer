"""Live RSS feed tests — hit real feeds and verify article collection.

Run with: pytest tests/integration/test_live_feeds.py -v -m integration
Skip in CI: pytest -m "not integration"
"""

import json
import logging
from datetime import datetime, timezone, timedelta

import pytest

from app.ingestion.plugins.rss_plugin import RssPlugin

logger = logging.getLogger(__name__)

FEEDS_PATH = "feeds.json"


def _load_feeds():
    with open(FEEDS_PATH) as f:
        return json.load(f)["feeds"]


@pytest.fixture(scope="module")
def all_feeds():
    return _load_feeds()


@pytest.fixture(scope="module")
def all_articles(all_feeds):
    """Fetch articles from all feeds once for the entire test module."""
    plugin = RssPlugin(all_feeds)
    articles = plugin.fetch()
    logger.info("Fetched %d total articles from %d feeds", len(articles), len(all_feeds))
    return articles


# --- Feed-level tests ---


@pytest.mark.integration
def test_feeds_json_is_valid():
    feeds = _load_feeds()
    assert len(feeds) > 0, "feeds.json has no feeds"
    for feed in feeds:
        assert "url" in feed, f"Feed missing 'url': {feed}"
        assert "name" in feed, f"Feed missing 'name': {feed}"
        assert feed["url"].startswith("http"), f"Invalid URL: {feed['url']}"


@pytest.mark.integration
def test_all_feeds_return_articles(all_feeds):
    """Each configured feed should return at least 1 article."""
    for feed_config in all_feeds:
        plugin = RssPlugin([feed_config])
        articles = plugin.fetch()
        assert len(articles) > 0, (
            f"Feed '{feed_config['name']}' ({feed_config['url']}) returned 0 articles"
        )
        logger.info(
            "Feed '%s': %d articles", feed_config["name"], len(articles)
        )


@pytest.mark.integration
def test_total_article_count(all_articles):
    """We should get a reasonable volume of articles across all feeds."""
    assert len(all_articles) >= 20, (
        f"Only {len(all_articles)} articles total — need more feeds for meaningful coverage"
    )
    logger.info("Total articles: %d", len(all_articles))


@pytest.mark.integration
def test_article_count_per_feed(all_feeds):
    """Report article counts per feed to help identify thin sources."""
    results = []
    for feed_config in all_feeds:
        plugin = RssPlugin([feed_config])
        articles = plugin.fetch()
        results.append((feed_config["name"], len(articles)))

    # Log the report
    for name, count in sorted(results, key=lambda x: x[1], reverse=True):
        logger.info("  %-30s %d articles", name, count)

    # At least half of feeds should return 5+ articles
    good_feeds = sum(1 for _, count in results if count >= 5)
    assert good_feeds >= len(results) // 2, (
        f"Only {good_feeds}/{len(results)} feeds return 5+ articles"
    )


# --- Article quality tests ---


@pytest.mark.integration
def test_articles_have_required_fields(all_articles):
    """Every article must have a URL, title, and source name."""
    for article in all_articles:
        assert article.url, f"Article missing URL: {article}"
        assert article.title, f"Article missing title: {article}"
        assert article.source_name, f"Article missing source_name: {article}"


@pytest.mark.integration
def test_articles_have_valid_urls(all_articles):
    """Article URLs should be proper HTTP(S) links."""
    for article in all_articles:
        assert article.url.startswith("http://") or article.url.startswith("https://"), (
            f"Invalid URL from {article.source_name}: {article.url}"
        )


@pytest.mark.integration
def test_articles_have_dates(all_articles):
    """Most articles should have published dates for time-based filtering."""
    with_dates = sum(1 for a in all_articles if a.published_at is not None)
    ratio = with_dates / len(all_articles) if all_articles else 0
    logger.info("Articles with dates: %d/%d (%.0f%%)", with_dates, len(all_articles), ratio * 100)
    assert ratio >= 0.5, (
        f"Only {ratio:.0%} of articles have published dates — scoring needs dates for filtering"
    )


@pytest.mark.integration
def test_articles_are_recent(all_articles):
    """Articles should be from the last 7 days (the scoring window)."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    dated = [a for a in all_articles if a.published_at is not None]
    if not dated:
        pytest.skip("No articles with dates to check")

    recent = sum(1 for a in dated if a.published_at >= week_ago)
    ratio = recent / len(dated)
    logger.info("Recent articles (<=7 days): %d/%d (%.0f%%)", recent, len(dated), ratio * 100)
    assert ratio >= 0.5, (
        f"Only {ratio:.0%} of dated articles are within 7 days"
    )


@pytest.mark.integration
def test_no_duplicate_urls(all_articles):
    """Check for URL-level duplicates across feeds."""
    urls = [a.url for a in all_articles]
    unique_urls = set(urls)
    dupes = len(urls) - len(unique_urls)
    logger.info("Duplicate URLs across feeds: %d", dupes)
    # Some duplication is expected (syndication), but flag excessive
    dupe_ratio = dupes / len(urls) if urls else 0
    assert dupe_ratio < 0.3, (
        f"{dupe_ratio:.0%} of articles are URL duplicates — feeds overlap too much"
    )


@pytest.mark.integration
def test_source_diversity(all_articles):
    """Articles should come from multiple distinct sources."""
    sources = set(a.source_name for a in all_articles)
    logger.info("Unique sources: %s", sources)
    assert len(sources) >= 3, (
        f"Only {len(sources)} unique sources — need more diversity"
    )
