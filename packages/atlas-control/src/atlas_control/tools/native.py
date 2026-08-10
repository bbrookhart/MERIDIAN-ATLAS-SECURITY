"""The four native tools, ported from atlas.tools.* to live behind the
control plane. Atlas's agent process no longer imports any of this — it
has no DB connection and no tool code, only an HTTP client for
atlas-control. Execution only ever happens after policy.authorize() has
approved the call and a capability token has been minted and redeemed for
it — issue_refund does not re-check the threshold itself; the gate in
front of it is what makes the threshold real.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import httpx

from atlas_control import ollama_client
from atlas_control.config import settings
from atlas_control.retrieval import search


async def lookup_claim(pool: asyncpg.Pool, claim_number: str) -> dict:
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


async def issue_refund(claim_number: str, amount_cents: int) -> dict:
    return {"issued": True, "claim_number": claim_number, "amount_cents": amount_cents}


async def send_email(to: str, subject: str, body: str) -> dict:
    outbox = Path(settings.outbox_dir)
    outbox.mkdir(parents=True, exist_ok=True)
    record = {
        "to": to,
        "subject": subject,
        "body": body,
        "sent_at": datetime.now(UTC).isoformat(),
    }
    with (outbox / "emails.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"sent": True, "to": to, "subject": subject}


async def search_kb(
    pool: asyncpg.Pool, http_client: httpx.AsyncClient, query: str, caller_role: str
) -> list[dict]:
    [embedding] = await ollama_client.embed(http_client, [query])
    chunks = await search(pool, embedding, caller_role)
    return [{"title": c.title, "body": c.body, "category": c.category} for c in chunks]
