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


def test_empty_content_hash_skips_hash_check():
    """An article with content_hash='' should skip the content hash duplicate check."""
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    article = make_normalized_article(content_hash="")
    assert dedup.is_duplicate(article) is False
    # exists_by_content_hash should never be called when content_hash is empty
    repo.exists_by_content_hash.assert_not_called()


def test_fuzzy_title_at_boundary_89_not_duplicate():
    """A title with similarity score of 89 should NOT be flagged as duplicate (threshold is 90)."""
    from unittest.mock import patch as mock_patch

    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "existing article title", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="different article title",
        author_normalized="john doe",
    )
    with mock_patch("app.ingestion.dedup.fuzz.ratio", return_value=89):
        assert dedup.is_duplicate(article) is False


def test_fuzzy_title_at_boundary_90_is_duplicate():
    """A title with similarity score of 90 SHOULD be flagged as duplicate (threshold is 90)."""
    from unittest.mock import patch as mock_patch

    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "existing article title", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="very similar article title",
        author_normalized="john doe",
    )
    with mock_patch("app.ingestion.dedup.fuzz.ratio", return_value=90):
        assert dedup.is_duplicate(article) is True
