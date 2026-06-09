"""Figma REST API client — minimal, PAT-authenticated."""
from __future__ import annotations

import re
import urllib.request
import urllib.error
import json
from typing import Any


_FILE_KEY_RE = re.compile(r"figma\.com/(?:file|design)/([A-Za-z0-9_-]+)")
_NODE_ID_RE = re.compile(r"node-id=([^&]+)")

BASE = "https://api.figma.com/v1"


def parse_figma_url(url: str) -> tuple[str, str | None]:
    """Extract (file_key, node_id_or_None) from any Figma share URL."""
    m = _FILE_KEY_RE.search(url)
    if not m:
        raise ValueError(f"Не удалось извлечь file_key из URL: {url}")
    file_key = m.group(1)
    nm = _NODE_ID_RE.search(url)
    node_id = nm.group(1).replace("%3A", ":") if nm else None
    return file_key, node_id


class FigmaClient:
    def __init__(self, pat: str) -> None:
        self._pat = pat

    def _get(self, path: str, timeout: int = 30) -> Any:
        req = urllib.request.Request(
            f"{BASE}{path}",
            headers={"X-Figma-Token": self._pat},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            raise RuntimeError(f"Figma API {e.code}: {body}") from e

    def get_toc(self, file_key: str) -> list[dict]:
        """Return top-level frames across all pages (depth=1 call)."""
        data = self._get(f"/files/{file_key}?depth=1")
        frames: list[dict] = []
        for page in data.get("document", {}).get("children", []):
            page_name = page.get("name", "")
            for child in page.get("children", []):
                if child.get("type") not in {"FRAME", "COMPONENT", "GROUP"}:
                    continue
                bb = child.get("absoluteBoundingBox") or {}
                frames.append({
                    "id": child["id"],
                    "name": child.get("name", ""),
                    "page": page_name,
                    "width": bb.get("width", 0),
                    "height": bb.get("height", 0),
                })
        return frames

    def get_nodes(self, file_key: str, node_id: str, depth: int = 5) -> dict:
        """Fetch a specific node subtree."""
        node_id_enc = node_id.replace(":", "%3A")
        data = self._get(f"/files/{file_key}/nodes?ids={node_id_enc}&depth={depth}")
        nodes = data.get("nodes", {})
        key = node_id if node_id in nodes else next(iter(nodes), None)
        return nodes[key]["document"] if key else {}

    def get_frame_image_url(self, file_key: str, node_id: str, scale: float = 0.5) -> str | None:
        """Request a PNG render of a frame. Returns the CDN URL (expires ~14 days)."""
        node_id_enc = node_id.replace(":", "%3A")
        try:
            data = self._get(f"/images/{file_key}?ids={node_id_enc}&format=png&scale={scale}")
            images = data.get("images", {})
            return images.get(node_id) or next(iter(images.values()), None)
        except Exception:
            return None

    def download_image(self, url: str, timeout: int = 20) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "mrktguru-agent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
