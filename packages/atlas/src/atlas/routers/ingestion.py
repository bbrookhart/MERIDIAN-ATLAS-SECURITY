"""Permission-change webhook (Project 2): ingestion-time permission
mirroring means `documents.allowed_roles` is a *copy* of the source
system's ACL, not a live lookup — it can drift stale between real
permission changes and the next mirror event. This endpoint is that
mirror event's landing point, and it measures its own staleness rather
than assuming it's instant.

Not every source category should be mirrored this way at all: content
whose access grants change fast and matter a lot if stale (e.g. litigation
holds, active claim access grants) should be fetched live at query time
instead of indexed with a permission mirror, precisely because *any*
mirror has a staleness window. Static HR policy documents, whose access
list rarely changes, are a reasonable fit for mirroring. This deployment
only implements mirroring (Atlas has one corpus, indexed); it doesn't have
a live-fetch path, and that's a real scope line, not an oversight — see
packages/atlas-retrieval/README.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class PermissionEvent(BaseModel):
    source_doc_id: str
    new_allowed_roles: list[str]


class PermissionEventResult(BaseModel):
    source_doc_id: str
    chunks_restamped: int
    staleness_seconds: float


@router.post("/retrieval/permission-events")
async def permission_event(request: Request, body: PermissionEvent) -> PermissionEventResult:
    pool = request.app.state.db_pool
    received_at = datetime.now(UTC)

    event_row = await pool.fetchrow(
        """
        INSERT INTO permission_sync_events (source_doc_id, new_allowed_roles, received_at)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        body.source_doc_id,
        body.new_allowed_roles,
        received_at,
    )
    event_id = event_row["id"]

    status = await pool.execute(
        "UPDATE documents SET allowed_roles = $1 WHERE source_doc_id = $2",
        body.new_allowed_roles,
        body.source_doc_id,
    )
    restamped_count = int(status.split()[-1]) if status else 0
    restamped_at = datetime.now(UTC)

    await pool.execute(
        """
        UPDATE permission_sync_events
        SET chunks_restamped_at = $1, chunks_restamped_count = $2
        WHERE id = $3
        """,
        restamped_at,
        restamped_count,
        event_id,
    )

    staleness = (restamped_at - received_at).total_seconds()
    return PermissionEventResult(
        source_doc_id=body.source_doc_id,
        chunks_restamped=restamped_count,
        staleness_seconds=staleness,
    )
