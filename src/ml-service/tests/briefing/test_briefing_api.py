from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.briefing.models import Briefing, BriefingArticle


TEST_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
TEST_BRIEFING_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


def _make_mock_profile():
    profile = MagicMock()
    profile.user_id = UUID(TEST_USER_ID)
    profile.name = "Test User"
    return profile


def _make_test_briefing(status="complete", articles=None):
    now = datetime.now(timezone.utc)
    if articles is None:
        articles = [
            BriefingArticle(
                article_id=UUID("c3d4e5f6-a7b8-9012-cdef-123456789012"),
                title="Test Article",
                source_name="CBC",
                rank=1,
                display_score=0.9,
                summary="Relevant because...",
                priority="critical",
                explanation="Environmental impact",
                url="http://cbc.ca/test",
            )
        ]
    return Briefing(
        id=UUID(TEST_BRIEFING_ID),
        user_id=UUID(TEST_USER_ID),
        status=status,
        article_count=len(articles),
        articles=articles,
        executive_summary="Today's key highlights..." if status == "complete" else None,
        generated_at=now,
        created_at=now,
    )


@patch("app.routers.briefing.get_connection")
@patch("app.routers.briefing._generator")
@patch("app.routers.briefing._profiles")
def test_generate_briefing_success(mock_profiles, mock_generator, mock_get_conn):
    mock_profiles.__iter__ = MagicMock(return_value=iter([_make_mock_profile()]))
    mock_generator.generate_summary.return_value = "Executive summary text"

    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    briefing = _make_test_briefing()
    mock_repo = MagicMock()
    mock_repo.create_briefing.return_value = UUID(TEST_BRIEFING_ID)
    mock_repo.add_articles.return_value = briefing.articles
    mock_repo.get_briefing.return_value = briefing

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            f"/api/briefing/generate?user_id={TEST_USER_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["article_count"] == 1
    assert len(data["articles"]) == 1


@patch("app.routers.briefing.get_connection")
@patch("app.routers.briefing._generator")
@patch("app.routers.briefing._profiles")
def test_generate_briefing_no_ready_articles(mock_profiles, mock_generator, mock_get_conn):
    mock_profiles.__iter__ = MagicMock(return_value=iter([_make_mock_profile()]))

    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    empty_briefing = _make_test_briefing(status="failed", articles=[])
    mock_repo = MagicMock()
    mock_repo.create_briefing.return_value = UUID(TEST_BRIEFING_ID)
    mock_repo.add_articles.return_value = []
    mock_repo.get_briefing.return_value = empty_briefing

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            f"/api/briefing/generate?user_id={TEST_USER_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["article_count"] == 0
    mock_repo.mark_failed.assert_called_once()


@patch("app.routers.briefing._profiles")
def test_generate_briefing_unknown_user(mock_profiles):
    mock_profiles.__iter__ = MagicMock(return_value=iter([]))

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/briefing/generate?user_id=00000000-0000-0000-0000-000000000000",
        headers={"X-Api-Key": "test-api-key"},
    )
    assert response.status_code == 404


def test_generate_briefing_invalid_uuid():
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/briefing/generate?user_id=not-a-uuid",
        headers={"X-Api-Key": "test-api-key"},
    )
    assert response.status_code == 400


@patch("app.routers.briefing.get_connection")
def test_get_latest_briefing(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    briefing = _make_test_briefing()
    mock_repo = MagicMock()
    mock_repo.get_latest.return_value = briefing

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.get(
            f"/api/briefing/latest/{TEST_USER_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["executive_summary"] == "Today's key highlights..."


@patch("app.routers.briefing.get_connection")
def test_get_latest_briefing_not_found(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    mock_repo = MagicMock()
    mock_repo.get_latest.return_value = None

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.get(
            f"/api/briefing/latest/{TEST_USER_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 404


@patch("app.routers.briefing.get_connection")
def test_get_briefing_by_id(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    briefing = _make_test_briefing()
    mock_repo = MagicMock()
    mock_repo.get_briefing.return_value = briefing

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.get(
            f"/api/briefing/{TEST_BRIEFING_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == TEST_BRIEFING_ID


@patch("app.routers.briefing.get_connection")
def test_get_briefing_history(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    mock_repo = MagicMock()
    mock_repo.get_history.return_value = [
        {
            "id": TEST_BRIEFING_ID,
            "status": "complete",
            "article_count": 5,
            "has_summary": True,
            "generated_at": "2026-04-10T12:00:00+00:00",
            "created_at": "2026-04-10T12:00:00+00:00",
        }
    ]

    with patch("app.routers.briefing.BriefingRepository", return_value=mock_repo):
        from app.main import app

        client = TestClient(app)
        response = client.get(
            f"/api/briefing/history/{TEST_USER_ID}",
            headers={"X-Api-Key": "test-api-key"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["article_count"] == 5


def test_briefing_endpoints_require_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post(f"/api/briefing/generate?user_id={TEST_USER_ID}")
    assert response.status_code == 401
