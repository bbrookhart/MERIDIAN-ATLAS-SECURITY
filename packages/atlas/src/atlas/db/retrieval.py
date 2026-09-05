from __future__ import annotations

import logging

import asyncpg
import httpx
from atlas_retrieval import (
    POSTFILTER_OVERFETCH_MULTIPLIER,
    PREFILTER_SQL,
    ChunkLogEntry,
    authorize_post,
    authorize_pre,
    verify_content_hash,
)

logger = logging.getLogger("atlas.corpus_integrity")


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


async def _search_prefiltered(
    pool: asyncpg.Pool, query_embedding: list[float], visible_roles: list[str], limit: int
) -> list[RetrievedChunk]:
    rows = await pool.fetch(PREFILTER_SQL, visible_roles, query_embedding, limit)
    return [_row_to_chunk(r) for r in rows]


def _verify_integrity(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Corpus integrity (Project 2): recompute each chunk's content hash and
    compare to what was recorded at ingestion. A mismatch means the row was
    written to outside the ingestion path — the only writer that's
    supposed to exist — and the chunk is excluded rather than served. This
    is a real, live check: see test_retrieval_authorization.py for a test
    that directly UPDATEs a row and confirms it gets caught here."""
    verified = []
    for chunk in chunks:
        if verify_content_hash(chunk.body, chunk.content_sha256):
            verified.append(chunk)
        else:
            logger.warning(
                "corpus integrity alert: content hash mismatch for chunk_id=%s "
                "source_doc_id=%s — excluded from results",
                chunk.chunk_id,
                chunk.source_doc_id,
            )
    return verified


class AuthorizedSearchResult:
    def __init__(
        self,
        chunks: list[RetrievedChunk],
        mode: str,
        candidate_chunk_ids: list[int],
        decisions: list[ChunkLogEntry],
    ) -> None:
        self.chunks = chunks
        self.mode = mode
        self.candidate_chunk_ids = candidate_chunk_ids
        self.decisions = decisions


async def authorized_search(
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    control_base_url: str,
    query_embedding: list[float],
    caller_role: str,
    mode: str,
    limit: int = 5,
) -> AuthorizedSearchResult:
    """The Project 2 boundary: every retrieval passes through here, and
    every chunk in the returned result has already been authorized by
    atlas-control's OPA policy (retrieval_authorization.rego) — never by
    the model, never by this process's own judgment. `mode` picks *when*
    that authorization runs relative to the vector search, not *whether*
    it runs.

    PRE-FILTER: resolve the caller's permitted `allowed_roles` set first
    (one atlas-control call), then run a SQL query that only ever ranks
    authorized candidates — the vector search itself never sees an
    unauthorized chunk. Candidate set == authorized set by construction.

    POST-FILTER: run a plain, unfiltered vector query over-fetched by
    POSTFILTER_OVERFETCH_MULTIPLIER (to compensate for expected denials),
    then ask atlas-control to decide each candidate, and keep only the
    authorized ones, capped at `limit`. See
    packages/atlas-retrieval/README.md for the measured latency/recall
    tradeoff and the timing-side-channel argument against defaulting to
    this mode.
    """
    if mode == "pre":
        visible_roles = await authorize_pre(http_client, control_base_url, caller_role)
        chunks = await _search_prefiltered(pool, query_embedding, visible_roles, limit)
        chunks = _verify_integrity(chunks)
        decisions = [
            ChunkLogEntry(c.chunk_id, c.allowed_roles, True, "role_in_allowed_roles")
            for c in chunks
        ]
        return AuthorizedSearchResult(chunks, "pre", [c.chunk_id for c in chunks], decisions)

    candidates = await search(
        pool, query_embedding, caller_role, limit=limit * POSTFILTER_OVERFETCH_MULTIPLIER
    )
    candidates = _verify_integrity(candidates)
    policy_decisions = await authorize_post(
        http_client,
        control_base_url,
        caller_role,
        [{"chunk_id": c.chunk_id, "allowed_roles": c.allowed_roles} for c in candidates],
    )
    decision_by_id = {d.chunk_id: d for d in policy_decisions}
    authorized = [c for c in candidates if decision_by_id[c.chunk_id].allow][:limit]
    log_decisions = [
        ChunkLogEntry(d.chunk_id, d.allowed_roles, d.allow, d.rule) for d in policy_decisions
    ]
    return AuthorizedSearchResult(
        authorized, "post", [c.chunk_id for c in candidates], log_decisions
    )
