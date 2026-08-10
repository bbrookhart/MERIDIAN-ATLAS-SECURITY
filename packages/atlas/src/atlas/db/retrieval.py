import asyncpg


class RetrievedChunk:
    def __init__(
        self,
        chunk_id: int,
        title: str,
        body: str,
        category: str,
        owner_role: str,
        allowed_roles: list[str],
        source_doc_id: str | None,
        content_sha256: str,
    ) -> None:
        self.chunk_id = chunk_id
        self.title = title
        self.body = body
        self.category = category
        self.owner_role = owner_role
        self.allowed_roles = allowed_roles
        self.source_doc_id = source_doc_id
        self.content_sha256 = content_sha256


def _row_to_chunk(r) -> RetrievedChunk:
    return RetrievedChunk(
        r["id"],
        r["title"],
        r["body"],
        r["category"],
        r["owner_role"],
        list(r["allowed_roles"]),
        r["source_doc_id"],
        r["content_sha256"],
    )


async def search(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    caller_role: str,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Semantic search over the document corpus.

    WEAKNESS (LLM02:2026 — Sensitive Information Disclosure, open —
    Project 2 Phase A before-state): `caller_role` is accepted but never
    applied as a query-time filter. Every role's documents — including HR
    records — are candidates for every caller, regardless of
    `allowed_roles`. Project 2 Phase B replaces this call site's caller
    (atlas.routers.rag.rag_query) with a pre/post-filter orchestrator that
    asks atlas-control who's authorized before returning anything; this
    function itself stays a plain, unfiltered vector query — the boundary
    is enforced by the caller, not hidden inside this helper. See
    WEAKNESSES.md.
    """
    del caller_role  # accepted for API shape, intentionally unused
    rows = await pool.fetch(
        """
        SELECT id, title, body, category, owner_role, allowed_roles, source_doc_id, content_sha256
        FROM documents
        ORDER BY embedding <=> $1
        LIMIT $2
        """,
        query_embedding,
        limit,
    )
    return [_row_to_chunk(r) for r in rows]
