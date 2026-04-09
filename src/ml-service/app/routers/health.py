import logging
import os

from fastapi import APIRouter

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    db_status = "not_connected"
    qdrant_status = "not_connected"

    if os.environ.get("TESTING") == "1":
        return {
            "status": "healthy",
            "database": "testing",
            "qdrant": "testing",
        }

    try:
        from app.database import get_connection

        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception:
        logger.debug("Health check: database not reachable", exc_info=True)

    try:
        from qdrant_client import QdrantClient

        from app.config import settings

        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        qdrant_status = "connected"
    except Exception:
        logger.debug("Health check: Qdrant not reachable", exc_info=True)

    return {
        "status": "healthy",
        "database": db_status,
        "qdrant": qdrant_status,
    }
