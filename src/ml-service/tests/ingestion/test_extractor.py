from unittest.mock import patch

from app.ingestion.extractor import FullTextExtractor


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_text(mock_traf):
    mock_traf.fetch_url.return_value = "<html><body>Content</body></html>"
    mock_traf.extract.return_value = (
        "This is a properly extracted article with enough content to pass the "
        "minimum length check that filters out stubs and error pages."
    )
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/article")
    assert result is not None
    assert "extracted article" in result
    mock_traf.fetch_url.assert_called_once_with("http://example.com/article")


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_on_download_failure(mock_traf):
    mock_traf.fetch_url.return_value = None
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/bad-url")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_when_extraction_empty(mock_traf):
    mock_traf.fetch_url.return_value = "<html></html>"
    mock_traf.extract.return_value = None
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/empty")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_for_short_content(mock_traf):
    mock_traf.fetch_url.return_value = "<html>content</html>"
    mock_traf.extract.return_value = "Too short."
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/stub")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_handles_exception(mock_traf):
    mock_traf.fetch_url.side_effect = Exception("Connection timeout")
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/timeout")
    assert result is None
