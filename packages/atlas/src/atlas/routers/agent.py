"""The agent loop, rewired (Project 3) to hold no tool code and no
credential of its own. Every tool invocation — native or MCP — goes through
atlas-control: this process has no DB connection or MCP client for
execution, only an HTTP client pointed at atlas-control.

Each iteration of the loop is one planning round: the model requests zero
or more tool calls, those become one Plan submitted to atlas-control for
policy authorization and hashing in one shot, and only the steps that were
approved are executed — in order, by index into that frozen plan. A tool
result feeding back into the *next* planning round is normal multi-turn
behavior; it cannot inject a new step into the round that's already been
frozen and is currently executing. See packages/atlas-control/README.md
for the full before/after architecture.
"""

import json

import asyncpg
import httpx
from atlas_detect.semconv import (
    ATTR_ATLAS_ROLE,
    ATTR_ATLAS_SESSION_ID,
    ATTR_OPERATION_NAME,
    ATTR_TOOL_NAME,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
)
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import memory, ollama_client
from atlas.config import settings
from atlas.prompts import build_system_prompt
from atlas.telemetry import tracer

router = APIRouter()

MAX_ITERATIONS = 6


class AgentRequest(BaseModel):
    session_id: str
    message: str
    seed: int | None = None
    temperature: float | None = None


class AgentResponse(BaseModel):
    reply: str


async def _available_tools(http_client: httpx.AsyncClient) -> list[dict]:
    resp = await http_client.get(f"{settings.control_base_url}/plan/_tools/available", timeout=30)
    resp.raise_for_status()
    return resp.json()["tools"]


async def _submit_plan(
    http_client: httpx.AsyncClient, session_id: str, role: str, steps: list[dict]
) -> dict:
    resp = await http_client.post(
        f"{settings.control_base_url}/plan",
        json={"session_id": session_id, "role": role, "steps": steps},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def _execute_step(http_client: httpx.AsyncClient, plan_id: str, step_index: int) -> dict:
    resp = await http_client.post(
        f"{settings.control_base_url}/plan/{plan_id}/steps/{step_index}/execute", timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def _tool_calls_to_steps(tool_calls: list[dict]) -> list[dict]:
    steps = []
    for call in tool_calls:
        args = call["function"].get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args) if args else {}
        steps.append({"tool": call["function"]["name"], "args": args})
    return steps


async def run_agent_turn(
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    session_id: str,
    caller_role: str,
    user_message: str,
    seed: int | None = None,
    temperature: float | None = None,
) -> str:
    with tracer.start_as_current_span(OP_INVOKE_AGENT) as agent_span:
        agent_span.set_attribute(ATTR_OPERATION_NAME, OP_INVOKE_AGENT)
        agent_span.set_attribute(ATTR_ATLAS_ROLE, caller_role)
        agent_span.set_attribute(ATTR_ATLAS_SESSION_ID, session_id)

        await memory.save_fact(pool, session_id, "user_message", user_message)

        tools = await _available_tools(http_client)

        messages: list[dict] = [{"role": "system", "content": build_system_prompt(caller_role)}]
        messages += await memory.load_recent_facts(pool, session_id)
        messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_ITERATIONS):
            response = await ollama_client.chat(
                http_client, messages, tools=tools, seed=seed, temperature=temperature
            )
            messages.append(response)
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                reply = response.get("content", "")
                await memory.save_fact(pool, session_id, "assistant_message", reply)
                return reply

            plan_result = await _submit_plan(
                http_client, session_id, caller_role, _tool_calls_to_steps(tool_calls)
            )
            plan_id = plan_result["plan_id"]

            for i, step_info in enumerate(plan_result["steps"]):
                with tracer.start_as_current_span(OP_EXECUTE_TOOL) as tool_span:
                    tool_span.set_attribute(ATTR_OPERATION_NAME, OP_EXECUTE_TOOL)
                    tool_span.set_attribute(ATTR_TOOL_NAME, step_info["tool"])
                    tool_span.set_attribute("atlas.tool.approved", step_info["approved"])
                    if step_info["approved"]:
                        exec_result = await _execute_step(http_client, plan_id, i)
                        content = exec_result["result"]
                    else:
                        tool_span.set_attribute("atlas.tool.denial_reason", step_info["reason"])
                        content = json.dumps({"error": f"denied by policy: {step_info['reason']}"})
                tool_message = {"role": "tool", "content": content}
                messages.append(tool_message)
                await memory.save_fact(pool, session_id, "tool_result", content)

        return "[max iterations reached]"


@router.post("/agent/act")
async def agent_act(
    request: Request,
    body: AgentRequest,
    x_atlas_role: str = Header(default="broker"),
) -> AgentResponse:
    pool = request.app.state.db_pool
    http_client = request.app.state.http_client
    reply = await run_agent_turn(
        pool,
        http_client,
        body.session_id,
        x_atlas_role,
        body.message,
        seed=body.seed,
        temperature=body.temperature,
    )
    return AgentResponse(reply=reply)
