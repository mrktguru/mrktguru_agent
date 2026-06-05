"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, servers, sites, tasks
from app.api.tasks_ws import ws_router as tasks_ws_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.services.llm.registry import seed_layers
        seed_layers()
    except Exception:
        pass  # don't block startup if DB not ready
    yield


app = FastAPI(
    title="MRKTGURU Agent",
    description="AI agent for editing existing sites",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(sites.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(tasks_ws_router)
