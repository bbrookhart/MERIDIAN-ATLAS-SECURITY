"""asyncpg pool — atlas-control reads/writes Atlas's own Postgres (the RAG
corpus for search_kb, the claims/policy documents for lookup_claim). Sharing
the database while enforcing who may invoke which tool is the control
plane's job, not a reason to fork the data store.
"""

from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector

from atlas_control.config import settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    await register_vector(conn)


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.database_url, init=_init_connection)
