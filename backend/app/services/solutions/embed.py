"""Embedding service — OpenAI text-embedding-3-small with graceful fallback.

If OPENAI_API_KEY is not configured, returns None (disables vector search;
system falls back to type/keyword ranking only).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_VECTOR_DIM = 1536


def embed(text: str) -> list[float] | None:
    """Return 1536-dim embedding or None if unavailable."""
    from app.core.config import settings
    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],
        )
        return resp.data[0].embedding
    except Exception as exc:
        logger.warning("embed failed: %s", exc)
        return None
