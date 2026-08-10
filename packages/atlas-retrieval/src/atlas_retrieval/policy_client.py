"""Client for atlas-control's retrieval authorization endpoint.

Retrieval authorization decisions are made by atlas-control (real OPA,
subprocess `opa eval`, see packages/atlas-control/policy/
retrieval_authorization.rego) — the same "outside the model" policy engine
Project 3 built for tool execution, extended here to cover retrieval. This
module never talks to Postgres or the LLM; it is a thin, explicit-argument
HTTP client so it can be unit tested without either.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class RetrievalPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChunkDecision:
    chunk_id: int
    allowed_roles: list[str]
    allow: bool
    rule: str


async def authorize_pre(
    http_client: httpx.AsyncClient, control_base_url: str, role: str
) -> list[str]:
    """Return the set of `allowed_roles` values this role may see, for use
    as a hard SQL filter before the vector search runs."""
    resp = await http_client.post(
        f"{control_base_url}/retrieval/authorize",
        json={"role": role, "mode": "pre"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload["visible_roles"]


async def authorize_post(
    http_client: httpx.AsyncClient,
    control_base_url: str,
    role: str,
    chunks: list[dict],
) -> list[ChunkDecision]:
    """Given already-retrieved candidate chunks (each `{chunk_id,
    allowed_roles}`), return a per-chunk allow/deny decision — the
    post-filter path: retrieve first, authorize after."""
    resp = await http_client.post(
        f"{control_base_url}/retrieval/authorize",
        json={"role": role, "mode": "post", "chunks": chunks},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    return [ChunkDecision(**d) for d in payload["decisions"]]
