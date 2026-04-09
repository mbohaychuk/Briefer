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
