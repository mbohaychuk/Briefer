from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

from app.briefing.repository import BriefingRepository


TEST_USER_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
TEST_BRIEFING_ID = UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


def _make_mock_conn():
    conn = MagicMock()
    return conn


def test_create_briefing_returns_uuid():
    conn = _make_mock_conn()
    conn.execute.return_value.fetchone.return_value = {"id": TEST_BRIEFING_ID}

    repo = BriefingRepository(conn)
    result = repo.create_briefing(TEST_USER_ID, profile_version=2)

    assert result == TEST_BRIEFING_ID
    conn.execute.assert_called_once()
    sql = conn.execute.call_args.args[0]
    assert "INSERT INTO briefings" in sql
    params = conn.execute.call_args.args[1]
    assert params[0] == str(TEST_USER_ID)
    assert params[1] == 2


def test_add_articles_returns_empty_for_no_ready():
    conn = _make_mock_conn()
    conn.execute.return_value.fetchall.return_value = []

    repo = BriefingRepository(conn)
    articles = repo.add_articles(TEST_BRIEFING_ID, TEST_USER_ID)

    assert articles == []


def test_add_articles_inserts_snapshots():
    conn = _make_mock_conn()
    article_id = uuid4()

    # First call returns the ready articles, subsequent calls are inserts
    fetch_result = MagicMock()
    fetch_result.fetchall.return_value = [
        {
            "article_id": article_id,
            "title": "Test Article",
            "source_name": "CBC",
            "url": "http://cbc.ca/test",
            "display_score": 0.9,
            "summary": "Relevant article",
            "priority": "critical",
            "explanation": "Environmental impact",
        }
    ]
    conn.execute.return_value = fetch_result

    repo = BriefingRepository(conn)
    articles = repo.add_articles(TEST_BRIEFING_ID, TEST_USER_ID)

    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].rank == 1
    assert articles[0].priority == "critical"
    # Should have been called: SELECT, INSERT briefing_articles, UPDATE user_articles, UPDATE briefings
    assert conn.execute.call_count == 4


def test_complete_briefing_sets_status():
    conn = _make_mock_conn()
    repo = BriefingRepository(conn)

    repo.complete_briefing(TEST_BRIEFING_ID, "Today's key items...")

    sql = conn.execute.call_args.args[0]
    assert "UPDATE briefings" in sql
    assert "complete" in sql
    params = conn.execute.call_args.args[1]
    assert params[0] == "Today's key items..."
    assert str(TEST_BRIEFING_ID) in params


def test_mark_failed_sets_status():
    conn = _make_mock_conn()
    repo = BriefingRepository(conn)

    repo.mark_failed(TEST_BRIEFING_ID)

    sql = conn.execute.call_args.args[0]
    assert "UPDATE briefings" in sql
    assert "failed" in sql


def test_get_briefing_returns_none_for_missing():
    conn = _make_mock_conn()
    conn.execute.return_value.fetchone.return_value = None

    repo = BriefingRepository(conn)
    result = repo.get_briefing(TEST_BRIEFING_ID)

    assert result is None


def test_get_briefing_returns_full_briefing():
    conn = _make_mock_conn()
    article_id = uuid4()
    now = datetime.now(timezone.utc)

    briefing_row = {
        "id": TEST_BRIEFING_ID,
        "user_id": TEST_USER_ID,
        "status": "complete",
        "article_count": 1,
        "executive_summary": "Key briefing summary",
        "profile_version": 1,
        "generated_at": now,
        "created_at": now,
    }
    article_rows = [
        {
            "article_id": article_id,
            "title": "Article 1",
            "source_name": "CBC",
            "url": "http://cbc.ca/1",
            "rank": 1,
            "display_score": 0.9,
            "summary": "Summary 1",
            "priority": "critical",
            "explanation": "Explanation 1",
        }
    ]

    # First execute returns briefing row, second returns article rows
    call_count = [0]
    original_execute = conn.execute

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.fetchone.return_value = briefing_row
        else:
            result.fetchall.return_value = article_rows
        return result

    conn.execute = MagicMock(side_effect=side_effect)

    repo = BriefingRepository(conn)
    briefing = repo.get_briefing(TEST_BRIEFING_ID)

    assert briefing is not None
    assert briefing.status == "complete"
    assert briefing.executive_summary == "Key briefing summary"
    assert len(briefing.articles) == 1
    assert briefing.articles[0].title == "Article 1"


def test_get_latest_returns_none_when_empty():
    conn = _make_mock_conn()
    conn.execute.return_value.fetchone.return_value = None

    repo = BriefingRepository(conn)
    result = repo.get_latest(TEST_USER_ID)

    assert result is None


def test_get_history_returns_list():
    conn = _make_mock_conn()
    now = datetime.now(timezone.utc)
    conn.execute.return_value.fetchall.return_value = [
        {
            "id": TEST_BRIEFING_ID,
            "status": "complete",
            "article_count": 5,
            "executive_summary": "Summary text",
            "generated_at": now,
            "created_at": now,
        }
    ]

    repo = BriefingRepository(conn)
    history = repo.get_history(TEST_USER_ID, limit=10)

    assert len(history) == 1
    assert history[0]["status"] == "complete"
    assert history[0]["article_count"] == 5
    assert history[0]["has_summary"] is True


def test_commit_delegates_to_connection():
    conn = _make_mock_conn()
    repo = BriefingRepository(conn)
    repo.commit()
    conn.commit.assert_called_once()
