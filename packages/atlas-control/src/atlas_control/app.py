from contextlib import asynccontextmanager

import httpx
from atlas_detect import instrument_fastapi_app
from fastapi import FastAPI

from atlas_control.db import create_pool
from atlas_control.routers import approval as approval_router
from atlas_control.routers import budget as budget_router
from atlas_control.routers import plan as plan_router
from atlas_control.routers import retrieval as retrieval_router
from atlas_control.routers import staged as staged_router


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
    app = FastAPI(title="atlas-control", lifespan=lifespan)
    instrument_fastapi_app(app)
    app.include_router(plan_router.router)
    app.include_router(budget_router.router)
    app.include_router(staged_router.router)
    app.include_router(approval_router.router)
    app.include_router(retrieval_router.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
