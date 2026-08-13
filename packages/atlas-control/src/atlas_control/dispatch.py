"""Unified tool dispatch — the only place a tool (native or MCP) actually
executes. Called exclusively by plan.execute_step() after policy.authorize()
and capability.redeem() have both succeeded for this exact step.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg
import httpx

from atlas_control import mcp_client
from atlas_control.config import settings
from atlas_control.tools import native

logger = logging.getLogger("atlas_control.dispatch")

NATIVE_TOOL_NAMES = {"lookup_claim", "issue_refund", "send_email", "search_kb"}


async def available_tools() -> tuple[list[dict], dict[str, str]]:
    """Native tool schemas plus every non-drifted MCP tool schema, and a
    routing table from MCP tool name -> its server URL.

    An unreachable MCP server degrades the tool list; it does not fail the
    request. Found the hard way: this function runs on *every* plan
    submission, and a transient `MCPError: Connection closed` from one
    streamable-http session propagated as an unhandled ExceptionGroup, so a
    single dropped MCP connection returned 500 for the whole agent turn.
    That killed two separate 110-request measurement runs partway through.

    Degrading is also the safer behaviour, not just the more available one:
    a tool that cannot be discovered is simply not offered to the planner,
    and policy still has to authorize whatever *is* offered. This is the
    same fail-closed posture as `_check_and_pin` excluding a drifted tool —
    the tool disappears rather than being trusted or crashing the caller.
    """
    from atlas_control.tools.schemas import NATIVE_TOOL_SCHEMAS

    tools = list(NATIVE_TOOL_SCHEMAS)
    routes: dict[str, str] = {}
    for url in (settings.mcp_ticketing_url, settings.mcp_docstore_url):
        try:
            # ExceptionGroup subclasses Exception, so this catches both the
            # bare MCPError and the TaskGroup-wrapped form the streamable-http
            # client actually raises. (`except*` would be the idiomatic match
            # for the group, but PEP 654 forbids `continue` inside it.)
            schemas = await mcp_client.list_remote_tools(url)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any MCP
            # transport failure must degrade the tool list rather than 500 the
            # request, and the streamable-http client wraps failures in a
            # TaskGroup ExceptionGroup whose contents aren't a fixed set.
            logger.warning(
                "MCP discovery failed for %s (%s) — continuing without its tools",
                url,
                exc,
            )
            continue
        for schema in schemas:
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
