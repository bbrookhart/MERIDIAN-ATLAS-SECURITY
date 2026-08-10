from fastapi import APIRouter

from atlas.config import settings

router = APIRouter()


@router.get("/version")
async def get_version() -> dict:
    """Build SHA endpoint — later projects pin findings to this value."""
    return {"build_sha": settings.build_sha, "service": "atlas"}
