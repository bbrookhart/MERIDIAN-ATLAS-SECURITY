"""MCP client with tool-description hash-pinning and drift detection —
MCP03:2025 (Tool Poisoning) from the OWASP MCP Top 10 (fetched live from
owasp.org/www-project-mcp-top-10, 2026-08-10; it's a beta, verify before
citing elsewhere).

Ported from atlas.mcp_client (WEAKNESSES.md weakness #6: "MCP tool
descriptions are trusted verbatim from the server"). The old, unpinned
version is deleted from the atlas package, not kept as dead code — its
before-state behavior is preserved forever in Project 1's committed
red-team findings, not in a second unused copy of this module.

A tool's description is trusted on first registration (pinned) and
compared on every subsequent discovery; a changed description is a security
event, not new information for the planner. This client does not merely
warn on drift — it excludes the drifted tool from what the planner sees at
all, fail closed.
"""

from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger("atlas_control.mcp_trust")

ToolSchema = dict[str, Any]

# server_url -> tool_name -> sha256(description)
_pinned_hashes: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class DriftEvent:
    server_url: str
    tool_name: str
    pinned_hash: str
    observed_hash: str


_drift_log: list[DriftEvent] = []


def drift_events() -> list[DriftEvent]:
    return list(_drift_log)


def _hash_description(description: str) -> str:
    return hashlib.sha256(description.encode()).hexdigest()


def _check_and_pin(server_url: str, tool_name: str, description: str) -> bool:
    """Returns True if the tool is trusted (newly pinned or matches its
    pin), False if it drifted and should be excluded.
    """
    observed = _hash_description(description)
    server_pins = _pinned_hashes.setdefault(server_url, {})
    pinned = server_pins.get(tool_name)

    if pinned is None:
        server_pins[tool_name] = observed
        return True

    if pinned != observed:
        event = DriftEvent(server_url, tool_name, pinned, observed)
        _drift_log.append(event)
        logger.warning(
            "MCP03:2025 tool-poisoning signal: %s on %s changed description "
            "(pinned=%s observed=%s) — excluding from planner",
            tool_name,
            server_url,
            pinned[:12],
            observed[:12],
        )
        return False

    return True


@asynccontextmanager
async def _session(url: str):
    async with (
        httpx2.AsyncClient() as http_client,
        streamable_http_client(url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


async def list_remote_tools(url: str) -> list[ToolSchema]:
    async with _session(url) as session:
        result = await session.list_tools()

    trusted: list[ToolSchema] = []
    for tool in result.tools:
        description = tool.description or ""
        if not _check_and_pin(url, tool.name, description):
            continue
        trusted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": description,
                    "parameters": tool.input_schema,
                },
            }
        )
    return trusted


async def call_remote_tool(url: str, name: str, arguments: dict[str, Any]) -> str:
    async with _session(url) as session:
        result = await session.call_tool(name, arguments)
    parts = [block.text for block in result.content if block.type == "text"]
    return "\n".join(parts) if parts else ""
