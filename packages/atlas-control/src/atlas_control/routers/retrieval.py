from fastapi import APIRouter
from pydantic import BaseModel

from atlas_control.retrieval_policy import authorize_retrieval

router = APIRouter(prefix="/retrieval")


class ChunkIn(BaseModel):
    chunk_id: int
    allowed_roles: list[str]


class AuthorizeRequest(BaseModel):
    role: str
    mode: str  # "pre" | "post"
    chunks: list[ChunkIn] | None = None


@router.post("/authorize")
async def authorize(body: AuthorizeRequest) -> dict:
    chunks = [c.model_dump() for c in body.chunks] if body.chunks else None
    result = authorize_retrieval(body.role, chunks)
    if body.mode == "pre":
        return {"visible_roles": result.visible_roles}
    return {"decisions": result.decisions}
