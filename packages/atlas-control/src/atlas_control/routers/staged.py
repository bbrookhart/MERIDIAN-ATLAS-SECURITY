from fastapi import APIRouter, HTTPException

from atlas_control import staged_commit

router = APIRouter(prefix="/staged")


@router.get("/{commit_id}")
async def get_staged(commit_id: str) -> dict:
    action = staged_commit.get(commit_id)
    if action is None:
        raise HTTPException(status_code=404, detail="unknown commit_id")
    return {
        "commit_id": action.commit_id,
        "tool": action.tool,
        "args": action.args,
        "status": action.status,
        "rollback_deadline": action.rollback_deadline,
    }


@router.post("/{commit_id}/void")
async def void_staged(commit_id: str) -> dict:
    try:
        action = staged_commit.void(commit_id)
    except staged_commit.UnknownStagedActionError as e:
        raise HTTPException(status_code=404, detail="unknown commit_id") from e
    except staged_commit.RollbackWindowExpiredError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"commit_id": action.commit_id, "status": action.status}
