"""Embeddings provider for ML pattern semantic search.

Provider selection via env:
- `EMBEDDINGS_PROVIDER=voyage` → Voyage AI (`VOYAGE_API_KEY`, model `voyage-3` → 1024)
- `EMBEDDINGS_PROVIDER=openai` → OpenAI (`OPENAI_API_KEY`, model `text-embedding-3-small` → 1536)
- unset / failure → `None`, caller must fall back to overlap-only search.

We always project to a fixed 1536 dimension (zero-pad or truncate) so it matches
`MLPattern.embedding Vector(1536)` regardless of provider.
"""
from __future__ import annotations

import os
from typing import Sequence

import httpx

TARGET_DIM = 1536


def _conform(vec: Sequence[float]) -> list[float]:
    v = list(vec)
    if len(v) == TARGET_DIM:
        return v
    if len(v) > TARGET_DIM:
        return v[:TARGET_DIM]
    return v + [0.0] * (TARGET_DIM - len(v))


async def embed_text(text: str) -> list[float] | None:
    """Return a 1536-d embedding, or None if no provider is configured/usable."""
    text = (text or "").strip()
    if not text:
        return None
    provider = os.getenv("EMBEDDINGS_PROVIDER", "").lower()
    try:
        if provider == "voyage":
            key = os.getenv("VOYAGE_API_KEY")
            if not key:
                return None
            model = os.getenv("VOYAGE_MODEL", "voyage-3")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"input": [text], "model": model},
                )
                resp.raise_for_status()
                data = resp.json()
                return _conform(data["data"][0]["embedding"])
        if provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                return None
            model = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"input": text, "model": model},
                )
                resp.raise_for_status()
                data = resp.json()
                return _conform(data["data"][0]["embedding"])
    except Exception:  # noqa: BLE001 — embeddings are opt-in; silently fall back
        return None
    return None


def embed_text_sync(text: str) -> list[float] | None:
    """Sync variant for Celery worker path."""
    text = (text or "").strip()
    if not text:
        return None
    provider = os.getenv("EMBEDDINGS_PROVIDER", "").lower()
    try:
        if provider == "voyage":
            key = os.getenv("VOYAGE_API_KEY")
            if not key:
                return None
            model = os.getenv("VOYAGE_MODEL", "voyage-3")
            resp = httpx.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"input": [text], "model": model},
                timeout=15.0,
            )
            resp.raise_for_status()
            return _conform(resp.json()["data"][0]["embedding"])
        if provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                return None
            model = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
            resp = httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"input": text, "model": model},
                timeout=15.0,
            )
            resp.raise_for_status()
            return _conform(resp.json()["data"][0]["embedding"])
    except Exception:  # noqa: BLE001
        return None
    return None
