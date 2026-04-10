"""Integration test — ingestion pipeline with real fetch + extract, mocked storage.

Runs the full pipeline against real RSS feeds and real article extraction,
but mocks PostgreSQL and Qdrant to avoid needing infrastructure.

Run with: pytest tests/integration/test_ingestion_pipeline.py -v -m integration
"""

import json
import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.ingestion.dedup import Deduplicator
from app.ingestion.extractor import FullTextExtractor
from app.ingestion.normalizer import normalize_article
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.plugins.rss_plugin import RssPlugin

logger = logging.getLogger(__name__)

FEEDS_PATH = "feeds.json"
# Limit feeds to keep test time reasonable
MAX_FEEDS = 5
# Limit articles per feed to keep extraction time reasonable
MAX_ARTICLES_PER_FEED = 2


def _load_feeds():
    with open(FEEDS_PATH) as f:
        return json.load(f)["feeds"][:MAX_FEEDS]


def _mock_repository():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    return repo


def _mock_embedder():
    embedder = MagicMock()
    embedder.embed_and_store.side_effect = lambda articles: [a.id for a in articles]
    return embedder


def _mock_dedup(repository):
    """Create a real Deduplicator that uses the mocked repository."""
    return Deduplicator(repository)


@pytest.fixture(scope="module")
def pipeline_result():
    """Run the ingestion pipeline once with real feeds + extraction, mocked storage."""
    feeds = _load_feeds()
    plugins = [RssPlugin([feed]) for feed in feeds]

    # Limit articles per plugin to keep test fast
    limited_plugins = []
    for plugin in plugins:
        limited = MagicMock(wraps=plugin)
        original_fetch = plugin.fetch

        def make_limited_fetch(fetch_fn):
            def limited_fetch():
                return fetch_fn()[:MAX_ARTICLES_PER_FEED]
            return limited_fetch

        limited.fetch = make_limited_fetch(original_fetch)
        limited.name = plugin.name
        limited_plugins.append(limited)

    repo = _mock_repository()
    embedder = _mock_embedder()

    pipeline = IngestionPipeline(
        plugins=limited_plugins,
        extractor=FullTextExtractor(),
        normalizer_fn=normalize_article,
        dedup=_mock_dedup(repo),
        repository=repo,
        embedder=embedder,
    )

    result = pipeline.run()
    logger.info(
        "Pipeline result: fetched=%d, extracted=%d, new=%d, embedded=%d",
        result.fetched, result.extracted, result.new, result.embedded,
    )
    return result, repo, embedder


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_fetches_articles(pipeline_result):
    result, _, _ = pipeline_result
    assert result.fetched > 0, "Pipeline should fetch articles from real feeds"
    logger.info("Fetched: %d", result.fetched)


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_extracts_articles(pipeline_result):
    result, _, _ = pipeline_result
    assert result.extracted > 0, "Pipeline should extract full text from some articles"
    ratio = result.extracted / result.fetched if result.fetched else 0
    logger.info("Extracted: %d/%d (%.0f%%)", result.extracted, result.fetched, ratio * 100)
    assert ratio >= 0.5, f"Extraction rate too low: {ratio:.0%}"


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_stores_articles(pipeline_result):
    result, repo, _ = pipeline_result
    assert result.new > 0, "Pipeline should find new articles to store"
    repo.insert_batch.assert_called_once()
    stored_articles = repo.insert_batch.call_args[0][0]
    assert len(stored_articles) == result.new


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_embeds_articles(pipeline_result):
    result, _, embedder = pipeline_result
    assert result.embedded > 0, "Pipeline should embed new articles"
    embedder.embed_and_store.assert_called_once()


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_commits(pipeline_result):
    _, repo, _ = pipeline_result
    repo.commit.assert_called_once()


@pytest.mark.integration
@pytest.mark.slow
def test_stored_articles_have_required_fields(pipeline_result):
    """Articles passed to repository should be fully normalized."""
    _, repo, _ = pipeline_result
    stored_articles = repo.insert_batch.call_args[0][0]
    for article in stored_articles:
        assert article.url, f"Missing URL: {article}"
        assert article.title, f"Missing title: {article}"
        assert article.title_normalized, f"Missing normalized title: {article}"
        assert article.raw_content, f"Missing raw content: {article}"
        assert len(article.raw_content) >= 100, f"Content too short: {article.url}"
        assert article.content_hash, f"Missing content hash: {article}"
        assert article.source_name, f"Missing source name: {article}"
        assert article.id, f"Missing ID: {article}"
