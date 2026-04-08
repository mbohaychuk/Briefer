from fastapi.testclient import TestClient


def test_health_check():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "qdrant" in data
    assert "database" in data
