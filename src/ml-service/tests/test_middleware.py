import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import ApiKeyMiddleware


def _make_app():
    """Create a minimal FastAPI app with the API key middleware."""
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected():
        return {"data": "secret"}

    return app


def test_health_bypasses_auth():
    """The /health endpoint should be accessible without any API key."""
    with patch.dict(os.environ, {"ML_SERVICE_API_KEY": "super-secret"}):
        client = TestClient(_make_app())
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_api_key_configured_passes_all_requests():
    """When ML_SERVICE_API_KEY is not set, all requests should pass through."""
    env = os.environ.copy()
    env.pop("ML_SERVICE_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        client = TestClient(_make_app())
        response = client.get("/protected")
    assert response.status_code == 200
    assert response.json() == {"data": "secret"}


def test_correct_api_key_succeeds():
    """A request with the correct X-Api-Key header should succeed."""
    with patch.dict(os.environ, {"ML_SERVICE_API_KEY": "my-key"}):
        client = TestClient(_make_app())
        response = client.get("/protected", headers={"X-Api-Key": "my-key"})
    assert response.status_code == 200
    assert response.json() == {"data": "secret"}


def test_wrong_api_key_returns_401():
    """A request with a wrong API key should get a 401."""
    with patch.dict(os.environ, {"ML_SERVICE_API_KEY": "correct-key"}):
        client = TestClient(_make_app())
        response = client.get("/protected", headers={"X-Api-Key": "wrong-key"})
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid API key"}


def test_missing_api_key_header_returns_401():
    """A request without the X-Api-Key header should get a 401."""
    with patch.dict(os.environ, {"ML_SERVICE_API_KEY": "correct-key"}):
        client = TestClient(_make_app())
        response = client.get("/protected")
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid API key"}


def test_empty_api_key_header_returns_401():
    """A request with an empty X-Api-Key header should get a 401."""
    with patch.dict(os.environ, {"ML_SERVICE_API_KEY": "correct-key"}):
        client = TestClient(_make_app())
        response = client.get("/protected", headers={"X-Api-Key": ""})
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid API key"}
