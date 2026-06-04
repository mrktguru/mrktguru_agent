"""Mocked pause→serialize→resume round-trip test. No real API/SSH."""
import types
import app.services.agent.task_executor as te
from app.services.agent.task_executor import PauseSignal


class Block:
    def __init__(self, type, text=None, name=None, input=None, id=None):
        self.type = type; self.text = text; self.name = name; self.input = input; self.id = id
    def model_dump(self):
        d = {"type": self.type}
        if self.text is not None: d["text"] = self.text
        if self.name is not None: d["name"] = self.name
        if self.input is not None: d["input"] = self.input
        if self.id is not None: d["id"] = self.id
        return d


class Resp:
    def __init__(self, content): self.content = content


# step1: edit a file + request_user_input (siblings in one turn) → must pause
# step2 (resume): finish
SCRIPT = [
    Resp([
        Block("text", text="Пишу роуты OAuth, нужны секреты"),
        Block("tool_use", name="edit_file", id="e1",
              input={"path": "/app/src/auth.ts", "action": "create", "content": "// oauth routes"}),
        Block("tool_use", name="request_user_input", id="p1",
              input={"message": "Зарегистрируйте приложение в Yandex и пришлите client_id/secret",
                     "required_fields": ["YANDEX_CLIENT_ID", "YANDEX_CLIENT_SECRET"]}),
    ]),
    Resp([
        Block("text", text="Секреты на месте, завершаю"),
        Block("tool_use", name="finish", id="f1", input={"summary": "OAuth подключён"}),
    ]),
]


class FakeClient:
    def __init__(self, model=None): pass
    def run_agent(self, system, messages, tools, max_tokens=0, thinking_tokens=0):
        return SCRIPT.pop(0)


class FakeSSH:
    def run(self, cmd, timeout=60):
        if "package.json" in cmd:
            return (0, "no", "")
        return (0, "", "")


te.ClaudeClient = FakeClient
te.resolve = lambda key: types.SimpleNamespace(model="m", system_prompt="sys", max_tokens=8192, temperature=0)

site = types.SimpleNamespace(
    name="S", url=None, cms="react", cms_version="", framework="react",
    is_docker=False, docker_compose_dir=None, docker_service_name=None,
    needs_rebuild=False, site_root_path="/app", file_structure={"entries": []},
)
task = types.SimpleNamespace(id="tid", tz_text="вход через Yandex", changed_files=None,
                             task_type="integration", agent_state=None)
logs = []
ex = te.TaskExecutor(db=types.SimpleNamespace(), site=site, task=task, ssh=FakeSSH(),
                     log_callback=lambda m, s, i=None: logs.append(m))
ex._file_diffs = {}
ex._recent_edits = []

subtask = {"title": "OAuth Yandex", "description": "подключить вход", "track_type": "integration", "track_id": "tr_1"}

# ── 1. First run → must pause ────────────────────────────────────────────────
try:
    ex._run_agentic_subtask(0, subtask)
    print("FAIL: expected PauseSignal"); raise SystemExit(1)
except PauseSignal as p:
    rs = p.resume_state
    assert p.pending_input["required_fields"] == ["YANDEX_CLIENT_ID", "YANDEX_CLIENT_SECRET"], p.pending_input
    assert rs["pending_tool_use_id"] == "p1", rs["pending_tool_use_id"]
    # sibling edit_file must have a computed tool_result already
    assert any(r["tool_use_id"] == "e1" for r in rs["sibling_results"]), rs["sibling_results"]
    # messages must be JSON-serializable dicts (no SDK objects)
    import json
    json.dumps(rs["messages"])
    assert ex._recent_edits == ["/app/src/auth.ts"], ex._recent_edits
    print("PAUSE OK — serialized", len(rs["messages"]), "msgs; pending=p1; sibling e1 captured")

# ── 2. Resume with provided secrets → must finish ────────────────────────────
resume = dict(rs)
resume["provided_fields"] = {"YANDEX_CLIENT_ID": "abc", "YANDEX_CLIENT_SECRET": "xyz"}
ex._recent_edits = list(resume["recent_edits"])  # _execute_subtask does this in real flow
edited = ex._run_agentic_subtask(0, subtask, resume=resume)
print("RESUME OK — edited:", edited)
assert "/app/src/auth.ts" in edited, edited
print("PAUSE/RESUME ROUND-TRIP PASSED")
