"""Shared tool credential.

WEAKNESS (ASI03 — Agent Identity & Privilege Abuse): every tool the agent can
call — native and MCP alike — authenticates with this single, long-lived,
unscoped token. There is no per-tool, per-action, or time-limited credential,
so compromising any one tool call is equivalent to compromising all of them.
See WEAKNESSES.md.
"""

TOOL_CREDENTIAL = "atlas-service-account-static-token"
