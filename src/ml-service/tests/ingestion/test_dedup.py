from unittest.mock import MagicMock

from conftest import make_normalized_article

from app.ingestion.dedup import Deduplicator

FEEDS_URL_BASE = "http://example.com"


def test_exact_url_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = True
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is True
    repo.exists_by_content_hash.assert_not_called()


def test_content_hash_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = True
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is True


def test_fuzzy_title_match_same_author_is_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "breaking news major event", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="breaking news major event",
        author_normalized="john doe",
    )
    assert dedup.is_duplicate(article) is True


def test_same_title_different_author_not_duplicate():
    """Per spec: same title + different author = different article (different perspectives)."""
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "breaking news event", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="breaking news event",
        author_normalized="jane smith",
    )
    assert dedup.is_duplicate(article) is False


def test_new_article_not_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is False


def test_filter_removes_duplicates():
    repo = MagicMock()
    repo.exists_by_url.side_effect = [True, False]
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    articles = [make_normalized_article(), make_normalized_article()]
    result = dedup.filter_duplicates(articles)
    assert len(result) == 1


def test_filter_deduplicates_within_batch():
    """Two articles with the same URL in one batch — only the first should pass."""
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    shared_url = "http://example.com/same-article"
    articles = [
        make_normalized_article(url=shared_url),
        make_normalized_article(url=shared_url),
    ]
    result = dedup.filter_duplicates(articles)
    assert len(result) == 1
