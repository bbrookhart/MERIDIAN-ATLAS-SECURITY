from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from atlas.db.pool import create_pool
from atlas.routers import agent, chat, ingestion, rag, version


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    app.state.http_client = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.db_pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas", lifespan=lifespan)
    # WEAKNESS (LLM06:2026 — Unbounded Consumption): no rate-limiting
    # middleware, no per-session token budget, no cost cap is registered
    # here. Every request is served with no throttling. See WEAKNESSES.md.
    app.include_router(version.router)
    app.include_router(chat.router)
    app.include_router(rag.router)
    app.include_router(agent.router)
    app.include_router(ingestion.router)
    return app


app = create_app()
