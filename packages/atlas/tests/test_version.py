from atlas.routers import version
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_version_returns_build_sha(monkeypatch):
    monkeypatch.setenv("ATLAS_BUILD_SHA", "test-sha-123")
    import importlib

    from atlas import config

    importlib.reload(config)
    monkeypatch.setattr(version, "settings", config.settings)

    app = FastAPI()
    app.include_router(version.router)
    client = TestClient(app)

    resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["build_sha"] == "test-sha-123"
    assert body["service"] == "atlas"
