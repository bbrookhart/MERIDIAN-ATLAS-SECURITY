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


async def list_decisions(
    pool: asyncpg.Pool,
    role: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query interface for the decision log (EU AI Act Article 12 evidence)
    — e.g. "on 3 August, which HR documents did the broker-facing
    assistant see, and who authorized that": role="broker",
    since="2026-08-03", until="2026-08-04"."""
    conditions: list[str] = []
    args: list = []
    if role:
        args.append(role)
        conditions.append(f"caller_role = ${len(args)}")
    if since:
        args.append(since)
        conditions.append(f"occurred_at >= ${len(args)}::timestamptz")
    if until:
        args.append(until)
        conditions.append(f"occurred_at < ${len(args)}::timestamptz")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    args.append(limit)

    rows = await pool.fetch(
        f"""
        SELECT id, request_id, occurred_at, caller_role, caller_session_id, query_hash,
               mode, candidate_chunk_ids, decisions, context_chunk_ids, redactions_applied,
               response_hash
        FROM retrieval_decisions
        {where}
        ORDER BY occurred_at DESC
        LIMIT ${len(args)}
        """,
        *args,
    )
    results = []
    for r in rows:
        row = dict(r)
        row["occurred_at"] = row["occurred_at"].isoformat()
        row["decisions"] = json.loads(row["decisions"])
        row["redactions_applied"] = json.loads(row["redactions_applied"])
        results.append(row)
    return results
