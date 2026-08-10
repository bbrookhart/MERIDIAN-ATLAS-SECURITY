import asyncpg
import httpx

from atlas import ollama_client
from atlas.db.retrieval import search


async def search_kb(
    pool: asyncpg.Pool,
    http_client: httpx.AsyncClient,
    query: str,
    caller_role: str,
    credential: str,
) -> list[dict]:
    del credential  # accepted but never scope-checked; see credentials.py (WEAKNESS ASI03)
    [embedding] = await ollama_client.embed(http_client, [query])
    chunks = await search(pool, embedding, caller_role)
    return [{"title": c.title, "body": c.body, "category": c.category} for c in chunks]
