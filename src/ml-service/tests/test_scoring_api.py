from dataclasses import asdict
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.reasoning.models import ScoringResult


@patch("app.routers.scoring.get_scoring_pipeline")
@patch("app.routers.scoring.get_profiles")
def test_trigger_scoring_returns_result(mock_profiles, mock_get_pipeline):
    mock_profile = MagicMock()
    mock_profile.user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    mock_profiles.return_value = [mock_profile]

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = ScoringResult(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        candidates_retrieved=100,
        reranked=100,
        llm_scored=15,
        summarized=12,
        stored=12,
    )
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scoring/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["stored"] == 12


@patch("app.routers.scoring.get_scoring_pipeline")
@patch("app.routers.scoring.get_profiles")
def test_trigger_scoring_handles_error(mock_profiles, mock_get_pipeline):
    mock_profile = MagicMock()
    mock_profile.user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    mock_profiles.return_value = [mock_profile]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = Exception("Qdrant unreachable")
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scoring/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 500


def test_get_scoring_status():
    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/scoring/status", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "last_run_at" in data


def test_scoring_endpoints_require_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/scoring/trigger")
    assert response.status_code == 401


@patch("app.routers.scoring._lock")
@patch("app.routers.scoring.get_scoring_pipeline")
def test_trigger_returns_already_running(mock_get_pipeline, mock_lock):
    """When the lock is already held, should return already_running status."""
    mock_lock.acquire.return_value = False

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scoring/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "already_running"
    mock_get_pipeline.assert_not_called()
