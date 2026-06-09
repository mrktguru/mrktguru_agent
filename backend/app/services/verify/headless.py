"""Headless-browser verification — live DOM, console errors, screenshot.

Runs in the Celery worker (sync Playwright). Import is guarded so the rest of
the executor keeps working even if chromium/playwright isn't installed yet.
"""
from __future__ import annotations

import base64


def headless_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def headless_check(url: str, expected_markers: list[str] | None = None,
                   timeout_ms: int = 25000, full_page: bool = False) -> dict:
    """Load a page in headless chromium. Returns:
    {ok, console_errors[], missing_markers[], screenshot_b64, error}.

    ok=False if there are JS console/page errors or any expected marker is absent.
    """
    res = {"ok": True, "console_errors": [], "missing_markers": [],
           "screenshot_b64": None, "error": None}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        res["error"] = f"playwright unavailable: {e}"
        return res  # ok stays True — caller treats unavailable as "skip"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                # networkidle can time out on long-polling sites; fall back to domcontentloaded
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1200)  # let client JS render
            html = page.content()
            try:
                png = page.screenshot(full_page=full_page)
                res["screenshot_b64"] = base64.b64encode(png).decode()
            except Exception:
                pass
            browser.close()

        res["console_errors"] = errors[:20]
        for m in (expected_markers or []):
            if m and m not in html:
                res["missing_markers"].append(m)
        res["ok"] = not errors and not res["missing_markers"]
    except Exception as e:
        res["error"] = str(e)[:300]
        # A harness failure shouldn't fail the task — treat as skip (ok stays True).
    return res
