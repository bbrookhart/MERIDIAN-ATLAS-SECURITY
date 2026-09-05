"""Executes atlas_retrieval's decision-log SQL against Atlas's own Postgres
pool. The SQL text and payload shape live in atlas_retrieval (pure, unit
testable); this module is just the thin asyncpg glue.
"""

from __future__ import annotations

import json

import asyncpg
from atlas_retrieval import INSERT_SQL, UPDATE_RESPONSE_HASH_SQL, ChunkLogEntry, decisions_to_jsonb


async def insert_decision_log(
    pool: asyncpg.Pool,
    request_id: str,
    caller_role: str,
    caller_session_id: str | None,
    query_hash: str,
    mode: str,
    candidate_chunk_ids: list[int],
    decisions: list[ChunkLogEntry],
    context_chunk_ids: list[int],
    redactions_applied: list[str],
) -> int:
    row = await pool.fetchrow(
        INSERT_SQL,
        request_id,
        caller_role,
        caller_session_id,
        query_hash,
        mode,
        candidate_chunk_ids,
        json.dumps(decisions_to_jsonb(decisions)),
        context_chunk_ids,
        json.dumps(redactions_applied),
    )
    return row["id"]


async def update_response_hash(pool: asyncpg.Pool, log_id: int, response_hash: str) -> None:
    await pool.execute(UPDATE_RESPONSE_HASH_SQL, response_hash, log_id)
