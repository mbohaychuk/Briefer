import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.ingestion.models import NormalizedArticle
from app.reasoning.models import ScoredArticle, UserProfile

logger = logging.getLogger(__name__)


class ArticleRetriever:
    """Tier 1: Retrieves candidate articles from Qdrant via multi-vector search."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection: str,
        conn: psycopg.Connection,
        top_k: int = 50,
        date_days: int = 7,
    ):
        self.qdrant = qdrant_client
        self.collection = collection
        self.conn = conn
        self.top_k = top_k
        self.date_days = date_days

    def retrieve(self, profile: UserProfile) -> list[ScoredArticle]:
        # Query Qdrant once per interest vector
        candidates: dict[str, float] = {}  # article_id -> best score

        for block in profile.interest_blocks:
            hits = self.qdrant.search(
                collection_name=self.collection,
                query_vector=block.embedding,
                limit=self.top_k,
            )
            for hit in hits:
                article_id = hit.id
                score = hit.score
                if article_id not in candidates or score > candidates[article_id]:
                    candidates[article_id] = score

        if not candidates:
            logger.info("No candidates found in Qdrant")
            return []

        logger.info(
            "Retrieved %d unique candidates from Qdrant", len(candidates)
        )

        # Load full article data from PostgreSQL
        article_ids = list(candidates.keys())
        articles = self._load_articles(article_ids)

        # Build ScoredArticle list
        results = []
        for article in articles:
            article_id_str = str(article.id)
            if article_id_str in candidates:
                results.append(
                    ScoredArticle(
                        article=article,
                        vector_score=candidates[article_id_str],
                    )
                )

        results.sort(key=lambda s: s.vector_score or 0, reverse=True)
        return results

    def _load_articles(self, article_ids: list[str]) -> list[NormalizedArticle]:
        if not article_ids:
            return []

        placeholders = ", ".join(["%s"] * len(article_ids))
        rows = self.conn.execute(
            f"""
            SELECT id, url, title, title_normalized, raw_content,
                   content_hash, source_name, author, author_normalized,
                   published_at, fetched_at
            FROM articles
            WHERE id IN ({placeholders})
            """,
            article_ids,
        ).fetchall()

        return [
            NormalizedArticle(
                id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
                url=row["url"],
                title=row["title"],
                title_normalized=row["title_normalized"] or "",
                raw_content=row["raw_content"] or "",
                content_hash=row["content_hash"] or "",
                source_name=row["source_name"],
                author=row["author"],
                author_normalized=row["author_normalized"],
                published_at=row["published_at"],
                fetched_at=row["fetched_at"],
            )
            for row in rows
        ]
