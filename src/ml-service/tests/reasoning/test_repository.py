from datetime import datetime, timezone
from unittest.mock import MagicMock, ANY
from uuid import UUID, uuid4

from conftest import make_normalized_article
from tests.reasoning.conftest import _make_scored

from app.reasoning.models import ScoredArticle


def _make_scored_for_storage():
    return _make_scored(
        vector_score=0.7,
        rerank_score=0.8,
        llm_score=8.0,
        llm_explanation="Relevant to environmental policy",
        priority="important",
        summary="This article matters because...",
        display_score=0.85,
        route="borderline",
    )


def test_repository_inserts_scored_article():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)

    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    scored = _make_scored_for_storage()

    repo.insert(user_id, scored, status="ready")

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql = call_args[0][0]
    assert "INSERT INTO user_articles" in sql
    params = call_args[0][1]
    # Verify parameter ordering matches SQL columns:
    # (user_id, article_id, status, vector_score, rerank_score,
    #  llm_score, display_score, summary, explanation, priority, route, scored_at)
    assert params[0] == str(user_id)
    assert params[1] == str(scored.article.id)
    assert params[2] == "ready"
    assert params[3] == scored.vector_score
    assert params[4] == scored.rerank_score
    assert params[5] == scored.llm_score
    assert params[6] == scored.display_score
    assert params[7] == scored.summary
    assert params[8] == scored.llm_explanation
    assert params[9] == scored.priority
    assert params[10] == scored.route
    assert isinstance(params[11], datetime)  # scored_at


def test_repository_insert_batch():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)

    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    articles = [_make_scored_for_storage() for _ in range(3)]

    repo.insert_batch(user_id, articles, status="ready")

    assert mock_conn.execute.call_count == 3


def test_repository_find_ready_for_user():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "article_id": str(uuid4()),
            "display_score": 0.9,
            "summary": "Summary",
            "priority": "important",
        }
    ]

    repo = ScoringRepository(conn=mock_conn)
    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    results = repo.find_by_user_and_status(user_id, "ready")

    assert len(results) == 1
    assert results[0]["display_score"] == 0.9


def test_repository_checks_already_scored():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"count": 1}

    repo = ScoringRepository(conn=mock_conn)
    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    article_id = uuid4()

    assert repo.is_already_scored(user_id, article_id) is True


def test_repository_is_already_scored_returns_false():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"count": 0}

    repo = ScoringRepository(conn=mock_conn)
    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    article_id = uuid4()

    assert repo.is_already_scored(user_id, article_id) is False


def test_repository_commit():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)
    repo.commit()
    mock_conn.commit.assert_called_once()
