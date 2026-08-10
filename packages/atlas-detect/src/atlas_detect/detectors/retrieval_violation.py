"""Retrieval boundary-violation attempts (LLM02:2026): reads Atlas's own
retrieval decision log (Project 2's GET /retrieval/decisions), not
ClickHouse — the full authorization decision per candidate chunk,
including denials, already lives there with better fidelity than
anything reconstructable from spans alone. Project 2's authorized_search()
structurally prevents a denied chunk from ever reaching the model, so a
"violation" here means *attempted*, not *succeeded* — the same
distinction the tool_denied_out_of_scope Sigma rule draws for policy
denials: a blocked attempt is still a detection-worthy event.
"""

from __future__ import annotations

import httpx


def detect(atlas_base_url: str, role: str | None = None, limit: int = 200) -> list[dict]:
    params: dict[str, str | int] = {"limit": limit}
    if role:
        params["role"] = role
    resp = httpx.get(f"{atlas_base_url}/retrieval/decisions", params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json()

    findings = []
    for row in rows:
        denials = [d for d in row["decisions"] if not d["allow"]]
        if denials:
            findings.append(
                {
                    "request_id": row["request_id"],
                    "occurred_at": row["occurred_at"],
                    "caller_role": row["caller_role"],
                    "mode": row["mode"],
                    "denied_chunk_ids": [d["chunk_id"] for d in denials],
                    "denied_allowed_roles": [d["allowed_roles"] for d in denials],
                }
            )
    return findings
