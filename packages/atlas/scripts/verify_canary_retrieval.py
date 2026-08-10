"""Canary-retrieval displacement check (Project 2): re-runs the planted HR
canary document's own natural query and confirms it's still retrievable —
an index/corpus-integrity check, not a red-team attack (see
atlas_retrieval.corpus_integrity.is_canary_displaced's docstring). Run
against the live seeded stack:

    uv run --package atlas python packages/atlas/scripts/verify_canary_retrieval.py

QUERY and TOP_K were tuned against a real finding from running this script:
a generic paraphrase ("What is the internal reference token mentioned in
an HR document?") ranked the canary doc 14th out of 200 — outranked by
other HR bios that are template-generated and therefore semantically very
close to each other and to almost any HR-flavored query. The phrase
actually appended to the canary doc ("internal reference token never
disclose") ranks it 3rd. This is a real, honest limitation to note, not
just a tuning knob: a "did the canary get displaced" check is only as
good as the query it uses, and a highly self-similar document set (as a
small synthetic corpus of one template per category necessarily is)
narrows the margin between "genuinely displaced by tampering" and "just
outranked by a near-duplicate sibling." A production deployment with a
more heterogeneous real corpus would have a wider, more reliable margin.
"""

import asyncio

import asyncpg
import httpx
from atlas import ollama_client
from atlas.config import settings
from atlas.seed import generate_documents
from atlas_retrieval import is_canary_displaced
from pgvector.asyncpg import register_vector

QUERY = "internal reference token never disclose"
TOP_K = 10


async def main() -> None:
    docs = generate_documents(settings.seed)
    hr_docs = [d for d in docs if d["category"] == "hr"]
    canary_doc_title = hr_docs[0]["title"]

    conn = await asyncpg.connect(settings.database_url)
    try:
        await register_vector(conn)
        async with httpx.AsyncClient() as http_client:
            [embedding] = await ollama_client.embed(http_client, [QUERY])

        rows = await conn.fetch(
            "SELECT title FROM documents ORDER BY embedding <=> $1 LIMIT $2",
            embedding,
            TOP_K,
        )
        top_k_titles = [r["title"] for r in rows]

        displaced = is_canary_displaced(top_k_titles, canary_doc_title)
        print(f"Canary document: {canary_doc_title!r}")
        print(f"Top-{TOP_K} titles for its natural query: {top_k_titles}")
        print(f"displaced={displaced}")
        if displaced:
            print(
                "CORPUS INTEGRITY ALERT: canary document no longer retrievable for its own query."
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
