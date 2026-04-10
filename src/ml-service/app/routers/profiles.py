import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

# Module-level references, set during lifespan
_profile_loader = None
_on_profiles_updated = None


def set_profile_loader(loader):
    global _profile_loader
    _profile_loader = loader


def set_on_profiles_updated(callback):
    """Register a callback invoked after profiles are reloaded.

    The callback receives the full list of UserProfile objects so that
    routers (scoring, briefing) can be updated.
    """
    global _on_profiles_updated
    _on_profiles_updated = callback


class InterestBlockInput(BaseModel):
    label: str
    text: str


class ProfileInput(BaseModel):
    user_id: str
    name: str
    interests: list[InterestBlockInput]


class SyncRequest(BaseModel):
    profiles: list[ProfileInput]


@router.post("/sync")
async def sync_profiles(request: SyncRequest):
    """Accept profile data from the web API and rebuild in-memory profiles."""
    if _profile_loader is None:
        raise HTTPException(status_code=503, detail="Profile loader not initialized")

    try:
        data = {
            "profiles": [p.model_dump() for p in request.profiles]
        }
        profiles = _profile_loader.load_from_dict(data)

        if _on_profiles_updated:
            _on_profiles_updated(profiles)

        logger.info("Synced %d profiles from web API", len(profiles))
        return {
            "status": "ok",
            "profiles_synced": len(profiles),
        }
    except Exception:
        logger.exception("Profile sync failed")
        raise HTTPException(status_code=500, detail="Profile sync failed")
