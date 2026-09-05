from atlas.memory import load_recent_facts, save_fact


class FakePool:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.execute_calls: list[tuple] = []
        self.fetch_sql: str | None = None
        self.fetch_args: tuple | None = None

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))

    async def fetch(self, sql, *args):
        self.fetch_sql = sql
        self.fetch_args = args
        return self.rows


async def test_save_fact_records_source_trust_tier_and_ttl():
    pool = FakePool()
    await save_fact(pool, "session-a", "user_message", "my recovery code is X")

    assert len(pool.execute_calls) == 1
    sql, args = pool.execute_calls[0]
    assert "source" in sql and "trust_tier" in sql and "run_id" in sql and "expires_at" in sql
    session_id, _kind, _content, source, trust_tier, run_id, ttl_seconds = args
    assert session_id == "session-a"
    assert source == "user_input"
    assert trust_tier == "untrusted"
    assert run_id  # a fresh id was generated
    assert ttl_seconds > 0


async def test_assistant_output_is_trusted():
    pool = FakePool()
    await save_fact(pool, "session-a", "assistant_message", "here is my answer")
    _sql, args = pool.execute_calls[0]
    source, trust_tier = args[3], args[4]
    assert source == "assistant_output"
    assert trust_tier == "trusted"


async def test_load_recent_facts_scopes_query_to_one_session():
    """WEAKNESS regression guard (ASI06): load_recent_facts must filter by
    session_id. This test fails the moment someone removes that filter —
    which is the point: that removal is exactly weakness #5 from Project 0.
    """
    pool = FakePool(rows=[])
    await load_recent_facts(pool, "session-b", limit=10)

    assert "session_id" in pool.fetch_sql
    assert "WHERE" in pool.fetch_sql.upper()
    assert pool.fetch_args[0] == "session-b"


async def test_load_recent_facts_excludes_expired_rows_in_query():
    pool = FakePool(rows=[])
    await load_recent_facts(pool, "session-b")
    assert "expires_at" in pool.fetch_sql


async def test_loaded_facts_never_use_system_role():
    """Untrusted content is never promoted to instruction tier: no kind
    maps to role="system", so nothing loaded from memory can pose as a
    system instruction.
    """
    pool = FakePool(
        rows=[
            {"kind": "user_message", "content": "a"},
            {"kind": "assistant_message", "content": "b"},
            {"kind": "tool_result", "content": "c"},
            {"kind": "some_unexpected_kind", "content": "d"},
        ]
    )
    facts = await load_recent_facts(pool, "session-b")
    assert all(f["role"] != "system" for f in facts)
