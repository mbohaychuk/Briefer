import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.ingestion.models import IngestionResult


@patch("app.routers.ingestion.get_pipeline")
def test_trigger_ingestion_starts_run(mock_get_pipeline):
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = IngestionResult(
        fetched=10, extracted=8, new=5, embedded=5
    )
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/ingestion/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["fetched"] == 10
    assert data["result"]["new"] == 5


@patch("app.routers.ingestion.get_pipeline")
def test_trigger_ingestion_handles_pipeline_error(mock_get_pipeline):
    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = Exception("DB connection failed")
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/ingestion/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 500
    assert "detail" in response.json()


@patch("app.routers.ingestion.load_feeds")
def test_list_feeds(mock_load):
    mock_load.return_value = [
        {"url": "http://feed1.rss", "name": "Feed 1"},
        {"url": "http://feed2.rss", "name": "Feed 2"},
    ]

    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/ingestion/feeds", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["feeds"]) == 2


def test_get_status():
    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/ingestion/status", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "last_result" in data


def test_ingestion_endpoints_require_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/ingestion/trigger")
    assert response.status_code == 401


@patch("app.routers.ingestion._lock")
@patch("app.routers.ingestion.get_pipeline")
def test_trigger_returns_already_running(mock_get_pipeline, mock_lock):
    """When the lock is already held, should return already_running status."""
    mock_lock.acquire.return_value = False

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/ingestion/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_running"
    mock_get_pipeline.assert_not_called()


@patch("app.routers.ingestion.load_feeds")
def test_list_feeds_handles_missing_file(mock_load):
    """When feeds.json is missing, should return empty feeds list with error."""
    mock_load.side_effect = FileNotFoundError("feeds.json not found")

    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/ingestion/feeds", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["feeds"] == []
    assert "error" in data
