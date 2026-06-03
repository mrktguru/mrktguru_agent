"""TaskEstimator — parses TZ text and estimates subtasks + credits using Claude."""
from __future__ import annotations

import json
import re
import shlex

from app.models.site import Site
from app.models.task import Task
from app.services.claude.client import ClaudeClient
from app.services.llm.registry import resolve

_SKIP_DIRS = ("/dist/", "/build/", "/.next/", "/out/", "/node_modules/", "__pycache__")


class TaskEstimator:
    def __init__(self, site: Site, task: Task, ssh=None) -> None:
        self._site = site
        self._task = task
        self._ssh = ssh  # SSHClient | None  — live SSH for fresh file reads

    async def estimate(self) -> dict:
        site_context = self._build_site_context()
        user_message = self._build_user_message()

        layer = resolve("task_estimator")
        claude = ClaudeClient(model=layer.model)
        result = claude.call_with_system(
            system=layer.system_prompt,
            messages=[
                # Site context as assistant pre-fill to enable caching
                {"role": "user", "content": site_context},
                {"role": "assistant", "content": "Понял контекст сайта. Жду ваше ТЗ."},
                {"role": "user", "content": user_message},
            ],
            max_tokens=layer.max_tokens,
        )

        return self._parse_response(result["content"])

    # ---------------------------------------------------------------- helpers

    def _build_site_context(self) -> str:
        site = self._site
        parts = [f"КОНТЕКСТ САЙТА: {site.name}"]
        if site.url:
            parts.append(f"URL: {site.url}")
        if site.cms:
            parts.append(f"CMS: {site.cms} {site.cms_version or ''}".strip())
        if site.php_version:
            parts.append(f"PHP: {site.php_version}")
        if site.web_server:
            parts.append(f"Web-сервер: {site.web_server}")
        if site.site_root_path:
            parts.append(f"Корневая папка: {site.site_root_path}")

        # ── Live SSH context (if available) or fallback to DB snapshot ────────
        file_list: list[str] = []
        file_contents: dict[str, str] = {}

        if self._ssh and site.site_root_path:
            try:
                file_list, file_contents = self._fetch_live_context(
                    site.site_root_path, self._task.tz_text or ""
                )
            except Exception:
                pass  # fall through to DB fallback

        if not file_list:
            # Fallback: DB snapshot, filtered to source files only
            db_entries = (site.file_structure or {}).get("entries", [])
            file_list = [e for e in db_entries if not any(s in e for s in _SKIP_DIRS)]
            if not file_list:
                file_list = db_entries  # last resort: show everything

        if file_list:
            parts.append("Структура файлов (только исходники):\n" + "\n".join(file_list[:150]))

        # Include actual file contents so Claude sees real code
        for path, content in file_contents.items():
            parts.append(f"\n--- {path} ---\n{content}")

        if site.installed_plugins:
            active = site.installed_plugins.get("active", [])
            if active:
                parts.append("Активные плагины: " + ", ".join(active[:20]))

        return "\n".join(parts)

    def _fetch_live_context(
        self, root: str, tz_text: str
    ) -> tuple[list[str], dict[str, str]]:
        """Return (source_file_list, {path: content}) via live SSH.

        Steps:
          1. Fresh `find` → source-only file list (no dist/build)
          2. grep source files for terms extracted from tz_text
          3. Read up to 10 matched files (cat | head -400)
        """
        from app.services.ssh.scanner import SiteScanner

        scanner = SiteScanner(self._ssh)

        # 1. Fresh file tree
        structure = scanner._get_file_structure(root)
        all_entries = structure.get("entries", [])
        source_entries = [e for e in all_entries if not any(s in e for s in _SKIP_DIRS)]

        # 2. Build grep pattern from tz_text
        grep_terms = self._extract_grep_terms(tz_text)
        files_to_read: list[str] = []

        if grep_terms and source_entries:
            pattern = "|".join(grep_terms)
            # grep recursively from root, limit to source extensions
            _, out, _ = self._ssh.run(
                f"grep -rl {shlex.quote(pattern)} {shlex.quote(root)} "
                f"--include='*.css' --include='*.scss' --include='*.tsx' "
                f"--include='*.ts' --include='*.vue' --include='*.html' "
                f"--include='*.js' --include='*.php' "
                f"2>/dev/null | grep -v '/dist/' | grep -v '/build/' "
                f"| grep -v '/node_modules/' | grep -v '/.next/' | head -12",
                timeout=20,
            )
            files_to_read = [f.strip() for f in out.splitlines() if f.strip()]

        # Fallback: use all CSS/SCSS source files when grep finds nothing
        if not files_to_read:
            files_to_read = [
                e for e in source_entries
                if e.endswith((".css", ".scss")) and not any(s in e for s in _SKIP_DIRS)
            ][:8]

        # 3. Read file contents (up to 10 files, 400 lines each)
        file_contents: dict[str, str] = {}
        for path in files_to_read[:10]:
            _, content, _ = self._ssh.run(
                f"cat {shlex.quote(path)} 2>/dev/null | head -400", timeout=15
            )
            if content.strip():
                file_contents[path] = content

        return source_entries, file_contents

    def _extract_grep_terms(self, tz_text: str) -> list[str]:
        """Extract 3-5 grep search terms from the task description."""
        text = tz_text.lower()
        terms: list[str] = []

        # Map common Russian task keywords → CSS/code patterns to search for
        keyword_map = [
            (["фон", "background", "bg-"], "background"),
            (["ссылк", "link", "href"], "a[^,{]*{|a:hover|a:link"),
            (["кнопк", "btn", "button"], "btn|button"),
            (["цвет", "color", "краск"], "color"),
            (["отступ", "padding", "margin"], "padding|margin"),
            (["шрифт", "font", "текст"], "font"),
            (["тень", "shadow"], "shadow"),
            (["границ", "border"], "border"),
            (["навигац", "меню", "nav"], "nav"),
            (["иконк", "icon", "svg"], "icon|svg"),
        ]
        for keywords, pattern in keyword_map:
            if any(kw in text for kw in keywords):
                terms.append(pattern)

        # Also grab short words that look like CSS class names (.something)
        class_refs = re.findall(r"\.[a-z][\w-]{2,}", tz_text)
        terms.extend(class_refs[:3])

        return terms[:5] if terms else ["background", "color", "a[^,{]*{"]

    def _build_user_message(self) -> str:
        lines = [f"ТЗ:\n{self._task.tz_text}"]
        if self._task.reference_urls:
            lines.append("Референсы (URL): " + ", ".join(self._task.reference_urls))
        if self._task.attachments:
            lines.append(f"Прикреплено изображений: {len(self._task.attachments)}")
        return "\n\n".join(lines)

    async def clarify(self, answers: str) -> dict:
        """Re-estimate after user provided clarification answers.

        We rebuild the FULL clarification thread of *this* task (every prior
        question/answer round from clarify_qa) so the agent keeps the entire
        context of the active task between rounds — not just the last question.
        Note: this context is scoped to a single task; history of *other* tasks
        is never included, so token usage does not grow across tasks.
        """
        site_context = self._build_site_context()
        original_tz = self._task.tz_text or ""

        # Render all completed Q&A rounds; the last round (pending questions with
        # answer=None) is paired with the answers just provided by the user.
        thread_parts = [f"ТЗ:\n{original_tz}"]
        qa_history = self._task.clarify_qa or []
        for turn in qa_history:
            questions = turn.get("questions") or []
            answer = turn.get("answer")
            if questions:
                thread_parts.append(
                    "Уточняющие вопросы:\n" + "\n".join(f"- {q}" for q in questions)
                )
            if answer:
                thread_parts.append(f"Ответы пользователя:\n{answer}")
        # Newest answer (for the last, still-unanswered round)
        thread_parts.append(f"Ответы пользователя:\n{answers}")

        combined_message = "\n\n".join(thread_parts)
        if self._task.reference_urls:
            combined_message += "\n\nРефересы (URL): " + ", ".join(self._task.reference_urls)

        layer = resolve("task_estimator")
        claude = ClaudeClient(model=layer.model)
        result = claude.call_with_system(
            system=layer.system_prompt,
            messages=[
                {"role": "user", "content": site_context},
                {"role": "assistant", "content": "Понял контекст сайта. Жду ваше ТЗ."},
                {"role": "user", "content": combined_message},
            ],
            max_tokens=layer.max_tokens,
        )
        return self._parse_response(result["content"])

    def _parse_response(self, content: str) -> dict:
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: create a single subtask from the whole TZ
            data = {
                "title": (self._task.tz_text or "Задача")[:80],
                "subtasks": [{
                    "id": "st_1",
                    "title": "Выполнить ТЗ",
                    "description": self._task.tz_text or "",
                    "files_to_touch": [],
                    "estimated_credits": 10,
                    "risk": "medium",
                }],
                "total_credits": 10,
                "confidence": "low",
                "estimated_minutes": 10,
            }
        # needs_clarification — return as-is (handled by API layer)
        if data.get("status") == "needs_clarification":
            return data
        # Ensure all subtasks have an id
        for i, st in enumerate(data.get("subtasks", [])):
            if not st.get("id"):
                st["id"] = f"st_{i+1}"
        return data
