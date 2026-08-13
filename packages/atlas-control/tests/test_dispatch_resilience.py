"""A transient MCP failure must degrade the tool list, not 500 the request.

Found live: `available_tools()` runs on every plan submission, and a
`MCPError: Connection closed` from one streamable-http session propagated
as an unhandled ExceptionGroup — returning 500 for the entire agent turn
and killing two separate 110-request measurement runs partway through.
"""

import pytest
from atlas_control import dispatch


async def test_unreachable_mcp_server_degrades_instead_of_raising(monkeypatch):
    async def boom(url: str):
        raise ExceptionGroup("unhandled errors in a TaskGroup", [RuntimeError("Connection closed")])

    monkeypatch.setattr(dispatch.mcp_client, "list_remote_tools", boom)

    tools, routes = await dispatch.available_tools()

    # Native tools survive; no MCP tools are offered, and nothing raised.
    assert {t["function"]["name"] for t in tools} == dispatch.NATIVE_TOOL_NAMES
    assert routes == {}


async def test_one_bad_server_does_not_hide_the_good_one(monkeypatch):
    calls: list[str] = []

    async def half_broken(url: str):
        calls.append(url)
        if len(calls) == 1:
            raise RuntimeError("Connection closed")
        return [{"type": "function", "function": {"name": "remote_tool", "description": "d"}}]

    monkeypatch.setattr(dispatch.mcp_client, "list_remote_tools", half_broken)

    tools, routes = await dispatch.available_tools()

    assert "remote_tool" in {t["function"]["name"] for t in tools}
    assert list(routes) == ["remote_tool"]


@pytest.mark.parametrize("exc", [RuntimeError("boom"), ExceptionGroup("g", [OSError("x")])])
async def test_both_bare_and_grouped_failures_are_handled(monkeypatch, exc):
    async def raise_it(url: str):
        raise exc

    monkeypatch.setattr(dispatch.mcp_client, "list_remote_tools", raise_it)

    tools, _ = await dispatch.available_tools()

    assert len(tools) == len(dispatch.NATIVE_TOOL_NAMES)
