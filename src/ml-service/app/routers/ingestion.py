import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.ingestion.models import IngestionResult
from app.ingestion.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

_last_result: IngestionResult | None = None
_last_run_at: datetime | None = None
_running = False


def load_feeds(path: str = "feeds.json") -> list[dict]:
    with open(path) as f:
        return json.load(f)["feeds"]


@router.post("/trigger")
async def trigger_ingestion():
    global _last_result, _last_run_at, _running

    if _running:
        return {"status": "already_running"}

    _running = True
    try:
        pipeline = get_pipeline()
        result = pipeline.run()
        _last_result = result
        _last_run_at = datetime.now(timezone.utc)
        return {"status": "completed", "result": asdict(result)}
    except Exception as e:
        logger.exception("Ingestion run failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _running = False


@router.get("/status")
async def get_status():
    return {
        "running": _running,
        "last_result": asdict(_last_result) if _last_result else None,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
    }


@router.get("/feeds")
async def list_feeds():
    try:
        feeds = load_feeds()
        return {"feeds": feeds}
    except FileNotFoundError:
        return {"feeds": [], "error": "feeds.json not found"}
