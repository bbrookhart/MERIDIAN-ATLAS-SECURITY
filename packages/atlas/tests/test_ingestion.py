from atlas.routers import ingestion
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakePool:
    def __init__(self, update_status: str = "UPDATE 3"):
        self.fetchrow_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []
        self.update_status = update_status
        self._next_id = 1

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        row_id = self._next_id
        self._next_id += 1
        return {"id": row_id}

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        if "UPDATE documents" in sql:
            return self.update_status
        return "UPDATE 1"


def _client(pool: FakePool) -> TestClient:
    app = FastAPI()
    app.include_router(ingestion.router)
    app.state.db_pool = pool
    return TestClient(app)


def test_permission_event_restamps_matching_documents_and_reports_count():
    pool = FakePool(update_status="UPDATE 3")
    client = _client(pool)

    resp = client.post(
        "/retrieval/permission-events",
        json={"source_doc_id": "src-hr-00001", "new_allowed_roles": ["hr", "adjuster"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_doc_id"] == "src-hr-00001"
    assert body["chunks_restamped"] == 3
    assert body["staleness_seconds"] >= 0

    update_calls = [c for c in pool.execute_calls if "UPDATE documents" in c[0]]
    assert len(update_calls) == 1
    _sql, args = update_calls[0]
    assert args == (["hr", "adjuster"], "src-hr-00001")


def test_permission_event_is_recorded_before_and_after_restamp():
    pool = FakePool()
    client = _client(pool)

    client.post(
        "/retrieval/permission-events",
        json={"source_doc_id": "src-hr-00002", "new_allowed_roles": ["hr"]},
    )

    assert len(pool.fetchrow_calls) == 1  # the initial received_at insert
    restamped_updates = [c for c in pool.execute_calls if "chunks_restamped_at" in c[0]]
    assert len(restamped_updates) == 1  # the staleness-completing update


def test_permission_event_zero_matches_reports_zero_restamped():
    pool = FakePool(update_status="UPDATE 0")
    client = _client(pool)

    resp = client.post(
        "/retrieval/permission-events",
        json={"source_doc_id": "src-unknown", "new_allowed_roles": ["hr"]},
    )

    assert resp.json()["chunks_restamped"] == 0
