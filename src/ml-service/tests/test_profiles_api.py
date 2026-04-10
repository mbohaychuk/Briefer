from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient


def _make_mock_loader():
    loader = MagicMock()
    profile = MagicMock()
    profile.user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    profile.name = "Test User"
    loader.load_from_dict.return_value = [profile]
    return loader


@patch("app.routers.profiles._on_profiles_updated")
@patch("app.routers.profiles._profile_loader")
def test_sync_profiles_success(mock_loader, mock_callback):
    mock_loader.load_from_dict.return_value = [MagicMock()]

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/profiles/sync",
        json={
            "profiles": [
                {
                    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "name": "Test User",
                    "interests": [
                        {"label": "Primary Role", "text": "Environmental analyst"}
                    ],
                }
            ]
        },
        headers={"X-Api-Key": "test-api-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["profiles_synced"] == 1
    mock_loader.load_from_dict.assert_called_once()


@patch("app.routers.profiles._on_profiles_updated")
@patch("app.routers.profiles._profile_loader")
def test_sync_profiles_calls_callback(mock_loader, mock_callback):
    profiles = [MagicMock()]
    mock_loader.load_from_dict.return_value = profiles

    from app.main import app

    client = TestClient(app)
    client.post(
        "/api/profiles/sync",
        json={"profiles": [{"user_id": "u1", "name": "User", "interests": []}]},
        headers={"X-Api-Key": "test-api-key"},
    )

    mock_callback.assert_called_once_with(profiles)


@patch("app.routers.profiles._profile_loader")
def test_sync_profiles_multiple(mock_loader):
    mock_loader.load_from_dict.return_value = [MagicMock(), MagicMock()]

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/profiles/sync",
        json={
            "profiles": [
                {"user_id": "u1", "name": "User 1", "interests": []},
                {"user_id": "u2", "name": "User 2", "interests": []},
            ]
        },
        headers={"X-Api-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json()["profiles_synced"] == 2


def test_sync_profiles_no_loader_returns_503():
    from app.routers import profiles as profiles_mod

    original = profiles_mod._profile_loader
    profiles_mod._profile_loader = None

    try:
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/profiles/sync",
            json={"profiles": []},
            headers={"X-Api-Key": "test-api-key"},
        )
        assert response.status_code == 503
    finally:
        profiles_mod._profile_loader = original


def test_sync_profiles_requires_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/profiles/sync",
        json={"profiles": []},
    )
    assert response.status_code == 401


def test_sync_profiles_invalid_body():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/profiles/sync",
        json={"not_profiles": []},
        headers={"X-Api-Key": "test-api-key"},
    )
    assert response.status_code == 422
