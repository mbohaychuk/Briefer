import logging
import threading
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.reasoning.models import ScoringResult
from app.reasoning.pipeline import get_scoring_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scoring", tags=["scoring"])

_last_results: list[dict] | None = None
_last_run_at: datetime | None = None
_lock = threading.Lock()

# Module-level profile list, set during lifespan
_profiles = []


def set_profiles(profiles):
    global _profiles
    _profiles = profiles


def get_profiles():
    return _profiles


@router.post("/trigger")
async def trigger_scoring():
    global _last_results, _last_run_at

    if not _lock.acquire(blocking=False):
        return {"status": "already_running"}

    try:
        pipeline = get_scoring_pipeline()
        profiles = get_profiles()

        results = []
        for profile in profiles:
            result = pipeline.run(profile)
            results.append(asdict(result))

        _last_results = results
        _last_run_at = datetime.now(timezone.utc)
        return {"status": "completed", "results": results}
    except Exception:
        logger.exception("Scoring run failed")
        raise HTTPException(status_code=500, detail="Internal error during scoring")
    finally:
        _lock.release()


@router.get("/status")
async def get_status():
    return {
        "running": _lock.locked(),
        "last_results": _last_results,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
    }
