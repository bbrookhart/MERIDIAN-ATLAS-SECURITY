"""Agent memory, with provenance (Project 3 / ASI06 — Memory & Context
Poisoning).

Every stored fact carries where it came from (source), how much it should
be trusted (trust_tier), which turn wrote it (run_id), and when it expires
(TTL). load_recent_facts() is scoped to one session_id — this, not trust
tiering, is what closes the cross-session leak Project 3's Phase A
red-team run demonstrated live: a fact planted in one session can no
longer influence a different session's agent turn at all, regardless of
trust tier.

Trust tiering is the second, narrower defense: content whose source is
`user_input` or `tool_result` is marked `untrusted` and is never given
elevated standing in the conversation — it's loaded back as ordinary
`user`/`tool` role messages, the same as it always was, never promoted to
a `system` role. `assistant_output` is `trusted`. This module simply never
provides a code path that could promote untrusted content to system/
instruction level; there's nothing to bypass because it doesn't exist.
"""

from __future__ import annotations

import uuid

import asyncpg

DEFAULT_TTL_SECONDS = 3600

_SOURCE_BY_KIND = {
    "user_message": "user_input",
    "assistant_message": "assistant_output",
    "tool_result": "tool_result",
}
_TRUST_TIER_BY_SOURCE = {
    "user_input": "untrusted",
    "assistant_output": "trusted",
    "tool_result": "untrusted",
}
_ROLE_BY_KIND = {
    "user_message": "user",
    "assistant_message": "assistant",
    "tool_result": "tool",
}


async def save_fact(
    pool: asyncpg.Pool,
    session_id: str,
    kind: str,
    content: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    source = _SOURCE_BY_KIND.get(kind, "user_input")
    trust_tier = _TRUST_TIER_BY_SOURCE[source]
    run_id = uuid.uuid4().hex
    await pool.execute(
        """
        INSERT INTO agent_memory
            (session_id, kind, content, source, trust_tier, run_id, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, now() + make_interval(secs => $7))
        """,
        session_id,
        kind,
        content,
        source,
        trust_tier,
        run_id,
        ttl_seconds,
    )


async def load_recent_facts(pool: asyncpg.Pool, session_id: str, limit: int = 20) -> list[dict]:
    """Load recent memory for exactly one session — never across sessions,
    and never anything past its TTL.
    """
    rows = await pool.fetch(
        """
        SELECT kind, content FROM agent_memory
        WHERE session_id = $1 AND expires_at > now()
        ORDER BY created_at DESC
        LIMIT $2
        """,
        session_id,
        limit,
    )
    return [
        {"role": _ROLE_BY_KIND.get(r["kind"], "user"), "content": r["content"]}
        for r in reversed(rows)
    ]


async def list_memory_with_provenance(pool: asyncpg.Pool, session_id: str) -> list[dict]:
    """Every stored fact for one session, with full provenance —
    including expired rows, unlike load_recent_facts (which is the
    prompt-assembly path, not an audit path). Project 4's memory-
    poisoning detector reads this to correlate untrusted-tier writes
    against later privileged tool calls in the same session."""
    rows = await pool.fetch(
        """
        SELECT kind, content, source, trust_tier, run_id, created_at, expires_at
        FROM agent_memory
        WHERE session_id = $1
        ORDER BY created_at ASC
        """,
        session_id,
    )
    return [
        {
            "kind": r["kind"],
            "content": r["content"],
            "source": r["source"],
            "trust_tier": r["trust_tier"],
            "run_id": r["run_id"],
            "created_at": r["created_at"].isoformat(),
            "expires_at": r["expires_at"].isoformat(),
        }
        for r in rows
    ]
