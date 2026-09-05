from fastapi import APIRouter

from atlas_control import budget

router = APIRouter(prefix="/budget")


@router.get("/{session_id}")
async def get_budget(session_id: str) -> dict:
    snap = budget.snapshot(session_id)
    return {
        "session_id": snap.session_id,
        "tool_calls_used": snap.tool_calls_used,
        "refund_cents_used": snap.refund_cents_used,
    }
