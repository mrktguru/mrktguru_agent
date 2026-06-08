"""Workflows API — exposes the generative workflow catalog for the 'new project' UI."""
from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.services.claude.workflows import build_catalog

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("/catalog")
async def get_catalog(user: CurrentUser) -> list[dict]:
    """Grouped catalog of what the agent can build from scratch (5 generative types)."""
    return build_catalog()
