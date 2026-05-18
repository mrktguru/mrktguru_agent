"""Auto-fix: ask Claude for shell commands to fix a failed deploy step."""
from __future__ import annotations

import json
import re
from typing import Any

from app.services.claude.client import ClaudeClient

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_SYSTEM = (
    "You are a senior DevOps engineer fixing a failed deploy step on a Linux server. "
    "You receive: the failing step name, the captured error output, the project spec, "
    "and basic server info. Respond with STRICTLY one JSON object: "
    '{"commands": ["sh cmd 1", "sh cmd 2"], "explanation": "what & why"}. '
    "Rules:\n"
    "- Commands run as root over SSH, non-interactively. No sudo prompts.\n"
    "- Never destroy unrelated containers, networks or data.\n"
    "- Prefer minimal, idempotent commands (mkdir -p, apt-get install -y, etc.).\n"
    "- If the error is unrecoverable, return an empty commands array.\n"
    "- No prose outside the JSON object."
)


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
    client = ClaudeClient()
    msg = client.client.messages.create(
        model=client.model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
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
