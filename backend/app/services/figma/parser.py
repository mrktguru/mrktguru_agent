"""Figma JSON → compact semantic digest for Claude context."""
from __future__ import annotations

import re
from typing import Any

# Node types to recurse into
_CONTAINER_TYPES = {"FRAME", "GROUP", "COMPONENT", "INSTANCE", "SECTION"}
# Types that carry text
_TEXT_TYPE = "TEXT"
# Types likely to be image fills
_IMAGE_FILL_TYPE = "IMAGE"

# Pages/frames that are almost certainly not the main site design
_SKIP_PAGE_NAMES = re.compile(
    r"(library|component|icon|styleguide|atom|token|color|typo|grid|spec|template)",
    re.IGNORECASE,
)
# Frame names that indicate the site design
_SITE_FRAME_NAMES = re.compile(
    r"(landing|desktop|main|web|site|сайт|главная|home|index|page|screen)",
    re.IGNORECASE,
)

MAX_DIGEST_CHARS = 6000
MAX_DEPTH = 5


def pick_best_frame(toc: list[dict]) -> list[dict]:
    """Apply heuristics and return ranked candidates (best first).

    Returns a list so caller can decide: 1 item = auto-selected, 2+ = ask user.
    """
    # Filter out library/component pages
    candidates = [f for f in toc if not _SKIP_PAGE_NAMES.search(f.get("page", ""))]
    if not candidates:
        candidates = toc[:]

    # Score each frame
    def score(f: dict) -> int:
        s = 0
        if _SITE_FRAME_NAMES.search(f.get("name", "")):
            s += 10
        w = f.get("width", 0)
        if 1200 <= w <= 1920:
            s += 5
        elif 900 <= w < 1200:
            s += 2
        h = f.get("height", 0)
        if h > 2000:
            s += 3
        return s

    candidates.sort(key=score, reverse=True)
    top_score = score(candidates[0]) if candidates else 0

    # If there's a clear winner (score gap >= 5), return just that one
    if len(candidates) >= 2 and (top_score - score(candidates[1])) >= 5:
        return candidates[:1]
    # Otherwise return top-3 for user to pick
    return candidates[:3]


def _rgba_to_hex(color: dict) -> str:
    r = int(color.get("r", 0) * 255)
    g = int(color.get("g", 0) * 255)
    b = int(color.get("b", 0) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _extract_color(node: dict) -> str | None:
    for fill in node.get("fills", []):
        if fill.get("type") == "SOLID" and fill.get("visible", True) is not False:
            return _rgba_to_hex(fill.get("color", {}))
    return None


def _simplify_node(node: dict, depth: int = 0) -> dict | None:
    if not node.get("visible", True):
        return None
    bb = node.get("absoluteBoundingBox") or {}
    w, h = bb.get("width", 0), bb.get("height", 0)
    if depth > 0 and (w < 10 or h < 10):
        return None

    ntype = node.get("type", "")
    name = node.get("name", "")

    if ntype == _TEXT_TYPE:
        chars = (node.get("characters") or "").strip()
        if not chars:
            return None
        fs = None
        try:
            fs = node.get("style", {}).get("fontSize")
        except Exception:
            pass
        result: dict[str, Any] = {"type": "TEXT", "text": chars[:200]}
        if fs:
            result["fontSize"] = fs
        return result

    if ntype in _CONTAINER_TYPES or depth == 0:
        result = {"type": ntype, "name": name}
        if bb:
            result["y"] = int(bb.get("y", 0))
            result["h"] = int(h)
            if depth == 0:
                result["w"] = int(w)

        color = _extract_color(node)
        if color:
            result["bg"] = color

        has_image = any(
            f.get("type") == _IMAGE_FILL_TYPE
            for f in node.get("fills", [])
        )
        if has_image:
            result["has_image"] = True

        if depth >= MAX_DEPTH:
            child_count = len(node.get("children", []))
            if child_count:
                result["_children"] = child_count
            return result

        children = []
        for child in node.get("children", []):
            simplified = _simplify_node(child, depth + 1)
            if simplified:
                children.append(simplified)
        if children:
            result["children"] = children
        return result

    return None


def _collect_colors(node: dict, colors: dict[str, int], depth: int = 0) -> None:
    if depth > 3:
        return
    color = _extract_color(node)
    if color:
        colors[color] = colors.get(color, 0) + 1
    for child in node.get("children", []):
        _collect_colors(child, colors, depth + 1)


def _collect_fonts(node: dict, fonts: set[str], depth: int = 0) -> None:
    if depth > 5:
        return
    if node.get("type") == _TEXT_TYPE:
        family = node.get("style", {}).get("fontFamily")
        if family:
            fonts.add(family)
    for child in node.get("children", []):
        _collect_fonts(child, fonts, depth + 1)


def _has_form(node: dict, depth: int = 0) -> bool:
    if depth > 6:
        return False
    name = (node.get("name") or "").lower()
    if any(kw in name for kw in ("form", "форма", "input", "field", "submit")):
        return True
    return any(_has_form(c, depth + 1) for c in node.get("children", []))


def build_digest(frame_node: dict, frame_meta: dict) -> dict:
    """Build a compact semantic digest from a frame node dict."""
    colors: dict[str, int] = {}
    _collect_colors(frame_node, colors)
    fonts: set[str] = set()
    _collect_fonts(frame_node, fonts)

    # Top color palette: up to 4 most-used colors
    top_colors = sorted(colors.items(), key=lambda x: -x[1])[:4]
    color_palette = [c for c, _ in top_colors]

    # Sections = direct children frames/groups of the root
    sections = []
    for child in frame_node.get("children", []):
        if not child.get("visible", True):
            continue
        bb = child.get("absoluteBoundingBox") or {}
        w, h = bb.get("width", 0), bb.get("height", 0)
        if h < 50:
            continue
        texts: list[str] = []
        for node in child.get("children", []):
            if node.get("type") == _TEXT_TYPE:
                t = (node.get("characters") or "").strip()
                if t and len(t) > 2:
                    texts.append(t[:120])
        section: dict[str, Any] = {
            "name": child.get("name", ""),
            "y": int(bb.get("y", 0)),
            "h": int(h),
        }
        if texts:
            section["texts"] = texts[:6]
        if any(f.get("type") == _IMAGE_FILL_TYPE for f in child.get("fills", [])):
            section["has_image"] = True
        sections.append(section)

    bb = frame_node.get("absoluteBoundingBox") or {}
    digest: dict[str, Any] = {
        "frame": frame_meta.get("name", ""),
        "size": f"{int(bb.get('width', 0))}×{int(bb.get('height', 0))}",
        "sections": sections,
        "colors": color_palette,
        "fonts": sorted(fonts)[:4],
        "has_form": _has_form(frame_node),
    }
    return digest
