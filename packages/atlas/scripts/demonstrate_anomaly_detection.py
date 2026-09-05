"""One-off live demonstration that the ingestion-time anomaly detector
(atlas_retrieval.detect_ingestion_anomaly) actually fires, not just that it
has unit tests. Run against the live seeded stack:

    uv run --package atlas python packages/atlas/scripts/demonstrate_anomaly_detection.py

An elementwise average of three real, unrelated documents' embeddings was
tried first and did NOT trip the detector (cosine similarity between an
average and its inputs drops fast in 768 dimensions) — an honest negative
worth recording, not hidden. The actual poisoning signature the detector
looks for is a single embedding recurring across many role-tagged entries
— exactly what an attacker submitting near-identical content tagged for
different roles to maximize reach would produce. This demo reproduces that
directly and honestly: one real document's embedding, "existing" as
several role-tagged copies of itself, checked against itself as the
incoming document.
"""

import asyncio

import asyncpg
from atlas.config import settings
from atlas_retrieval import detect_ingestion_anomaly
from pgvector.asyncpg import register_vector

ROLE_CYCLE = ["broker", "adjuster", "hr", "broker", "adjuster", "hr"]


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await register_vector(conn)
        row = await conn.fetchrow(
            "SELECT title, owner_role, embedding FROM documents WHERE category = 'policy' LIMIT 1"
        )
        real_embedding = row["embedding"].to_list()
        print(f"Base document: {row['title']!r} (real owner_role={row['owner_role']!r})")

        # A poisoning attempt: the same content submitted under several
        # different role tags to maximize how many roles' retrieval it
        # can reach.
        existing = [(role, real_embedding) for role in ROLE_CYCLE]
        print(f"Simulated near-duplicate submissions tagged as: {ROLE_CYCLE}")

        result = detect_ingestion_anomaly(
            existing, real_embedding, similarity_threshold=0.9, fanout_limit=5
        )
        print(f"flagged={result.flagged}")
        print(f"similar_count={result.similar_count}")
        print(f"roles_spanned={sorted(result.roles_spanned)}")
        print(f"reason={result.reason!r}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
