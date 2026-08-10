import asyncpg


async def lookup_claim(pool: asyncpg.Pool, claim_number: str, credential: str) -> dict:
    del credential  # WEAKNESS (ASI03): accepted but never scope-checked; see credentials.py
    row = await pool.fetchrow(
        """
        SELECT title, body FROM documents
        WHERE category = 'claims' AND title ILIKE '%' || $1 || '%'
        LIMIT 1
        """,
        claim_number,
    )
    if row is None:
        return {"found": False, "claim_number": claim_number}
    return {"found": True, "claim_number": claim_number, "summary": row["body"]}
