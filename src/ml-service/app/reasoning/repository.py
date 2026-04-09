import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg

from app.reasoning.models import ScoredArticle

logger = logging.getLogger(__name__)


class ScoringRepository:
    """PostgreSQL CRUD for user_articles scoring results."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def insert(self, user_id: UUID, scored: ScoredArticle, status: str = "ready") -> None:
        self.conn.execute(
            """
            INSERT INTO user_articles
                (user_id, article_id, status, vector_score, rerank_score,
                 llm_score, display_score, summary, explanation, priority,
                 route, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, article_id) DO NOTHING
            """,
            (
                str(user_id),
                str(scored.article.id),
                status,
                scored.vector_score,
                scored.rerank_score,
                scored.llm_score,
                scored.display_score,
                scored.summary,
                scored.llm_explanation,
                scored.priority,
                scored.route,
                datetime.now(timezone.utc),
            ),
        )

    def insert_batch(
        self, user_id: UUID, articles: list[ScoredArticle], status: str = "ready"
    ) -> None:
        for scored in articles:
            self.insert(user_id, scored, status)

    def find_by_user_and_status(self, user_id: UUID, status: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT article_id, display_score, summary, priority, explanation,
                   route, scored_at
            FROM user_articles
            WHERE user_id = %s AND status = %s
            ORDER BY display_score DESC
            """,
            (str(user_id), status),
        ).fetchall()
        return rows

    def is_already_scored(self, user_id: UUID, article_id: UUID) -> bool:
        row = self.conn.execute(
            "SELECT count(*) as count FROM user_articles WHERE user_id = %s AND article_id = %s",
            (str(user_id), str(article_id)),
        ).fetchone()
        return row["count"] > 0

    def commit(self) -> None:
        self.conn.commit()
