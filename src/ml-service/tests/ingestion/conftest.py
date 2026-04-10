from unittest.mock import MagicMock


def _mock_httpx_get(mock_httpx, text="<html><body>Content</body></html>"):
    mock_response = MagicMock()
    mock_response.text = text
    mock_response.raise_for_status = MagicMock()
    mock_httpx.get.return_value = mock_response
