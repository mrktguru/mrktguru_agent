"""Integrations API — connect third-party services (Figma, etc.)."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.deps import CurrentUser, DB
from app.core.security import _get_fernet
from app.models.user import User
from sqlalchemy import select

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def _decrypt_token(enc: str) -> str:
    return _get_fernet().decrypt(enc.encode()).decode()


class FigmaTokenRequest(BaseModel):
    token: str


@router.get("/figma")
async def get_figma_status(user: CurrentUser, db: DB) -> dict:
    return {"connected": bool(user.figma_token_enc)}


@router.post("/figma")
async def save_figma_token(body: FigmaTokenRequest, user: CurrentUser, db: DB) -> dict:
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Token is empty")
    db_user = await db.scalar(select(User).where(User.id == user.id))
    if not db_user:
        raise HTTPException(status_code=404)
    db_user.figma_token_enc = _encrypt_token(token)
    await db.commit()
    return {"connected": True}


@router.delete("/figma")
async def delete_figma_token(user: CurrentUser, db: DB) -> dict:
    db_user = await db.scalar(select(User).where(User.id == user.id))
    if db_user:
        db_user.figma_token_enc = None
        await db.commit()
    return {"connected": False}
