"""The decision log has always recorded `caller_session_id`; only this
query interface lacked the filter. Without it, Project 4's
retrieval_violation detector had to score "did any denial happen for this
role" instead of real per-session TP/FP like every other detector.
"""

from atlas.decision_log import list_decisions


class FakePool:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.fetch_sql: str | None = None
        self.fetch_args: tuple | None = None

    async def fetch(self, sql, *args):
        self.fetch_sql = sql
        self.fetch_args = args
        return self.rows


async def test_session_id_adds_a_caller_session_id_predicate():
    pool = FakePool()

    await list_decisions(pool, session_id="replay-attack-abc123")

    assert "caller_session_id = $1" in pool.fetch_sql
    assert pool.fetch_args[0] == "replay-attack-abc123"


async def test_session_id_composes_with_role_without_clobbering_placeholders():
    pool = FakePool()

    await list_decisions(pool, role="broker", session_id="sess-9")

    assert "caller_role = $1" in pool.fetch_sql
    assert "caller_session_id = $2" in pool.fetch_sql
    # limit is always the final positional arg
    assert pool.fetch_args[:2] == ("broker", "sess-9")
    assert f"LIMIT ${len(pool.fetch_args)}" in pool.fetch_sql


async def test_no_session_id_leaves_the_query_unfiltered_by_session():
    pool = FakePool()

    await list_decisions(pool)

    assert "caller_session_id" not in pool.fetch_sql.split("FROM")[1]
