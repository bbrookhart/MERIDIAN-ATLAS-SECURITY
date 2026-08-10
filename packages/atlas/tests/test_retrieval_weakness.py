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
    """WEAKNESS (LLM02:2026): search() must not scope results to caller_role.

    This test fails the moment someone "fixes" the weakness by adding a
    WHERE owner_role clause — which is the point: that fix belongs in a
    later project, not here.
    """
    rows = [{"title": "HR record", "body": "salary info", "category": "hr", "owner_role": "hr"}]
    pool = FakePool(rows)

    results = await search(pool, [0.1, 0.2, 0.3], caller_role="broker", limit=5)

    assert "owner_role" not in pool.captured_sql or "WHERE" not in pool.captured_sql.upper()
    assert len(results) == 1
    assert results[0].owner_role == "hr"  # an HR doc, returned to a broker caller
