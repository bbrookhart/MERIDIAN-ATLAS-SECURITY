from atlas.db.retrieval import search


class FakePool:
    def __init__(self, rows):
        self.rows = rows
        self.captured_sql = None
        self.captured_args = None

    async def fetch(self, sql, *args):
        self.captured_sql = sql
        self.captured_args = args
        return self.rows


async def test_search_does_not_filter_by_caller_role():
    """This low-level helper is intentionally still a plain, unfiltered
    vector query after Project 2 (see its docstring) — the authorization
    boundary lives one layer up, in routers/rag.py's pre/post-filter
    orchestration, which decides *which* SQL runs and *who* gets to see the
    result. This test documents that `search()` itself carries no filter,
    so nobody mistakes it for the enforcement point. The real regression
    guard for "a broker can't actually see HR content" lives in
    test_retrieval_authorization.py, against the orchestrator.
    """
    rows = [
        {
            "id": 1,
            "title": "HR record",
            "body": "salary info",
            "category": "hr",
            "owner_role": "hr",
            "allowed_roles": ["hr"],
            "source_doc_id": "src-hr-00001",
            "content_sha256": "deadbeef",
        }
    ]
    pool = FakePool(rows)

    results = await search(pool, [0.1, 0.2, 0.3], caller_role="broker", limit=5)

    assert "owner_role" not in pool.captured_sql or "WHERE" not in pool.captured_sql.upper()
    assert len(results) == 1
    assert results[0].owner_role == "hr"  # an HR doc, returned to a broker caller
