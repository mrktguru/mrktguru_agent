"""Mocked smoke test for the agentic executor loop. No real API / SSH."""
import types
import app.services.agent.task_executor as te


class Block:
    def __init__(self, type, text=None, name=None, input=None, id=None):
        self.type = type; self.text = text; self.name = name; self.input = input; self.id = id


class Resp:
    def __init__(self, content): self.content = content


SCRIPT = [
    Resp([Block("text", text="Ищу где фон у ссылок"),
          Block("tool_use", name="grep", input={"pattern": "bg-blue"}, id="t1")]),
    Resp([Block("tool_use", name="read_file", input={"path": "/app/src/Nav.tsx"}, id="t2")]),
    Resp([Block("tool_use", name="edit_file",
                input={"path": "/app/src/Nav.tsx", "action": "replace",
                       "find": "bg-blue-600", "content": ""}, id="t3")]),
    Resp([Block("text", text="Готово"),
          Block("tool_use", name="finish", input={"summary": "убрал bg у ссылки"}, id="t4")]),
]


class FakeClient:
    def __init__(self, model=None): pass
    def run_agent(self, system, messages, tools, max_tokens=0, thinking_tokens=0):
        # validate message threading: assistant turns must carry raw content blocks
        return SCRIPT.pop(0)


class FakeSSH:
    def run(self, cmd, timeout=60):
        if "grep" in cmd:
            return (0, '/app/src/Nav.tsx:5: <a className="bg-blue-600">link</a>', "")
        if cmd.strip().startswith("cat"):
            return (0, '<a className="bg-blue-600">link</a>', "")
        if "package.json" in cmd:
            return (0, "no", "")  # skip npm build
        return (0, "", "")


te.ClaudeClient = FakeClient
te.resolve = lambda key: types.SimpleNamespace(model="m", system_prompt="sys", max_tokens=8192, temperature=0)

site = types.SimpleNamespace(
    name="S", url=None, cms="react", cms_version="", framework="react",
    is_docker=False, docker_compose_dir=None, docker_service_name=None,
    needs_rebuild=False, site_root_path="/app/dist",
    file_structure={"entries": ["/app/src/Nav.tsx"]},
)
task = types.SimpleNamespace(id="tid", tz_text="убрать фон у ссылок", changed_files=None)

logs = []
ex = te.TaskExecutor(db=types.SimpleNamespace(), site=site, task=task, ssh=FakeSSH(),
                     log_callback=lambda m, s, i=None: logs.append(m))
ex._file_diffs = {}
edited = ex._run_agentic_subtask(0, {"title": "убрать фон у ссылок",
                                     "description": "у ссылок убрать bg-*"})
print("EDITED:", edited)
for l in logs:
    if any(k in l for k in ["grep", "read", "✏", "📝", "💭", "Контент", "отвеч"]):
        print("LOG:", l)
assert edited == ["/app/src/Nav.tsx"], f"unexpected: {edited}"
print("LOOP TEST PASSED")
