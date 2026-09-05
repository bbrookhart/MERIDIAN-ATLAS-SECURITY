"""Retrieval decision log — the Project 2 headline deliverable.

An append-only record of every retrieval: who asked, what was a candidate,
what was authorized and by which rule, what actually reached the context
window, and (once available) a hash of the model's reply. This is what
answers an EU AI Act Article 12 record-keeping question after the fact —
"on 3 August, which HR documents did the broker-facing assistant see, and
who authorized that" — without needing to trust anyone's memory of what
happened.

Hashing only, never the raw query or reply text: the log proves *what
happened*, it doesn't become a second copy of the corpus or the
conversation to protect.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkLogEntry:
    chunk_id: int
    allowed_roles: list[str]
    allow: bool
    rule: str


@dataclass(frozen=True)
class DecisionLogEntry:
    request_id: str
    caller_role: str
    caller_session_id: str | None
    query_hash: str
    mode: str  # "none" | "pre" | "post"
    candidate_chunk_ids: list[int]
    decisions: list[ChunkLogEntry]
    context_chunk_ids: list[int]
    redactions_applied: list[str] = field(default_factory=list)


INSERT_SQL = """
INSERT INTO retrieval_decisions
    (request_id, caller_role, caller_session_id, query_hash, mode,
     candidate_chunk_ids, decisions, context_chunk_ids, redactions_applied)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
RETURNING id
"""

UPDATE_RESPONSE_HASH_SQL = """
UPDATE retrieval_decisions SET response_hash = $1 WHERE id = $2
"""


def decisions_to_jsonb(decisions: list[ChunkLogEntry]) -> list[dict]:
    return [
        {
            "chunk_id": d.chunk_id,
            "allowed_roles": d.allowed_roles,
            "allow": d.allow,
            "rule": d.rule,
        }
        for d in decisions
    ]
