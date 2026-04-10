import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.briefing.repository import BriefingRepository
from app.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefing", tags=["briefing"])

# Module-level references, set during lifespan
_generator = None
_profiles = []


def set_generator(generator):
    global _generator
    _generator = generator


def set_profiles(profiles):
    global _profiles
    _profiles = profiles


def get_profiles():
    return _profiles


def _find_profile(user_id: UUID):
    for p in _profiles:
        if p.user_id == user_id:
            return p
    return None


def _briefing_to_dict(briefing):
    return {
        "id": str(briefing.id),
        "user_id": str(briefing.user_id),
        "status": briefing.status,
        "article_count": briefing.article_count,
        "executive_summary": briefing.executive_summary,
        "profile_version": briefing.profile_version,
        "generated_at": briefing.generated_at.isoformat() if briefing.generated_at else None,
        "created_at": briefing.created_at.isoformat() if briefing.created_at else None,
        "articles": [
            {
                "article_id": str(a.article_id),
                "title": a.title,
                "source_name": a.source_name,
                "url": a.url,
                "rank": a.rank,
                "display_score": a.display_score,
                "summary": a.summary,
                "priority": a.priority,
                "explanation": a.explanation,
            }
            for a in briefing.articles
        ],
    }


@router.post("/generate")
async def generate_briefing(user_id: str):
    """Generate a new briefing for a user from their ready articles."""
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    profile = _find_profile(uid)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    conn = get_connection()
    try:
        repo = BriefingRepository(conn)

        # Create a pending briefing
        briefing_id = repo.create_briefing(uid)

        # Snapshot ready articles into the briefing and mark as briefed
        articles = repo.add_articles(briefing_id, uid)

        if not articles:
            repo.mark_failed(briefing_id)
            repo.commit()
            briefing = repo.get_briefing(briefing_id)
            return _briefing_to_dict(briefing)

        # Generate executive summary (graceful degradation on failure)
        summary = None
        if _generator:
            summary = _generator.generate_summary(articles, profile)

        if summary:
            repo.complete_briefing(briefing_id, summary)
        else:
            repo.mark_failed(briefing_id)

        repo.commit()

        briefing = repo.get_briefing(briefing_id)
        return _briefing_to_dict(briefing)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Briefing generation failed")
        raise HTTPException(
            status_code=500, detail="Internal error during briefing generation"
        )
    finally:
        conn.close()


@router.get("/latest/{user_id}")
async def get_latest_briefing(user_id: str):
    """Get the most recent briefing for a user."""
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    conn = get_connection()
    try:
        repo = BriefingRepository(conn)
        briefing = repo.get_latest(uid)
        if not briefing:
            raise HTTPException(status_code=404, detail="No briefings found")
        return _briefing_to_dict(briefing)
    finally:
        conn.close()


@router.get("/history/{user_id}")
async def get_briefing_history(user_id: str, limit: int = 30):
    """Get recent briefing metadata for a user."""
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    conn = get_connection()
    try:
        repo = BriefingRepository(conn)
        return repo.get_history(uid, limit=limit)
    finally:
        conn.close()


@router.get("/{briefing_id}")
async def get_briefing(briefing_id: str):
    """Get a specific briefing by ID."""
    try:
        bid = UUID(briefing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid briefing_id format")

    conn = get_connection()
    try:
        repo = BriefingRepository(conn)
        briefing = repo.get_briefing(bid)
        if not briefing:
            raise HTTPException(status_code=404, detail="Briefing not found")
        return _briefing_to_dict(briefing)
    finally:
        conn.close()
