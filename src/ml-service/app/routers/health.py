from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "qdrant": "not_connected",
        "database": "not_connected",
    }
