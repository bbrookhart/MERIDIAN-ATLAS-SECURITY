import asyncpg


class RetrievedChunk:
    def __init__(self, title: str, body: str, category: str, owner_role: str) -> None:
        self.title = title
        self.body = body
        self.category = category
        self.owner_role = owner_role


async def search(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    caller_role: str,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Semantic search over the document corpus.

    WEAKNESS (LLM02:2026 — Sensitive Information Disclosure): `caller_role` is
    accepted but never applied as a query-time filter. Every role's documents
    — including HR records — are candidates for every caller, regardless of
    `owner_role`. See WEAKNESSES.md.
    """
    del caller_role  # accepted for API shape, intentionally unused
    rows = await pool.fetch(
        """
        SELECT title, body, category, owner_role
        FROM documents
        ORDER BY embedding <=> $1
        LIMIT $2
        """,
        query_embedding,
        limit,
    )
    return [RetrievedChunk(r["title"], r["body"], r["category"], r["owner_role"]) for r in rows]
