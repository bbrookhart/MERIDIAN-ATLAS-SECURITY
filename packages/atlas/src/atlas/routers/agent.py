import json
from typing import Any

import asyncpg
import httpx
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from atlas import mcp_client, memory, ollama_client
from atlas.config import settings
from atlas.credentials import TOOL_CREDENTIAL
from atlas.prompts import build_system_prompt
from atlas.tools.issue_refund import issue_refund
from atlas.tools.lookup_claim import lookup_claim
from atlas.tools.schemas import NATIVE_TOOL_SCHEMAS
from atlas.tools.search_kb import search_kb
from atlas.tools.send_email import send_email

router = APIRouter()

MAX_ITERATIONS = 6
NATIVE_TOOL_NAMES = {"lookup_claim", "issue_refund", "send_email", "search_kb"}


class AgentRequest(BaseModel):
    session_id: str
    message: str


class AgentResponse(BaseModel):
    reply: str


async def _remote_tools_and_routes(
    http_client: httpx.AsyncClient,
) -> tuple[list[dict], dict[str, str]]:
    del http_client  # MCP client manages its own httpx client internally
    tools: list[dict] = []
    routes: dict[str, str] = {}
    for url in (settings.mcp_ticketing_url, settings.mcp_docstore_url):
        for schema in await mcp_client.list_remote_tools(url):
            tools.append(schema)
            routes[schema["function"]["name"]] = url
    return tools, routes


async def _dispatch_native(
    name: str,
    args: dict[str, Any],
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    caller_role: str,
) -> str:
    # WEAKNESS (ASI03): the same shared, unscoped TOOL_CREDENTIAL is passed to
    # every native tool call, regardless of which action it authorizes.
    if name == "lookup_claim":
        result = await lookup_claim(pool, args["claim_number"], TOOL_CREDENTIAL)
    elif name == "issue_refund":
        result = await issue_refund(args["claim_number"], args["amount"], TOOL_CREDENTIAL)
    elif name == "send_email":
        result = await send_email(args["to"], args["subject"], args["body"], TOOL_CREDENTIAL)
    elif name == "search_kb":
        result = await search_kb(pool, http_client, args["query"], caller_role, TOOL_CREDENTIAL)
    else:  # pragma: no cover — guarded by NATIVE_TOOL_NAMES membership check
        result = {"error": f"unknown native tool {name}"}
    return json.dumps(result)


async def dispatch_tool_call(
    call: dict,
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    remote_routes: dict[str, str],
    caller_role: str,
) -> dict:
    name = call["function"]["name"]
    args = call["function"].get("arguments", {})
    if isinstance(args, str):
        args = json.loads(args) if args else {}

    if name in NATIVE_TOOL_NAMES:
        content = await _dispatch_native(name, args, pool, http_client, caller_role)
    elif name in remote_routes:
        # Same shared credential crosses the MCP boundary too — see mcp_client.py.
        content = await mcp_client.call_remote_tool(
            remote_routes[name], name, args, TOOL_CREDENTIAL
        )
    else:
        content = json.dumps({"error": f"unknown tool {name}"})

    return {"role": "tool", "content": content}


async def run_agent_turn(
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    session_id: str,
    caller_role: str,
    user_message: str,
) -> str:
    await memory.save_fact(pool, session_id, "user_message", user_message)

    remote_tools, remote_routes = await _remote_tools_and_routes(http_client)
    tools = NATIVE_TOOL_SCHEMAS + remote_tools

    messages: list[dict] = [{"role": "system", "content": build_system_prompt(caller_role)}]
    messages += await memory.load_recent_facts(pool)
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_ITERATIONS):
        response = await ollama_client.chat(http_client, messages, tools=tools)
        messages.append(response)
        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            reply = response.get("content", "")
            await memory.save_fact(pool, session_id, "assistant_message", reply)
            return reply
        for call in tool_calls:
            tool_message = await dispatch_tool_call(
                call, pool, http_client, remote_routes, caller_role
            )
            messages.append(tool_message)
            await memory.save_fact(pool, session_id, "tool_result", tool_message["content"])

    return "[max iterations reached]"


@router.post("/agent/act")
async def agent_act(
    request: Request,
    body: AgentRequest,
    x_atlas_role: str = Header(default="broker"),
) -> AgentResponse:
    pool = request.app.state.db_pool
    http_client = request.app.state.http_client
    reply = await run_agent_turn(pool, http_client, body.session_id, x_atlas_role, body.message)
    return AgentResponse(reply=reply)
