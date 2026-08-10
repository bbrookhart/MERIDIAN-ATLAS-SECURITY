from fastapi import APIRouter, Request
from pydantic import BaseModel

from atlas_control import approval, ollama_client

router = APIRouter(prefix="/approval")


class CompareRequest(BaseModel):
    session_id: str
    tool: str = "issue_refund"
    claim_number: str
    amount_cents: int
    threshold_cents: int
    verbatim_user_message: str
    agent_rationale: str


class OutcomeOut(BaseModel):
    design: str
    approved: bool
    judge_raw_response: str


class CompareResponse(BaseModel):
    naive: OutcomeOut
    hardened: OutcomeOut


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest, request: Request) -> CompareResponse:
    http_client = request.app.state.http_client

    async def judge(prompt: str) -> str:
        return await ollama_client.chat(http_client, prompt)

    scenario = approval.ApprovalScenario(
        session_id=body.session_id,
        tool=body.tool,
        claim_number=body.claim_number,
        amount_cents=body.amount_cents,
        threshold_cents=body.threshold_cents,
        verbatim_user_message=body.verbatim_user_message,
        agent_rationale=body.agent_rationale,
    )
    naive, hardened = await approval.run_comparison(scenario, judge)
    return CompareResponse(
        naive=OutcomeOut(**naive.__dict__),
        hardened=OutcomeOut(**hardened.__dict__),
    )
