from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Rosulo Affiliate API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router, prefix="/v1")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
