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
    def __init__(self, site: Site, task: Task, ssh=None, previous_tasks=None) -> None:
        self._site = site
        self._task = task
        self._ssh = ssh  # SSHClient | None  — live SSH for fresh file reads
        self._previous_tasks: list = list(previous_tasks or [])

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

        # ── Task history context ───────────────────────────────────────────────
        history = self._build_task_history_context()
        if history:
            parts.append(history)

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
        if site.framework:
            parts.append(f"Фреймворк: {site.framework}")
        if site.is_docker is not None:
            parts.append(f"Docker: {'да' if site.is_docker else 'нет'}")
        if site.docker_compose_dir:
            parts.append(f"Docker Compose dir: {site.docker_compose_dir}")
        if site.docker_service_name:
            parts.append(f"Docker сервис: {site.docker_service_name}")

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

        # ── Design system: always fetch for frontend frameworks ───────────────
        frontend_frameworks = {"nextjs", "react", "vue", "nuxt", "vite", "angular"}
        if self._ssh and site.site_root_path and (site.cms or "") in frontend_frameworks:
            try:
                design_ctx = self._extract_design_system(site.site_root_path)
                if design_ctx:
                    parts.insert(1, design_ctx)  # right after КОНТЕКСТ САЙТА header
            except Exception:
                pass

        # Include actual file contents so Claude sees real code
        for path, content in file_contents.items():
            parts.append(f"\n--- {path} ---\n{content}")

        if site.installed_plugins:
            active = site.installed_plugins.get("active", [])
            if active:
                parts.append("Активные плагины: " + ", ".join(active[:20]))

        return "\n".join(parts)

    def _build_task_history_context(self) -> str:
        """Return a formatted summary of recent completed tasks for the estimator.

        Gives Claude the vocabulary to understand follow-up messages like
        "the changes didn't apply" — it can reference specific files and
        what was attempted without the user having to repeat themselves.
        """
        if not self._previous_tasks:
            return ""
        status_ru = {
            "done": "выполнено", "failed": "ошибка",
            "rolled_back": "откатано", "running": "выполняется",
        }
        lines = ["ИСТОРИЯ ЗАДАЧ САЙТА (последние выполненные):"]
        for i, t in enumerate(self._previous_tasks[:5], 1):
            st = status_ru.get(t.status, t.status)
            title = (t.title or (t.tz_text or ""))[:70]
            ts = ""
            if getattr(t, "updated_at", None):
                ts = t.updated_at.strftime("%d %b %H:%M")
            lines.append(f"\n[{i}] «{title}» — {st} {ts}".rstrip())
            if t.changed_files:
                lines.append(f"    Изменены файлы: {', '.join(t.changed_files[:6])}")
            if t.file_diffs:
                diffs = [
                    f"{p.split('/')[-1]} (+{d.get('added', 0)}-{d.get('removed', 0)})"
                    for p, d in list(t.file_diffs.items())[:4]
                ]
                lines.append(f"    Правки: {', '.join(diffs)}")
            if t.status == "failed" and getattr(t, "error_message", None):
                lines.append(f"    Ошибка: {(t.error_message or '')[:120]}")
        return "\n".join(lines)

    # ── Design-system files: always read for frontend projects ────────────────
    _DESIGN_SYSTEM_FILES = [
        "tailwind.config.js", "tailwind.config.ts",
        "src/index.css", "src/styles/global.css", "src/styles/globals.css",
        "app/globals.css", "src/styles/variables.css", "src/tokens.css", "src/theme.ts",
    ]
    _COMPONENT_DIRS = [
        "src/components/ui", "src/components/shared", "components/ui", "src/ui",
    ]
    # Within component dirs these names get priority so Claude sees core patterns first
    _COMPONENT_PRIORITY = ("button", "card", "badge", "input", "modal")

    def _extract_design_system(self, root: str) -> str:
        """Read tailwind config, global CSS and shared UI components.

        Returns a formatted string to prepend to the site context so the estimator
        (and via the same helper, the executor) knows the real design tokens and
        existing component patterns before planning any changes.
        """
        parts: list[str] = ["ДИЗАЙН-СИСТЕМА:"]

        # 1. Config + global CSS files
        for rel in self._DESIGN_SYSTEM_FILES:
            path = f"{root}/{rel}"
            rc, content, _ = self._ssh.run(f"cat {path!r} 2>/dev/null | head -200", timeout=15)
            if rc == 0 and content.strip():
                parts.append(f"--- {path} ---\n{content.strip()}")

        # 2. Shared UI components (Button, Card, … — highest priority first)
        for comp_dir_rel in self._COMPONENT_DIRS:
            comp_dir = f"{root}/{comp_dir_rel}"
            rc, listing, _ = self._ssh.run(
                f"ls {comp_dir!r} 2>/dev/null | head -30", timeout=10
            )
            if rc != 0 or not listing.strip():
                continue
            files = [f.strip() for f in listing.splitlines() if f.strip()]
            # Sort: priority names first, then alphabetical
            def _prio(name: str) -> int:
                n = name.lower()
                for i, p in enumerate(self._COMPONENT_PRIORITY):
                    if n.startswith(p):
                        return i
                return len(self._COMPONENT_PRIORITY)
            files.sort(key=_prio)
            for fname in files[:5]:
                path = f"{comp_dir}/{fname}"
                rc, content, _ = self._ssh.run(
                    f"cat {path!r} 2>/dev/null | head -150", timeout=15
                )
                if rc == 0 and content.strip():
                    parts.append(f"--- {path} ---\n{content.strip()}")
            break  # first existing component dir is enough

        return "\n".join(parts) if len(parts) > 1 else ""

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

        # If site_root_path itself is a build artifact dir, resolve to source root
        root = root.rstrip("/")
        last_segment = root.split("/")[-1]
        if last_segment in ("dist", "build", ".next", "out", "public"):
            parent = root.rsplit("/", 1)[0]
            # Prefer parent if it has package.json or src/
            has_pkg = scanner._run(f"[ -f '{parent}/package.json' ] && echo yes || echo no")
            has_src = scanner._run(f"[ -d '{parent}/src' ] || [ -d '{parent}/app' ] && echo yes || echo no")
            if has_pkg == "yes" or has_src == "yes":
                root = parent

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

        # Literal term extraction — abbreviations and quoted names from the TZ text.
        # These are domain-specific identifiers the user wrote that appear verbatim
        # in code (e.g. "ЧЗ", "SKU", `labelField`), not generic CSS keywords.
        # Skip noise words that match many files and add no signal.
        _LITERAL_SKIP = {
            "CSS", "JS", "TS", "URL", "API", "UI", "UX", "БД", "ТЗ",
            "HTML", "JSON", "SSH", "HTTP", "PHP", "SQL",
        }
        # Uppercase Cyrillic abbreviations: ЧЗ, НДС, АИС, etc.
        for word in re.findall(r'\b[А-ЯЁ]{2,6}\b', tz_text):
            if word not in _LITERAL_SKIP and re.escape(word) not in terms:
                terms.append(re.escape(word))
        # Uppercase Latin abbreviations (not already filtered as common): SKU, EAN, etc.
        for word in re.findall(r'\b[A-Z]{2,6}\b', tz_text):
            if word not in _LITERAL_SKIP and re.escape(word) not in terms:
                terms.append(re.escape(word))
        # Quoted / backtick-quoted names: "поле X", `blockName`, «Блок ЧЗ»
        for word in re.findall(r'["`«»]([^"`«»]{2,30})["`«»]', tz_text):
            w = word.strip()
            if w and re.escape(w) not in terms:
                terms.append(re.escape(w))

        return terms[:7] if terms else ["background", "color", "a[^,{]*{"]

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
