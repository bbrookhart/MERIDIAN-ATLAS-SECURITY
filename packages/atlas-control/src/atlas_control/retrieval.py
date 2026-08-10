"""Ported from atlas.db.retrieval — unchanged on purpose.

Cross-role RAG authorization (WEAKNESSES.md weakness #1) is Project 2's
scope, not Project 3's. search_kb still has no per-role filter here; fixing
it is a different project's job.
"""

from __future__ import annotations

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
    del caller_role  # accepted for API shape, intentionally unused — see module docstring
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
