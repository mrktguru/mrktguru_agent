"""Auto-fix: ask Claude for shell commands to fix a failed deploy step."""
from __future__ import annotations

import json
import re
from typing import Any

from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def suggest_fix(
    step: str,
    error_output: str,
    spec: dict[str, Any],
    server_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return {"commands": [...], "explanation": "..."}."""
    user = (
        f"Step: {step}\n\n"
        f"Error output (last lines):\n{error_output[-2000:]}\n\n"
        f"Project spec:\n{json.dumps(spec, ensure_ascii=False)[:4000]}\n\n"
        f"Server info:\n{json.dumps(server_info or {}, ensure_ascii=False)[:2000]}"
    )
    layer = resolve("auto_fix")
    client = ClaudeClient(model=layer.model)
    msg = client.client.messages.create(
        model=client.model,
        max_tokens=layer.max_tokens,
        system=[
            {
                "type": "text",
                "text": layer.system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in msg.content if hasattr(block, "text"))
    match = _JSON_RE.search(text)
    if not match:
        return {"commands": [], "explanation": "no JSON in response"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"commands": [], "explanation": "invalid JSON in response"}
    return {
        "commands": [str(c) for c in (data.get("commands") or [])],
        "explanation": str(data.get("explanation", "")),
    }
