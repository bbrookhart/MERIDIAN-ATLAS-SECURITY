from pathlib import Path

import asyncpg
from pgvector.asyncpg import register_vector

from atlas.config import settings

_SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text()


async def _init_connection(conn: asyncpg.Connection) -> None:
    await register_vector(conn)


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(settings.database_url, init=_init_connection)
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA_SQL)
    return pool
