import asyncpg


async def save_fact(pool: asyncpg.Pool, session_id: str, kind: str, content: str) -> None:
    await pool.execute(
        "INSERT INTO agent_memory (session_id, kind, content) VALUES ($1, $2, $3)",
        session_id,
        kind,
        content,
    )


async def load_recent_facts(pool: asyncpg.Pool, limit: int = 20) -> list[dict]:
    """Load recent conversational memory to seed a new agent turn.

    WEAKNESS (ASI06 — Memory & Context Poisoning): facts are loaded across
    *all* sessions, not filtered by the current session_id, and carry no
    provenance (who said it, which session, whether it came from a trusted
    caller). A fact planted by any user in any session can influence any
    other session's agent turn. See WEAKNESSES.md.
    """
    rows = await pool.fetch(
        "SELECT kind, content FROM agent_memory ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    role_by_kind = {
        "user_message": "user",
        "assistant_message": "assistant",
        "tool_result": "tool",
    }
    return [
        {"role": role_by_kind.get(r["kind"], "user"), "content": r["content"]}
        for r in reversed(rows)
    ]
