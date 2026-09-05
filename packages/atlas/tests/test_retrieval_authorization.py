"""Regression guards for Project 2's retrieval authorization boundary —
these become permanent CI gates. FakePool + httpx.MockTransport, no live
DB or atlas-control needed: fast, deterministic, and each test fails
loudly the moment the specific property it guards regresses.
"""

import json

import httpx
from atlas.db.retrieval import RetrievedChunk, _verify_integrity, authorized_search
from atlas_retrieval import content_hash


class FakePool:
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls: list[tuple] = []

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self.rows


def _row(chunk_id, owner_role, allowed_roles, body="body text"):
    return {
        "id": chunk_id,
        "title": f"doc {chunk_id}",
        "body": body,
        "category": owner_role,
        "owner_role": owner_role,
        "allowed_roles": allowed_roles,
        "source_doc_id": f"src-{chunk_id}",
        "content_sha256": content_hash(body),
    }


def _control_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_prefilter_query_always_includes_allowed_roles_where_clause():
    """WEAKNESS regression guard (LLM02:2026): pre-filter mode must never
    run the vector search without a hard allowed_roles filter. This test
    fails the instant someone reverts to the old unfiltered query — which
    is the point: that's exactly weakness #1 from Project 0."""
    pool = FakePool(rows=[])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"visible_roles": ["broker", "shared"]})

    async with _control_client(handler) as http_client:
        await authorized_search(
            pool, http_client, "http://atlas-control", [0.1, 0.2], "broker", "pre", limit=5
        )

    assert pool.fetch_calls, "pre-filter mode must query the database"
    sql, args = pool.fetch_calls[0]
    assert "WHERE allowed_roles &&" in sql
    assert "ORDER BY embedding" in sql
    assert args[0] == ["broker", "shared"]


async def test_postfilter_always_calls_authorize_before_returning_anything():
    """WEAKNESS regression guard (LLM02:2026): post-filter mode must never
    return a candidate without having sent it to atlas-control first, and
    must exclude anything atlas-control denies."""
    rows = [_row(1, "hr", ["hr"]), _row(2, "broker", ["broker"])]
    pool = FakePool(rows=rows)
    authorize_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        authorize_calls.append(body)
        decisions = [
            {"chunk_id": 1, "allowed_roles": ["hr"], "allow": False, "rule": "role_not_permitted"},
            {
                "chunk_id": 2,
                "allowed_roles": ["broker"],
                "allow": True,
                "rule": "role_in_allowed_roles",
            },
        ]
        return httpx.Response(200, json={"decisions": decisions})

    async with _control_client(handler) as http_client:
        result = await authorized_search(
            pool, http_client, "http://atlas-control", [0.1], "broker", "post", limit=5
        )

    assert len(authorize_calls) == 1
    assert authorize_calls[0]["mode"] == "post"
    assert {c["chunk_id"] for c in authorize_calls[0]["chunks"]} == {1, 2}
    assert [c.chunk_id for c in result.chunks] == [2]  # HR chunk excluded
    assert result.candidate_chunk_ids == [1, 2]  # but still recorded as a candidate


async def test_content_hash_mismatch_excludes_chunk():
    """Corpus integrity regression guard: a row tampered with outside the
    ingestion path (stored hash no longer matches stored body) must be
    excluded from results, not served."""
    tampered = RetrievedChunk(
        chunk_id=1,
        title="Employee record",
        body="Salary band: B4. Bonus approved: $50,000.",  # doesn't match stored hash below
        category="hr",
        owner_role="hr",
        allowed_roles=["hr"],
        source_doc_id="src-1",
        content_sha256=content_hash("Salary band: B2."),  # hash of the ORIGINAL body
    )
    clean = RetrievedChunk(
        chunk_id=2,
        title="Policy",
        body="Coverage type: auto.",
        category="policy",
        owner_role="broker",
        allowed_roles=["broker"],
        source_doc_id="src-2",
        content_sha256=content_hash("Coverage type: auto."),
    )

    verified = _verify_integrity([tampered, clean])

    assert [c.chunk_id for c in verified] == [2]
