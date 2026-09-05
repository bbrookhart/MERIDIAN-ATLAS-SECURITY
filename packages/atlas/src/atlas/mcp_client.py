"""MCP client helpers used by the /agent tool loop.

Connects to the two real MCP servers (mcp-ticketing, mcp-docstore) over the
streamable-HTTP transport, discovers their tools, and dispatches tool calls.
"""

from contextlib import asynccontextmanager
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ToolSchema = dict[str, Any]


@asynccontextmanager
async def _session(url: str, credential: str | None = None):
    headers = {"Authorization": f"Bearer {credential}"} if credential else {}
    async with (
        httpx2.AsyncClient(headers=headers) as http_client,
        streamable_http_client(url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


async def list_remote_tools(url: str) -> list[ToolSchema]:
    """Fetch tool schemas from one MCP server.

    WEAKNESS (ASI04 — Agentic Supply Chain Compromise): each tool's
    description is forwarded to the model verbatim, exactly as the server
    reports it, with no hashing, pinning, or drift detection. A compromised
    or malicious MCP server can rewrite its tool descriptions at any time and
    this client will trust the new text unconditionally. See WEAKNESSES.md.
    """
    async with _session(url) as session:
        result = await session.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in result.tools
    ]


async def call_remote_tool(url: str, name: str, arguments: dict[str, Any], credential: str) -> str:
    """Call a tool on a remote MCP server.

    WEAKNESS (ASI03 — Agent Identity & Privilege Abuse): `credential` is the
    same shared, unscoped token used for every native and MCP tool call — see
    credentials.py. The mock servers here don't even verify it; a real
    ticketing/document-store integration would, and a leaked or replayed
    copy of this one token would authorize every tool, everywhere.
    """
    async with _session(url, credential) as session:
        result = await session.call_tool(name, arguments)
    parts = [block.text for block in result.content if block.type == "text"]
    return "\n".join(parts) if parts else ""
