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
        conn.commit()
    logger.info("Database schema initialized")
