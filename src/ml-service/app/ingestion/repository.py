from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg

from app.ingestion.models import NormalizedArticle


class ArticleRepository:
    """PostgreSQL CRUD operations for articles."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def insert(self, article: NormalizedArticle) -> None:
        self.conn.execute(
            """
            INSERT INTO articles
                (id, url, content_hash, title, title_normalized,
                 author, author_normalized, raw_content, source_name,
                 published_at, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                str(article.id),
                article.url,
                article.content_hash,
                article.title,
                article.title_normalized,
                article.author,
                article.author_normalized,
                article.raw_content,
                article.source_name,
                article.published_at,
                article.fetched_at,
            ),
        )

    def insert_batch(self, articles: list[NormalizedArticle]) -> None:
        for article in articles:
            self.insert(article)

    def exists_by_url(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url = %s", (url,)
        ).fetchone()
        return row is not None

    def exists_by_content_hash(self, content_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE content_hash = %s", (content_hash,)
        ).fetchone()
        return row is not None

    def find_recent_for_dedup(self, days: int = 7) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.conn.execute(
            """
            SELECT title_normalized, author_normalized
            FROM articles
            WHERE created_at > %s
            """,
            (cutoff,),
        ).fetchall()
        return rows

    def update_qdrant_point_ids(self, article_ids: list[UUID]) -> None:
        for article_id in article_ids:
            self.conn.execute(
                "UPDATE articles SET qdrant_point_id = %s WHERE id = %s",
                (str(article_id), str(article_id)),
            )

    def commit(self) -> None:
        self.conn.commit()
