"""Corpus integrity: content hashing, ingestion-time anomaly detection, and
canary-retrieval displacement — pure functions, no DB connection, so the
detection logic itself is unit-testable independent of a live corpus.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


def content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def verify_content_hash(body: str, stored_hash: str) -> bool:
    """True if `body` still matches the hash recorded at ingestion time.
    A mismatch means the row was written to outside the ingestion path —
    the only writer that's supposed to exist (see README's restricted
    write path section) — and the chunk must be excluded, not served."""
    return content_hash(body) == stored_hash


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass(frozen=True)
class AnomalyResult:
    flagged: bool
    similar_count: int
    roles_spanned: set[str]
    reason: str


def detect_ingestion_anomaly(
    existing: list[tuple[str, list[float]]],
    new_embedding: list[float],
    similarity_threshold: float = 0.9,
    fanout_limit: int = 5,
) -> AnomalyResult:
    """Flag a newly-ingested document whose embedding sits unusually close
    to many existing documents *spanning more roles than fanout_limit*.

    A single poisoned document trying to rank highly for many different
    queries across role boundaries it shouldn't span is the signature this
    looks for — a legitimately similar pair of same-role documents (two
    near-duplicate policy docs) is expected and not flagged; the same
    similarity spread across broker+adjuster+hr is not.

    `existing` is `[(owner_role, embedding), ...]` for the current corpus.
    This is a monitoring signal, not a hard ingestion gate: on a small
    corpus, false positives from legitimately similar documents are
    plausible, and it's reported/logged rather than silently blocking
    ingestion.
    """
    similar_roles: set[str] = set()
    similar_count = 0
    for role, embedding in existing:
        if _cosine_similarity(new_embedding, embedding) >= similarity_threshold:
            similar_count += 1
            similar_roles.add(role)

    flagged = len(similar_roles) > fanout_limit or (
        len(similar_roles) > 1 and similar_count > fanout_limit
    )
    reason = (
        f"embedding highly similar to {similar_count} existing docs "
        f"spanning {len(similar_roles)} roles ({sorted(similar_roles)})"
        if flagged
        else "no anomaly"
    )
    return AnomalyResult(
        flagged=flagged, similar_count=similar_count, roles_spanned=similar_roles, reason=reason
    )


def is_canary_displaced(top_k_titles: list[str], canary_doc_title: str) -> bool:
    """True if the known-good canary document is *not* in the top-k results
    for its own natural query — a retrieval-displacement alert. Used as a
    live integrity check (see verify_canary_retrieval.py), not a red-team
    probe: this tests whether the index still works, not whether an
    attacker can break in."""
    return canary_doc_title not in top_k_titles
