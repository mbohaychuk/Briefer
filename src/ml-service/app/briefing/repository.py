import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg

from app.briefing.models import Briefing, BriefingArticle

logger = logging.getLogger(__name__)


class BriefingRepository:
    """PostgreSQL CRUD for briefings and briefing_articles."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create_briefing(self, user_id: UUID, profile_version: int = 1) -> UUID:
        """Create a new pending briefing and return its ID."""
        row = self.conn.execute(
            """
            INSERT INTO briefings (user_id, profile_version, status)
            VALUES (%s, %s, 'pending')
            RETURNING id
            """,
            (str(user_id), profile_version),
        ).fetchone()
        return UUID(str(row["id"]))

    def add_articles(self, briefing_id: UUID, user_id: UUID) -> list[BriefingArticle]:
        """Snapshot ready articles into briefing_articles and mark them as briefed.

        Returns the list of BriefingArticle objects added to the briefing.
        """
        rows = self.conn.execute(
            """
            SELECT ua.article_id, a.title, a.source_name, a.url,
                   ua.display_score, ua.summary, ua.priority, ua.explanation
            FROM user_articles ua
            JOIN articles a ON a.id = ua.article_id
            WHERE ua.user_id = %s AND ua.status = 'ready'
            ORDER BY ua.display_score DESC
            """,
            (str(user_id),),
        ).fetchall()

        articles = []
        now = datetime.now(timezone.utc)

        for rank, row in enumerate(rows, start=1):
            article = BriefingArticle(
                article_id=UUID(str(row["article_id"])),
                title=row["title"],
                source_name=row["source_name"],
                rank=rank,
                display_score=row["display_score"],
                summary=row["summary"],
                priority=row["priority"],
                explanation=row["explanation"],
                url=row["url"],
            )
            articles.append(article)

            self.conn.execute(
                """
                INSERT INTO briefing_articles
                    (briefing_id, article_id, rank, display_score, summary,
                     priority, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(briefing_id),
                    str(article.article_id),
                    rank,
                    article.display_score,
                    article.summary,
                    article.priority,
                    article.explanation,
                ),
            )

        # Mark all these articles as briefed
        if articles:
            article_ids = [str(a.article_id) for a in articles]
            self.conn.execute(
                """
                UPDATE user_articles
                SET status = 'briefed', briefed_at = %s
                WHERE user_id = %s AND article_id = ANY(%s)
                """,
                (now, str(user_id), article_ids),
            )

        # Update article count on the briefing
        self.conn.execute(
            "UPDATE briefings SET article_count = %s WHERE id = %s",
            (len(articles), str(briefing_id)),
        )

        return articles

    def complete_briefing(self, briefing_id: UUID, executive_summary: str) -> None:
        """Mark briefing as complete with the generated executive summary."""
        self.conn.execute(
            """
            UPDATE briefings
            SET status = 'complete', executive_summary = %s, generated_at = %s
            WHERE id = %s
            """,
            (executive_summary, datetime.now(timezone.utc), str(briefing_id)),
        )

    def mark_failed(self, briefing_id: UUID) -> None:
        """Mark briefing as failed (articles are still valid)."""
        self.conn.execute(
            """
            UPDATE briefings
            SET status = 'failed', generated_at = %s
            WHERE id = %s
            """,
            (datetime.now(timezone.utc), str(briefing_id)),
        )

    def get_briefing(self, briefing_id: UUID) -> Briefing | None:
        """Retrieve a full briefing with its articles."""
        row = self.conn.execute(
            """
            SELECT id, user_id, status, article_count, executive_summary,
                   profile_version, generated_at, created_at
            FROM briefings WHERE id = %s
            """,
            (str(briefing_id),),
        ).fetchone()

        if not row:
            return None

        article_rows = self.conn.execute(
            """
            SELECT ba.article_id, a.title, a.source_name, a.url,
                   ba.rank, ba.display_score, ba.summary, ba.priority,
                   ba.explanation
            FROM briefing_articles ba
            JOIN articles a ON a.id = ba.article_id
            WHERE ba.briefing_id = %s
            ORDER BY ba.rank
            """,
            (str(briefing_id),),
        ).fetchall()

        articles = [
            BriefingArticle(
                article_id=UUID(str(ar["article_id"])),
                title=ar["title"],
                source_name=ar["source_name"],
                rank=ar["rank"],
                display_score=ar["display_score"],
                summary=ar["summary"],
                priority=ar["priority"],
                explanation=ar["explanation"],
                url=ar["url"],
            )
            for ar in article_rows
        ]

        return Briefing(
            id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            status=row["status"],
            article_count=row["article_count"],
            articles=articles,
            executive_summary=row["executive_summary"],
            profile_version=row["profile_version"],
            generated_at=row["generated_at"],
            created_at=row["created_at"],
        )

    def get_latest(self, user_id: UUID) -> Briefing | None:
        """Retrieve the most recent briefing for a user."""
        row = self.conn.execute(
            "SELECT id FROM briefings WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()

        if not row:
            return None

        return self.get_briefing(UUID(str(row["id"])))

    def get_history(self, user_id: UUID, limit: int = 30) -> list[dict]:
        """Return recent briefing metadata (no articles) for history view."""
        rows = self.conn.execute(
            """
            SELECT id, status, article_count, executive_summary,
                   generated_at, created_at
            FROM briefings
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (str(user_id), limit),
        ).fetchall()

        return [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "article_count": r["article_count"],
                "has_summary": r["executive_summary"] is not None,
                "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    def commit(self) -> None:
        self.conn.commit()
