import logging

import psycopg
from psycopg.rows import dict_row

from app.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection:
    """Create a new database connection with dict row factory."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def init_schema():
    """Create the articles table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                url TEXT NOT NULL UNIQUE,
                content_hash TEXT,
                title TEXT NOT NULL,
                title_normalized TEXT,
                author TEXT,
                author_normalized TEXT,
                raw_content TEXT,
                source_name TEXT NOT NULL,
                published_at TIMESTAMPTZ,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                qdrant_point_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_content_hash "
            "ON articles (content_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_articles (
                user_id UUID NOT NULL,
                article_id UUID NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                vector_score REAL,
                rerank_score REAL,
                llm_score REAL,
                display_score REAL,
                summary TEXT,
                explanation TEXT,
                priority TEXT,
                route TEXT,
                profile_version INTEGER NOT NULL DEFAULT 1,
                scored_at TIMESTAMPTZ,
                briefed_at TIMESTAMPTZ,
                seen_at TIMESTAMPTZ,
                feedback TEXT,
                feedback_note TEXT,
                feedback_at TIMESTAMPTZ,
                PRIMARY KEY (user_id, article_id),
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_articles_user_status "
            "ON user_articles(user_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_articles_display_score "
            "ON user_articles(user_id, display_score DESC)"
        )
        conn.commit()
    logger.info("Database schema initialized")
