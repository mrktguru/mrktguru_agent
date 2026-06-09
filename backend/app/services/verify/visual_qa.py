"""Visual QA via Claude Vision — compare before/after screenshots.

Called after headless capture to give the agent "eyes" to judge whether
the change was applied correctly. Inspired by browser-use's vision loop.

Returns a lightweight verdict dict; the caller decides whether to rollback.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_SYSTEM = (
    "You are a visual QA specialist reviewing website screenshots. "
    "You compare before/after screenshots to verify that a specific change was applied correctly. "
    "Be concise and objective. Return only valid JSON."
)

_PROMPT_TEMPLATE = """Task that was applied to the website:
{task_description}

Analyze the two screenshots:
- Image 1: BEFORE the change
- Image 2: AFTER the change

Determine whether the change was visibly applied correctly.

Return ONLY valid JSON (no markdown):
{{
  "ok": true/false,
  "confidence": "high|medium|low",
  "notes": "brief observation about what changed or what is wrong"
}}"""


def visual_qa(
    screenshot_before_b64: str,
    screenshot_after_b64: str,
    task_description: str,
) -> dict:
    """Compare before/after screenshots with Claude Vision.

    Returns: {ok: bool, confidence: str, notes: str, error: str|None}
    Never raises — all errors are returned in the `error` field.
    """
    result: dict = {"ok": True, "confidence": "low", "notes": "", "error": None}
    try:
        import anthropic
        from app.core.config import settings

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast + cheap for QA
            max_tokens=256,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_before_b64,
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_after_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _PROMPT_TEMPLATE.format(
                            task_description=task_description[:800]
                        ),
                    },
                ],
            }],
        )
        text = "".join(
            b.text for b in response.content if getattr(b, "type", "") == "text"
        ).strip()
        # Strip markdown fences if model adds them
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
        parsed = json.loads(text)
        result.update({
            "ok": bool(parsed.get("ok", True)),
            "confidence": str(parsed.get("confidence", "low")),
            "notes": str(parsed.get("notes", "")),
        })
    except Exception as exc:
        result["error"] = str(exc)[:200]
        logger.warning("visual_qa failed: %s", exc)
    return result
