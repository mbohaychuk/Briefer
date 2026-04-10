import logging

from fastapi import APIRouter

router = APIRouter()

logger = logging.getLogger(__name__)


def _check_database() -> str:
    try:
        from app.database import get_connection

        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return "connected"
    except Exception:
        logger.debug("Health check: database not reachable", exc_info=True)
        return "not_connected"


def _check_qdrant() -> str:
    try:
        from qdrant_client import QdrantClient

        from app.config import settings

        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        return "connected"
    except Exception:
        logger.debug("Health check: Qdrant not reachable", exc_info=True)
        return "not_connected"


@router.get("/health")
async def health_check():
    db_status = _check_database()
    qdrant_status = _check_qdrant()

    overall = "healthy" if db_status == "connected" and qdrant_status == "connected" else "degraded"

    return {
        "status": overall,
        "database": db_status,
        "qdrant": qdrant_status,
    }
