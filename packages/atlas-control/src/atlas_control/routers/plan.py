from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from atlas_control import dispatch, plan, staged_commit

router = APIRouter(prefix="/plan")


class PlanStepIn(BaseModel):
    tool: str
    args: dict = {}


class SubmitPlanRequest(BaseModel):
    session_id: str
    role: str
    steps: list[PlanStepIn]


class PlanStepOut(BaseModel):
    tool: str
    args: dict
    approved: bool
    reason: str


class SubmitPlanResponse(BaseModel):
    plan_id: str
    plan_hash: str
    steps: list[PlanStepOut]


@router.post("", response_model=SubmitPlanResponse)
async def submit_plan(body: SubmitPlanRequest) -> SubmitPlanResponse:
    p = plan.submit_plan(body.session_id, body.role, [s.model_dump() for s in body.steps])
    return SubmitPlanResponse(
        plan_id=p.plan_id,
        plan_hash=p.plan_hash,
        steps=[
            PlanStepOut(tool=s.tool, args=s.args, approved=d.approved, reason=d.reason)
            for s, d in zip(p.steps, p.decisions, strict=True)
        ],
    )


class ExecuteStepResponse(BaseModel):
    tool: str
    args: dict
    result: str
    staged_commit_id: str | None = None


@router.post("/{plan_id}/steps/{step_index}/execute", response_model=ExecuteStepResponse)
async def execute_step(plan_id: str, step_index: int, request: Request) -> ExecuteStepResponse:
    pool = request.app.state.db_pool
    http_client = request.app.state.http_client
    try:
        step, result = await plan.execute_step(plan_id, step_index, pool, http_client)
    except plan.PlanDeviationError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    staged_id = None
    if step.tool in staged_commit.STAGED_TOOLS:
        p = plan.get_plan(plan_id)
        action = staged_commit.stage(p.session_id, step.tool, step.args, {"raw": result})
        staged_id = action.commit_id

    return ExecuteStepResponse(
        tool=step.tool, args=step.args, result=result, staged_commit_id=staged_id
    )


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict:
    p = plan.get_plan(plan_id)
    if p is None:
        raise HTTPException(status_code=404, detail="unknown plan_id")
    return {
        "plan_id": p.plan_id,
        "plan_hash": p.plan_hash,
        "session_id": p.session_id,
        "steps": [
            {
                "tool": s.tool,
                "args": s.args,
                "approved": d.approved,
                "reason": d.reason,
                "executed": ex,
            }
            for s, d, ex in zip(p.steps, p.decisions, p.executed, strict=True)
        ],
    }


@router.get("/_tools/available")
async def available_tools() -> dict:
    tools, _routes = await dispatch.available_tools()
    return {"tools": tools}
