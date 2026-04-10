from unittest.mock import MagicMock, patch

from app.ingestion.extractor import FullTextExtractor


def _mock_httpx_get(mock_httpx, text="<html><body>Content</body></html>"):
    mock_response = MagicMock()
    mock_response.text = text
    mock_response.raise_for_status = MagicMock()
    mock_httpx.get.return_value = mock_response


@patch("app.ingestion.extractor.trafilatura")
@patch("app.ingestion.extractor.httpx")
def test_extract_returns_text(mock_httpx, mock_traf):
    _mock_httpx_get(mock_httpx)
    mock_traf.extract.return_value = (
        "This is a properly extracted article with enough content to pass the "
        "minimum length check that filters out stubs and error pages."
    )
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/article")
    assert result is not None
    assert "extracted article" in result
    mock_httpx.get.assert_called_once()


@patch("app.ingestion.extractor.httpx")
def test_extract_returns_none_on_download_failure(mock_httpx):
    mock_httpx.get.side_effect = Exception("Connection refused")
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/bad-url")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
@patch("app.ingestion.extractor.httpx")
def test_extract_returns_none_on_empty_response(mock_httpx, mock_traf):
    _mock_httpx_get(mock_httpx, text="")
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/empty")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
@patch("app.ingestion.extractor.httpx")
def test_extract_returns_none_when_extraction_empty(mock_httpx, mock_traf):
    _mock_httpx_get(mock_httpx)
    mock_traf.extract.return_value = None
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/empty")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
@patch("app.ingestion.extractor.httpx")
def test_extract_returns_none_for_short_content(mock_httpx, mock_traf):
    _mock_httpx_get(mock_httpx)
    mock_traf.extract.return_value = "Too short."
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/stub")
    assert result is None


@patch("app.ingestion.extractor.httpx")
def test_extract_handles_exception(mock_httpx):
    mock_httpx.get.side_effect = Exception("Connection timeout")
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/timeout")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
@patch("app.ingestion.extractor.httpx")
def test_extract_returns_none_on_http_error(mock_httpx, mock_traf):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")
    mock_httpx.get.return_value = mock_response
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/missing")
    assert result is None
