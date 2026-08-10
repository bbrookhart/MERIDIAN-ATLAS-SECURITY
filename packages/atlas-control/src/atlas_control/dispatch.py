"""Unified tool dispatch — the only place a tool (native or MCP) actually
executes. Called exclusively by plan.execute_step() after policy.authorize()
and capability.redeem() have both succeeded for this exact step.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import httpx

from atlas_control import mcp_client
from atlas_control.config import settings
from atlas_control.tools import native

NATIVE_TOOL_NAMES = {"lookup_claim", "issue_refund", "send_email", "search_kb"}


async def available_tools() -> tuple[list[dict], dict[str, str]]:
    """Native tool schemas plus every non-drifted MCP tool schema, and a
    routing table from MCP tool name -> its server URL.
    """
    from atlas_control.tools.schemas import NATIVE_TOOL_SCHEMAS

    tools = list(NATIVE_TOOL_SCHEMAS)
    routes: dict[str, str] = {}
    for url in (settings.mcp_ticketing_url, settings.mcp_docstore_url):
        for schema in await mcp_client.list_remote_tools(url):
            tools.append(schema)
            routes[schema["function"]["name"]] = url
    return tools, routes


async def dispatch(
    tool: str,
    args: dict,
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    caller_role: str,
    mcp_routes: dict[str, str],
) -> str:
    if tool == "lookup_claim":
        result: Any = await native.lookup_claim(pool, args["claim_number"])
    elif tool == "issue_refund":
        result = await native.issue_refund(args["claim_number"], args["amount_cents"])
    elif tool == "send_email":
        result = await native.send_email(args["to"], args["subject"], args["body"])
    elif tool == "search_kb":
        result = await native.search_kb(pool, http_client, args["query"], caller_role)
    elif tool in mcp_routes:
        return await mcp_client.call_remote_tool(mcp_routes[tool], tool, args)
    else:
        result = {"error": f"unknown tool {tool}"}
    return json.dumps(result)
