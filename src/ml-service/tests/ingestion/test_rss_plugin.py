import time
from types import SimpleNamespace
from unittest.mock import patch

from app.ingestion.plugins.rss_plugin import RssPlugin


def _make_entry(
    title="Test Article",
    link="http://example.com/1",
    author="Test Author",
    published_parsed=None,
):
    return SimpleNamespace(
        title=title,
        link=link,
        author=author,
        summary="A summary",
        published_parsed=published_parsed
        or time.struct_time((2026, 4, 8, 12, 0, 0, 1, 99, 0)),
    )


def _make_feed(entries):
    return SimpleNamespace(entries=entries, bozo=False)


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_returns_articles(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry()])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].url == "http://example.com/1"
    assert articles[0].source_name == "Test Feed"
    assert articles[0].author == "Test Author"
    assert articles[0].published_at is not None


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_multiple_feeds(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry()])
    feeds = [
        {"url": "http://feed1.rss", "name": "Feed 1"},
        {"url": "http://feed2.rss", "name": "Feed 2"},
    ]
    plugin = RssPlugin(feeds)
    articles = plugin.fetch()
    assert len(articles) == 2
    assert mock_parse.call_count == 2


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_skips_entries_without_link(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry(link="")])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_skips_entries_without_title(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry(title="")])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_handles_missing_published_date(mock_parse):
    entry = _make_entry()
    entry.published_parsed = None
    mock_parse.return_value = _make_feed([entry])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 1
    assert articles[0].published_at is None


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_survives_feed_error(mock_parse):
    mock_parse.side_effect = Exception("Network error")
    plugin = RssPlugin([{"url": "http://bad.rss", "name": "Bad Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0
