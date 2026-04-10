from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.routers.health._check_qdrant", return_value="connected")
@patch("app.routers.health._check_database", return_value="connected")
def test_health_both_connected(mock_db, mock_qdrant):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["qdrant"] == "connected"


@patch("app.routers.health._check_qdrant", return_value="connected")
@patch("app.routers.health._check_database", return_value="not_connected")
def test_health_database_down(mock_db, mock_qdrant):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "not_connected"
    assert data["qdrant"] == "connected"


@patch("app.routers.health._check_qdrant", return_value="not_connected")
@patch("app.routers.health._check_database", return_value="connected")
def test_health_qdrant_down(mock_db, mock_qdrant):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "connected"
    assert data["qdrant"] == "not_connected"


@patch("app.routers.health._check_qdrant", return_value="not_connected")
@patch("app.routers.health._check_database", return_value="not_connected")
def test_health_both_down(mock_db, mock_qdrant):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "not_connected"
    assert data["qdrant"] == "not_connected"
