"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

/* ─── Types ──────────────────────────────────────────────────────────────── */
type FileStructure = { root?: string; entries?: string[] } | null;

type Site = {
  id: string; name: string; url: string | null; status: string;
  ssh_host?: string | null; server_ip?: string | null;
  cms: string | null; cms_version: string | null; web_server: string | null;
  php_version?: string | null; server_os?: string | null;
  site_root_path?: string | null;
  is_docker?: boolean; framework?: string;
  file_structure?: FileStructure;
};

type FileDiff = { added: number; removed: number };

type Subtask = {
  id: string; title: string; description: string;
  files_to_touch: string[]; estimated_credits: number;
  risk: "low" | "medium" | "high"; enabled: boolean;
};

type TaskEstimate = {
  task_id: string; subtasks: Subtask[];
  total_credits: number; confidence: string; estimated_minutes: number;
};

type Clarification = {
  task_id: string; status: "needs_clarification";
  summary: string; questions: string[];
};

// TaskPublic from the backend (used to rebuild the thread after a refresh)
type Task = {
  id: string; site_id: string; title: string | null; tz_text: string | null;
  status: string; subtasks: Subtask[] | null;
  estimated_credits: number | null; estimated_minutes: number | null;
  confidence: string | null;
  clarify_qa: { questions: string[]; answer: string | null }[] | null;
  changed_files: string[] | null; error_message: string | null;
  file_diffs: Record<string, FileDiff> | null;
  backup_available: boolean; created_at: string;
};

type LogLine = {
  type: string; subtask_index: number | null;
  status: string; message: string; timestamp: string;
};

// ── Chat message union ──────────────────────────────────────────────────────
type MsgUser = { kind: "user"; text: string; attachments?: number; ref?: string };
type MsgAnalyzing = { kind: "analyzing" };
type MsgClarify = { kind: "clarify"; data: Clarification };
type MsgEstimate = { kind: "estimate"; data: TaskEstimate; subtasks: Subtask[] };
type MsgRunning = { kind: "running"; taskId: string; backupAvailable?: boolean; isRollback?: boolean };
type MsgDone = { kind: "done"; status: string; taskId: string; logs: LogLine[] | null; backupAvailable?: boolean; errorMessage?: string | null };
type MsgError = { kind: "error"; text: string };

type ChatMsg = MsgUser | MsgAnalyzing | MsgClarify | MsgEstimate | MsgRunning | MsgDone | MsgError;

type Tab = "tasks" | "audit" | "history";
const RISK = { low: "bg-emerald-50 text-emerald-700 border-emerald-100", medium: "bg-amber-50 text-amber-700 border-amber-100", high: "bg-red-50 text-red-700 border-red-100" };

const INITIAL_TASKS = 15;       // how many recent tasks to render on first load
const RUNNING_STATUSES = new Set(["approved", "running", "rolling_back"]);

// Pending clarification: { taskId, answered }
type PendingClarify = { taskId: string } | null;

/* ─── Agent avatar ────────────────────────────────────────────────────────── */
function AgentAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
      </svg>
    </div>
  );
}

/* ─── Agent bubble wrapper ────────────────────────────────────────────────── */
function AgentBubble({ children, label }: { children: React.ReactNode; label?: string }) {
  return (
    <div className="flex gap-3 items-start">
      <AgentAvatar />
      <div className="flex-1 min-w-0 bg-surface rounded-2xl rounded-tl-sm border border-border shadow-card px-4 py-3">
        <p className="text-xs font-semibold text-accent mb-2">{label || "SiteDoc AI"}</p>
        {children}
      </div>
    </div>
  );
}

/* ─── Log block (light) ───────────────────────────────────────────────────── */
function LogBlock({ logs, running, siteId, taskId, lazy, autoExpand, onRollback, onNew, rolledBack, errorMessage }: {
  logs?: LogLine[]; running: boolean;
  siteId?: string; taskId?: string; lazy?: boolean; autoExpand?: boolean;
  onRollback?: () => void; onNew?: () => void; rolledBack?: boolean; errorMessage?: string | null;
}) {
  const [collapsed, setCollapsed] = useState(!running && !autoExpand);
  const [fetched, setFetched] = useState<LogLine[] | null>(null);
  const [loading, setLoading] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const effectiveLogs = logs ?? fetched ?? [];

  // Lazily load persisted logs for finished tasks (on first expand).
  useEffect(() => {
    if (collapsed || !lazy || logs || fetched || loading) return;
    if (!siteId || !taskId) return;
    setLoading(true);
    api.get<LogLine[]>(`/api/sites/${siteId}/tasks/${taskId}/logs`)
      .then(({ data }) => setFetched(data.map(d => ({ ...d, type: "log" }))))
      .catch(() => setFetched([]))
      .finally(() => setLoading(false));
  }, [collapsed, lazy, logs, fetched, loading, siteId, taskId]);

  useEffect(() => {
    if (logRef.current && running) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [effectiveLogs, running]);

  const successCount = effectiveLogs.filter(l => l.status === "success").length;
  const errorCount = effectiveLogs.filter(l => l.status === "error").length;

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2">
          {running ? (
            <svg className="animate-spin text-accent" width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="14 10"/>
            </svg>
          ) : rolledBack ? (
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400"/>
          ) : errorCount > 0 ? (
            <span className="w-2.5 h-2.5 rounded-full bg-red-400"/>
          ) : (
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"/>
          )}
          <span className="text-xs font-medium text-gray-600">
            {running ? "выполняется..."
              : rolledBack ? "откатено"
              : effectiveLogs.length === 0 ? "лог"
              : `${successCount} успешно${errorCount > 0 ? ` · ${errorCount} ошибок` : ""}`}
          </span>
          {running && (
            <span className="flex items-center gap-1 text-xs text-accent/70 ml-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"/>
              live
            </span>
          )}
        </div>
        <button
          onClick={() => setCollapsed(v => !v)}
          className="text-xs text-slate-400 hover:text-slate-600 transition-colors px-2 py-0.5 rounded-lg hover:bg-slate-100"
        >
          {collapsed ? "развернуть ▼" : "свернуть ▲"}
        </button>
      </div>

      {/* Log lines */}
      {!collapsed && (
        <div ref={logRef} className="px-4 py-3 font-mono text-xs space-y-1.5 max-h-64 overflow-y-auto bg-white">
          {effectiveLogs.length === 0 && (running || loading) && (
            <div className="flex items-center gap-2 text-slate-400">
              <svg className="animate-spin" width="10" height="10" viewBox="0 0 10 10" fill="none">
                <circle cx="5" cy="5" r="3.5" stroke="currentColor" strokeWidth="1.2" strokeDasharray="12 8"/>
              </svg>
              <span>{loading ? "загружаю логи..." : "подключаюсь к серверу..."}</span>
            </div>
          )}
          {effectiveLogs.length === 0 && !running && !loading && errorMessage && (
            <div className="flex items-start gap-2 text-red-600 leading-relaxed">
              <span className="flex-shrink-0 select-none w-3 text-center">✗</span>
              <span className="break-all">{errorMessage}</span>
            </div>
          )}
          {effectiveLogs.length === 0 && !running && !loading && !errorMessage && (
            <span className="text-slate-400 italic">логи не сохранились</span>
          )}
          {effectiveLogs.map((log, i) => (
            <div key={i} className={`flex items-start gap-2 leading-relaxed ${
              log.status === "success" ? "text-emerald-700" :
              log.status === "error" ? "text-red-600" :
              log.status === "rollback" ? "text-amber-600" :
              log.message?.startsWith("━━━") ? "text-slate-700 font-medium" :
              "text-slate-500"
            }`}>
              <span className="flex-shrink-0 select-none w-3 text-center">
                {log.status === "success" ? "✓" : log.status === "error" ? "✗" :
                 log.status === "rollback" ? "↩" : log.message?.startsWith("━━━") ? "▶" : "·"}
              </span>
              <span className="break-all">{log.message}</span>
            </div>
          ))}
          {running && effectiveLogs.length > 0 && (
            <span className="text-gray-300 animate-pulse">█</span>
          )}
        </div>
      )}

      {/* Done actions */}
      {!running && (onRollback || onNew || rolledBack) && (
        <div className="px-4 py-2.5 border-t border-slate-200 bg-white flex gap-2 items-center">
          {rolledBack && (
            <span className="text-xs text-amber-600 flex items-center gap-1">↩ Изменения откатены</span>
          )}
          {onRollback && (
            <button onClick={onRollback} className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-xl hover:bg-gray-50 transition-colors">
              ↩ Откатить
            </button>
          )}
          {onNew && (
            <button onClick={onNew} className="text-xs text-white bg-accent hover:bg-accent-hover px-3 py-1.5 rounded-xl transition-colors ml-auto">
              Новая задача
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── File tree (built from the flat scan entry list) ─────────────────────── */
type TreeNode = { name: string; path: string; children: Map<string, TreeNode>; isFile: boolean };

function buildTree(structure: FileStructure): TreeNode | null {
  if (!structure?.entries?.length) return null;
  const root = (structure.root || "").replace(/\/+$/, "");
  const tree: TreeNode = { name: root.split("/").pop() || "/", path: root, children: new Map(), isFile: false };
  for (const entry of structure.entries) {
    const rel = root && entry.startsWith(root) ? entry.slice(root.length) : entry;
    const parts = rel.split("/").filter(Boolean);
    let node = tree;
    let acc = root;
    parts.forEach((part, i) => {
      acc += "/" + part;
      const isFile = i === parts.length - 1 && /\.[a-z0-9]+$/i.test(part);
      let child = node.children.get(part);
      if (!child) {
        child = { name: part, path: acc, children: new Map(), isFile };
        node.children.set(part, child);
      }
      node = child;
    });
  }
  return tree;
}

function FileTreeNode({ node, diffs, depth }: { node: TreeNode; diffs: Record<string, FileDiff>; depth: number }) {
  const [open, setOpen] = useState(depth === 0);
  const diff = diffs[node.path];

  if (node.isFile) {
    return (
      <div className="flex items-center gap-1 py-[2px] text-xs group" style={{ paddingLeft: depth * 14 + 2 }}>
        {/* file icon */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="flex-shrink-0 text-slate-400">
          <path d="M2 1h5.5L10 3.5V11H2V1z" stroke="currentColor" strokeWidth="1" fill="none"/>
          <path d="M7 1v3h3" stroke="currentColor" strokeWidth="1"/>
        </svg>
        <span className="truncate text-text-sub flex-1 min-w-0">{node.name}</span>
        {diff && (diff.added > 0 || diff.removed > 0) && (
          <span className="flex-shrink-0 flex items-center gap-0.5 font-mono text-[10px]">
            {diff.added > 0 && <span className="text-emerald-600">+{diff.added}</span>}
            {diff.removed > 0 && <span className="text-red-500">−{diff.removed}</span>}
          </span>
        )}
      </div>
    );
  }

  const children = [...node.children.values()].sort((a, b) => {
    if (a.isFile !== b.isFile) return a.isFile ? 1 : -1;  // folders first
    return a.name.localeCompare(b.name);
  });

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 py-[2px] text-xs w-full hover:bg-surface-2 rounded-md transition-colors"
        style={{ paddingLeft: depth * 14 + 2 }}
      >
        {/* chevron */}
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="flex-shrink-0 text-slate-400 transition-transform" style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          <path d="M3 2L7 5L3 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        {/* folder icon */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="flex-shrink-0 text-amber-400">
          <path d="M1 3.5C1 2.67 1.67 2 2.5 2H4.5L5.5 3H9.5C10.33 3 11 3.67 11 4.5V8.5C11 9.33 10.33 10 9.5 10H2.5C1.67 10 1 9.33 1 8.5V3.5Z" fill="currentColor" fillOpacity="0.3" stroke="currentColor" strokeWidth="0.8"/>
        </svg>
        <span className="truncate text-text-main font-medium flex-1 min-w-0 text-left">{node.name || "/"}</span>
        {children.length > 0 && (
          <span className="flex-shrink-0 text-[10px] text-text-muted mr-1">{children.length}</span>
        )}
      </button>
      {open && (
        <div>
          {children.map((c) => <FileTreeNode key={c.path} node={c} diffs={diffs} depth={depth + 1} />)}
        </div>
      )}
    </div>
  );
}

/* ─── Project info column ─────────────────────────────────────────────────── */
function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between gap-2 py-1 text-xs">
      <span className="text-text-muted flex-shrink-0">{label}</span>
      <span className="text-text-main font-medium truncate text-right">{value}</span>
    </div>
  );
}

function ProjectInfo({ site, tasks, onRollback, onRescan, rescanning }: {
  site: Site | null; tasks: Task[]; onRollback: (taskId: string) => void;
  onRescan: () => void; rescanning: boolean;
}) {
  if (!site) return null;

  // Aggregate latest diff per file across all tasks (newest task wins).
  const diffs: Record<string, FileDiff> = {};
  for (const t of [...tasks].reverse()) {
    if (t.file_diffs) for (const [path, d] of Object.entries(t.file_diffs)) diffs[path] = d;
  }

  const tree = buildTree(site.file_structure ?? null);
  const restorePoints = tasks.filter((t) => t.backup_available);

  // Files that were changed but aren't inside the file tree (e.g. source files
  // when the tree shows the compiled dist/ directory). Display them separately.
  const treePathSet = new Set(site.file_structure?.entries ?? []);
  const orphanDiffs = Object.entries(diffs).filter(([p]) => !treePathSet.has(p));

  return (
    <aside className="w-72 bg-surface border-r border-border flex-shrink-0 overflow-y-auto">
      {/* Server / stack */}
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-2">Сервер и стек</h3>
        <InfoRow label="IP" value={site.server_ip || site.ssh_host} />
        <InfoRow label="CMS" value={site.cms ? `${site.cms}${site.cms_version ? " " + site.cms_version : ""}` : null} />
        <InfoRow label="Фреймворк" value={site.framework} />
        <InfoRow label="Веб-сервер" value={site.web_server} />
        <InfoRow label="PHP" value={site.php_version} />
        <InfoRow label="ОС" value={site.server_os} />
        {site.is_docker && <InfoRow label="Docker" value="да" />}
        <InfoRow label="Путь" value={site.site_root_path} />
      </div>

      {/* File tree */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wide">Структура проекта</h3>
          <button
            onClick={onRescan}
            disabled={rescanning}
            className="text-[10px] text-text-muted hover:text-accent transition-colors disabled:opacity-40"
            title="Пересканировать"
          >
            {rescanning ? "…" : "↻"}
          </button>
        </div>
        {tree ? (
          <div>
            {[...tree.children.values()].length === 0
              ? <FileTreeNode node={tree} diffs={diffs} depth={0} />
              : [...tree.children.values()]
                  .sort((a, b) => (a.isFile !== b.isFile ? (a.isFile ? 1 : -1) : a.name.localeCompare(b.name)))
                  .map((c) => <FileTreeNode key={c.path} node={c} diffs={diffs} depth={0} />)}
          </div>
        ) : (
          <p className="text-xs text-text-muted">Структура пока не просканирована.</p>
        )}
      </div>

      {/* Source files changed outside the file tree (e.g. edits to src/ when tree shows dist/) */}
      {orphanDiffs.length > 0 && (
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-2">Изменённые файлы</h3>
          <div className="space-y-0.5">
            {orphanDiffs.map(([path, d]) => (
              <div key={path} className="flex items-center justify-between gap-2 py-0.5">
                <span className="text-[11px] text-text-sub font-mono truncate" title={path}>{path.split("/").pop()}</span>
                <span className="flex-shrink-0 flex items-center gap-0.5 font-mono text-[10px]">
                  {d.added > 0 && <span className="text-emerald-600">+{d.added}</span>}
                  {d.removed > 0 && <span className="text-red-500">−{d.removed}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Backups / restore points */}
      <div className="px-4 py-3">
        <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-2">Точки восстановления</h3>
        {restorePoints.length === 0 ? (
          <p className="text-xs text-text-muted">Пока нет бэкапов. Появятся после выполнения задач.</p>
        ) : (
          <div className="space-y-2">
            {restorePoints.map((t) => (
              <div key={t.id} className="border border-border rounded-xl px-3 py-2 bg-surface-2">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                  <span className="text-xs font-medium text-text-main truncate">{t.title || t.tz_text || "Задача"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-text-muted">{new Date(t.created_at).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
                  <button
                    onClick={() => onRollback(t.id)}
                    className="text-[10px] text-text-sub border border-border px-2 py-0.5 rounded-lg hover:bg-surface-3 transition-colors"
                  >
                    ↩ Откатить
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

/* ─── Main page ───────────────────────────────────────────────────────────── */
export default function SitePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("tasks");
  const [site, setSite] = useState<Site | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [hiddenTasks, setHiddenTasks] = useState<Task[]>([]);  // older tasks not yet rendered
  const [allTasks, setAllTasks] = useState<Task[]>([]);        // raw tasks for the info column
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [input, setInput] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [pendingClarify, setPendingClarify] = useState<PendingClarify>(null);

  // Live log state per running task
  const [runningLogs, setRunningLogs] = useState<Record<string, LogLine[]>>({});
  const wsRef = useRef<Record<string, WebSocket>>({});

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { init(); /* eslint-disable-next-line */ }, [id]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, runningLogs]);

  // Close all sockets on unmount
  useEffect(() => () => { Object.values(wsRef.current).forEach(ws => ws.close()); }, []);

  /* ── Init: load site + history ───────────────────────────────────────────── */
  async function init() {
    try {
      const { data } = await api.get<Site>(`/api/sites/${id}`);
      setSite(data);
    } catch { router.push("/dashboard"); return; }
    await loadHistory();
  }

  /* ── Re-scan the site to refresh file structure ──────────────────────────── */
  async function handleRescan() {
    if (!site) return;
    setRescanning(true);
    try {
      await api.post(`/api/sites/${site.id}/scan`);
      const { data } = await api.get<Site>(`/api/sites/${site.id}`);
      setSite(data);
    } catch { /* ignore scan errors, keep stale data */ }
    finally { setRescanning(false); }
  }

  /* ── Load & reconstruct task history ─────────────────────────────────────── */
  async function loadHistory() {
    try {
      const { data } = await api.get<Task[]>(`/api/sites/${id}/tasks`);
      setAllTasks(data);  // newest-first, raw — used by the info column
      const chrono = [...data].reverse();  // backend returns newest-first
      const recent = chrono.slice(-INITIAL_TASKS);
      const older = chrono.slice(0, chrono.length - recent.length);

      const msgs = tasksToMessages(recent);
      setMessages(msgs);
      setHiddenTasks(older);

      // Bind input to the most recent task still awaiting clarification
      const lastClarifying = [...recent].reverse().find(t => t.status === "clarifying");
      if (lastClarifying) setPendingClarify({ taskId: lastClarifying.id });

      // Reconnect live streams for tasks still in progress
      recent.filter(t => RUNNING_STATUSES.has(t.status)).forEach(t => {
        setRunningLogs(p => ({ ...p, [t.id]: [] }));
        startWs(t.id);
      });
    } catch { /* keep empty thread */ }
    finally { setHistoryLoaded(true); }
  }

  function tasksToMessages(tasks: Task[]): ChatMsg[] {
    const out: ChatMsg[] = [];
    for (const t of tasks) {
      if (t.tz_text) out.push({ kind: "user", text: t.tz_text });

      // Full clarification dialogue (questions + answers), in order
      for (const turn of (t.clarify_qa || [])) {
        if (turn.questions?.length) {
          out.push({ kind: "clarify", data: { task_id: t.id, status: "needs_clarification", summary: "", questions: turn.questions } });
        }
        if (turn.answer) out.push({ kind: "user", text: turn.answer });
      }

      switch (t.status) {
        case "clarifying": {
          // If clarify_qa was empty, fall back to error_message for the pending questions
          if (!(t.clarify_qa || []).some(q => q.questions?.length) && t.error_message) {
            const questions = t.error_message.split("\n").filter(Boolean);
            out.push({ kind: "clarify", data: { task_id: t.id, status: "needs_clarification", summary: "", questions } });
          }
          break;
        }
        case "estimated":
          out.push({
            kind: "estimate",
            data: {
              task_id: t.id, subtasks: t.subtasks || [],
              total_credits: t.estimated_credits || 0,
              confidence: t.confidence || "medium",
              estimated_minutes: t.estimated_minutes || 10,
            },
            subtasks: (t.subtasks || []).map(s => ({ ...s, enabled: s.enabled !== false })),
          });
          break;
        case "approved":
        case "running":
        case "rolling_back":
          out.push({ kind: "running", taskId: t.id, backupAvailable: t.backup_available, isRollback: t.status === "rolling_back" });
          break;
        case "done":
        case "failed":
          out.push({ kind: "done", status: t.status, taskId: t.id, logs: null, backupAvailable: t.backup_available, errorMessage: t.error_message });
          break;
        case "rolled_back":
          out.push({ kind: "done", status: "rolled_back", taskId: t.id, logs: null, backupAvailable: false });
          break;
      }
    }
    return out;
  }

  function showEarlier() {
    if (!hiddenTasks.length) return;
    const older = tasksToMessages(hiddenTasks);
    setMessages(prev => [...older, ...prev]);
    setHiddenTasks([]);
  }

  /* ── Push message ──────────────────────────────────────────────────────── */
  function push(msg: ChatMsg) {
    setMessages(p => [...p, msg]);
  }

  function replaceLast(msg: ChatMsg) {
    setMessages(p => [...p.slice(0, -1), msg]);
  }

  /* ── Submit (new task OR clarification answer) ─────────────────────────── */
  async function handleSend(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    // If we're waiting for a clarification answer — route there
    if (pendingClarify) {
      const { taskId } = pendingClarify;
      push({ kind: "user", text });
      push({ kind: "analyzing" });
      setInput("");
      setBusy(true);

      try {
        const { data } = await api.post<TaskEstimate | Clarification>(
          `/api/sites/${id}/tasks/${taskId}/clarify`,
          { answers: text }
        );
        if ((data as Clarification).status === "needs_clarification") {
          const cl = data as Clarification;
          replaceLast({ kind: "clarify", data: cl });
          setPendingClarify({ taskId: cl.task_id });
        } else {
          const est = data as TaskEstimate;
          replaceLast({ kind: "estimate", data: est, subtasks: est.subtasks.map(s => ({ ...s, enabled: true })) });
          setPendingClarify(null);
        }
      } catch (err: any) {
        replaceLast({ kind: "error", text: err?.response?.data?.detail || "Ошибка" });
        setPendingClarify(null);
      } finally { setBusy(false); inputRef.current?.focus(); }
      return;
    }

    // New task
    push({ kind: "user", text, attachments: attachments.length || undefined, ref: refUrl || undefined });
    push({ kind: "analyzing" });
    setInput(""); setRefUrl(""); setAttachments([]);
    setBusy(true);

    try {
      const { data } = await api.post<TaskEstimate | Clarification>(`/api/sites/${id}/tasks`, {
        tz_text: text,
        reference_urls: refUrl ? [refUrl] : undefined,
        attachments: attachments.length ? attachments : undefined,
      });
      if ((data as Clarification).status === "needs_clarification") {
        const cl = data as Clarification;
        replaceLast({ kind: "clarify", data: cl });
        setPendingClarify({ taskId: cl.task_id });
      } else {
        const est = data as TaskEstimate;
        const subs = est.subtasks.map(s => ({ ...s, enabled: true }));
        replaceLast({ kind: "estimate", data: est, subtasks: subs });
        setPendingClarify(null);
      }
    } catch (err: any) {
      replaceLast({ kind: "error", text: err?.response?.data?.detail || "Ошибка анализа" });
      setPendingClarify(null);
    } finally { setBusy(false); inputRef.current?.focus(); }
  }

  /* ── Toggle subtask ─────────────────────────────────────────────────────── */
  function toggleSubtask(msgIdx: number, taskId: string) {
    setMessages(prev => prev.map((m, i) => {
      if (i !== msgIdx || m.kind !== "estimate") return m;
      const updated = m.subtasks.map(s => s.id === taskId ? { ...s, enabled: !s.enabled } : s);
      return { ...m, subtasks: updated };
    }));
  }

  /* ── Approve ────────────────────────────────────────────────────────────── */
  async function handleApprove(msgIdx: number, est: TaskEstimate, subtasks: Subtask[]) {
    if (busy) return;
    const enabledIds = subtasks.filter(s => s.enabled).map(s => s.id);
    setBusy(true);
    setPendingClarify(null);
    try {
      await api.post(`/api/sites/${id}/tasks/${est.task_id}/approve`, enabledIds);
      // Replace the estimate card with a running block
      setMessages(prev => prev.map((m, i) =>
        i === msgIdx ? { kind: "running", taskId: est.task_id, backupAvailable: true } : m
      ));
      setRunningLogs(p => ({ ...p, [est.task_id]: [] }));
      startWs(est.task_id);
    } catch (err: any) {
      push({ kind: "error", text: err?.response?.data?.detail || "Ошибка запуска" });
      setBusy(false);
    }
  }

  /* ── WebSocket ──────────────────────────────────────────────────────────── */
  function startWs(taskId: string) {
    wsRef.current[taskId]?.close();
    const token = localStorage.getItem("token");
    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/tasks/${taskId}?token=${token}`);
    wsRef.current[taskId] = ws;

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "log") {
        setRunningLogs(p => ({ ...p, [taskId]: [...(p[taskId] || []), msg] }));
      } else if (msg.type === "task_complete") {
        setRunningLogs(p => {
          const logs = p[taskId] || [];
          setMessages(prev => prev.map(m => {
            if (m.kind !== "running" || m.taskId !== taskId) return m;
            const rolledBack = msg.status === "rolled_back";
            return {
              kind: "done",
              status: msg.status,
              taskId,
              logs,
              backupAvailable: rolledBack ? false : (m.backupAvailable ?? true),
            };
          }));
          return p;
        });
        setBusy(false);
        ws.close();
        delete wsRef.current[taskId];
        // Refresh allTasks so the restore-points sidebar reflects the new backup
        loadHistory();
      }
    };
    ws.onerror = () => {
      setMessages(prev => prev.map(m =>
        m.kind === "running" && m.taskId === taskId
          ? { kind: "error", text: "WebSocket disconnected" }
          : m
      ));
      setBusy(false);
    };
  }

  /* ── Rollback ───────────────────────────────────────────────────────────── */
  async function handleRollback(taskId: string) {
    if (!confirm("Откатить все изменения по этой задаче? Для Docker-сайтов будет выполнена пересборка.")) return;
    try {
      await api.post(`/api/sites/${id}/tasks/${taskId}/rollback`);
      // Drop this restore point from the info column (backup is consumed)
      setAllTasks(prev => prev.map(t => t.id === taskId ? { ...t, backup_available: false } : t));
      // Switch the done block into a live rollback stream
      setRunningLogs(p => ({ ...p, [taskId]: [] }));
      setMessages(prev => prev.map(m =>
        m.kind === "done" && m.taskId === taskId
          ? { kind: "running", taskId, isRollback: true, backupAvailable: true }
          : m
      ));
      startWs(taskId);
    } catch (err: any) {
      push({ kind: "error", text: err?.response?.data?.detail || "Ошибка отката" });
    }
  }

  /* ── File ───────────────────────────────────────────────────────────────── */
  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files || []).forEach(file => {
      const r = new FileReader();
      r.onload = ev => {
        const b64 = (ev.target?.result as string).split(",")[1];
        setAttachments(p => [...p, b64]);
      };
      r.readAsDataURL(file);
    });
  }

  /* ── Keyboard ───────────────────────────────────────────────────────────── */
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend();
  }

  const canType = !busy;
  const inputPlaceholder = busy
    ? "Ожидаю ответа агента..."
    : pendingClarify
    ? "Ответьте на вопросы агента... (⌘↵ отправить)"
    : "Опишите задачу или ответьте на вопрос... (⌘↵ отправить)";

  /* ── Render ─────────────────────────────────────────────────────────────── */
  return (
    <div className="flex h-screen overflow-hidden bg-surface-2">

      {/* ── Sidebar ── */}
      <aside className="w-56 bg-surface border-r border-border flex flex-col flex-shrink-0">
        <div className="px-4 py-4 border-b border-border flex items-center gap-2 h-[57px]">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-sm text-text-main">SiteDoc</span>
        </div>

        <button onClick={() => router.push("/dashboard")}
          className="flex items-center gap-2 px-4 py-2.5 text-xs text-text-muted hover:text-text-main hover:bg-surface-2 transition-colors mx-2 mt-2 rounded-xl">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M7.5 9.5L4 6L7.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Все сайты
        </button>

        {site && (
          <div className="mx-2 mt-1 px-3 py-3 bg-surface-2 rounded-xl border border-border">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${site.status === "active" ? "bg-emerald-400" : "bg-red-400"}`}/>
              <span className="text-xs font-medium text-text-main truncate">{site.name}</span>
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {site.cms && <span className="text-[10px] text-text-muted">{site.cms}</span>}
              {site.is_docker && <span className="text-[10px] text-blue-500">Docker</span>}
              {site.framework && <span className="text-[10px] text-purple-500">{site.framework}</span>}
            </div>
          </div>
        )}

        <nav className="flex-1 px-2 mt-3 space-y-0.5">
          {(["tasks", "audit", "history"] as Tab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-colors ${
                tab === t ? "bg-accent text-white font-medium" : "text-text-sub hover:bg-surface-2 hover:text-text-main"
              }`}>
              <span className="text-base leading-none">
                {t === "tasks" ? "💬" : t === "audit" ? "🔍" : "📋"}
              </span>
              {t === "tasks" ? "Задачи" : t === "audit" ? "Аудит" : "История"}
            </button>
          ))}
        </nav>
      </aside>

      {/* ── Project info column ── */}
      <ProjectInfo site={site} tasks={allTasks} onRollback={handleRollback} onRescan={handleRescan} rescanning={rescanning} />

      {/* ── Main ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {tab === "tasks" && (
          <>
            {/* Chat thread */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">

              {/* Show earlier tasks */}
              {hiddenTasks.length > 0 && (
                <div className="max-w-2xl mx-auto w-full text-center">
                  <button
                    onClick={showEarlier}
                    className="text-xs text-text-muted hover:text-accent border border-border rounded-xl px-4 py-2 transition-colors bg-surface"
                  >
                    Показать предыдущие задачи ({hiddenTasks.length})
                  </button>
                </div>
              )}

              {/* Empty state — agent welcome bubble */}
              {historyLoaded && messages.length === 0 && (
                <div className="max-w-2xl mx-auto w-full">
                  <AgentBubble label="SiteDoc AI">
                    <p className="text-sm font-medium text-text-main mb-1">Привет! Проект подключён и просканирован 👋</p>
                    <p className="text-sm text-text-muted leading-relaxed">
                      Опишите задачу — что нужно изменить на сайте.<br/>
                      Можно вставить ТЗ целиком, агент разберётся и при необходимости задаст уточняющие вопросы.
                    </p>
                  </AgentBubble>
                </div>
              )}

              {/* Message thread */}
              {messages.map((msg, idx) => (
                <div key={idx} className="max-w-2xl mx-auto w-full">

                  {/* User message */}
                  {msg.kind === "user" && (
                    <div className="flex justify-end">
                      <div className="bg-accent text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-lg">
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                        {(msg.attachments || msg.ref) && (
                          <div className="mt-2 flex gap-2 text-white/60 text-xs">
                            {msg.ref && <span>🔗 {msg.ref}</span>}
                            {msg.attachments && <span>📎 {msg.attachments} файл(а)</span>}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Analyzing spinner */}
                  {msg.kind === "analyzing" && (
                    <div className="flex gap-3 items-center">
                      <AgentAvatar />
                      <div className="flex items-center gap-2 bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-card">
                        <svg className="animate-spin text-accent" width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="20 14"/>
                        </svg>
                        <span className="text-sm text-text-muted">Анализирую...</span>
                      </div>
                    </div>
                  )}

                  {/* Error */}
                  {msg.kind === "error" && (
                    <div className="flex gap-3 items-start">
                      <AgentAvatar />
                      <div className="bg-red-50 border border-red-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-red-600">
                        {msg.text}
                      </div>
                    </div>
                  )}

                  {/* Clarification */}
                  {msg.kind === "clarify" && (
                    <ClarifyMsg
                      data={msg.data}
                      pending={pendingClarify?.taskId === msg.data.task_id && idx === messages.length - 1}
                    />
                  )}

                  {/* Estimate */}
                  {msg.kind === "estimate" && (
                    <EstimateMsg
                      msgIdx={idx}
                      est={msg.data}
                      subtasks={msg.subtasks}
                      busy={busy}
                      onToggle={(taskId) => toggleSubtask(idx, taskId)}
                      onApprove={() => handleApprove(idx, msg.data, msg.subtasks)}
                    />
                  )}

                  {/* Running (execution OR rollback) */}
                  {msg.kind === "running" && (
                    <AgentBubble label={msg.isRollback ? "SiteDoc AI — откатываю" : "SiteDoc AI — выполняю"}>
                      <LogBlock
                        logs={runningLogs[msg.taskId] || []}
                        running={true}
                      />
                    </AgentBubble>
                  )}

                  {/* Done */}
                  {msg.kind === "done" && (
                    <AgentBubble label={
                      msg.status === "rolled_back" ? "SiteDoc AI — откатено ↩"
                      : msg.status === "done" ? "SiteDoc AI — выполнено ✓"
                      : "SiteDoc AI — завершено с ошибками"
                    }>
                      <LogBlock
                        logs={msg.logs?.length ? msg.logs : undefined}
                        lazy={!msg.logs || msg.logs.length === 0}
                        autoExpand={idx === messages.length - 1}
                        siteId={id}
                        taskId={msg.taskId}
                        running={false}
                        rolledBack={msg.status === "rolled_back"}
                        errorMessage={msg.errorMessage}
                        onRollback={msg.status === "done" && msg.backupAvailable ? () => handleRollback(msg.taskId) : undefined}
                        onNew={() => inputRef.current?.focus()}
                      />
                    </AgentBubble>
                  )}

                </div>
              ))}

              <div ref={bottomRef} />
            </div>

            {/* ── Input ── */}
            <div className={`border-t p-4 transition-colors ${pendingClarify ? "bg-accent/5 border-accent/20" : "bg-surface border-border"}`}>
              <div className="max-w-2xl mx-auto">
                {pendingClarify && (
                  <div className="flex items-center gap-2 mb-2 text-xs text-accent font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"/>
                    Агент ждёт ваш ответ
                  </div>
                )}
                {/* Attachments row */}
                {!pendingClarify && <div className="flex gap-2 mb-2">
                  <input
                    className="flex-1 text-sm border border-border rounded-xl px-3 py-2 bg-surface-2 text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
                    placeholder="🔗 Референс URL"
                    value={refUrl}
                    onChange={e => setRefUrl(e.target.value)}
                    disabled={!canType}
                  />
                  <label className={`flex items-center gap-1.5 text-xs border border-border rounded-xl px-3 py-2 cursor-pointer transition-colors ${canType ? "text-text-sub hover:text-text-main bg-surface-2 hover:bg-surface-3" : "text-text-muted opacity-50"}`}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 1V8M3 4.5L6 1.5L9 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M1 10H11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    </svg>
                    Файл
                    <input type="file" accept="image/*" multiple className="hidden" onChange={handleFile} disabled={!canType}/>
                  </label>
                  {attachments.length > 0 && (
                    <span className="self-center text-xs bg-accent/10 text-accent px-2 py-1 rounded-lg">
                      {attachments.length} прикреплено
                      <button onClick={() => setAttachments([])} className="ml-1 opacity-60 hover:opacity-100">×</button>
                    </span>
                  )}
                </div>}

                {/* Textarea */}
                <div className="relative">
                  <textarea
                    ref={inputRef}
                    className="w-full border border-border rounded-xl px-3.5 py-3 text-sm bg-surface-2 text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors resize-none"
                    style={{ minHeight: 52, maxHeight: 180 }}
                    placeholder={inputPlaceholder}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    disabled={!canType}
                    rows={2}
                    onInput={e => {
                      const t = e.target as HTMLTextAreaElement;
                      t.style.height = "auto";
                      t.style.height = Math.min(t.scrollHeight, 180) + "px";
                    }}
                  />
                  <button
                    onClick={() => handleSend()}
                    disabled={!canType || !input.trim()}
                    className="absolute bottom-2.5 right-2.5 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
                  >
                    {busy ? (
                      <svg className="animate-spin" width="11" height="11" viewBox="0 0 11 11" fill="none">
                        <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" strokeDasharray="14 10"/>
                      </svg>
                    ) : (
                      <>Отправить <kbd className="opacity-60 text-[10px]">⌘↵</kbd></>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {tab !== "tasks" && (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="w-12 h-12 rounded-2xl bg-surface-3 flex items-center justify-center mb-4 text-2xl">
              {tab === "audit" ? "🔍" : "📋"}
            </div>
            <p className="text-text-sub font-medium">{tab === "audit" ? "Аудит сайта" : "История задач"}</p>
            <p className="text-sm text-text-muted mt-1">В разработке</p>
          </div>
        )}
      </main>
    </div>
  );
}

/* ─── Clarify message ─────────────────────────────────────────────────────── */
function ClarifyMsg({ data, pending }: {
  data: Clarification; pending: boolean;
}) {
  return (
    <AgentBubble>
      {data.summary && (
        <p className="text-sm text-text-sub mb-3 pb-3 border-b border-border">{data.summary}</p>
      )}
      <p className="text-sm font-medium text-text-main mb-2">Уточните, пожалуйста:</p>
      <ol className="space-y-1.5">
        {data.questions.map((q, i) => (
          <li key={i} className="flex gap-2 text-sm text-text-main">
            <span className="text-accent font-semibold flex-shrink-0">{i + 1}.</span>
            <span>{q}</span>
          </li>
        ))}
      </ol>
      {pending && (
        <p className="mt-3 text-xs text-text-muted flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"/>
          Напишите ответ в поле ниже
        </p>
      )}
    </AgentBubble>
  );
}

/* ─── Estimate message ────────────────────────────────────────────────────── */
function EstimateMsg({ msgIdx, est, subtasks, busy, onToggle, onApprove }: {
  msgIdx: number; est: TaskEstimate; subtasks: Subtask[];
  busy: boolean;
  onToggle: (id: string) => void;
  onApprove: () => void;
}) {
  const totalEnabled = subtasks.filter(s => s.enabled).reduce((a, s) => a + s.estimated_credits, 0);
  const enabledCount = subtasks.filter(s => s.enabled).length;

  return (
    <AgentBubble>
      <p className="text-sm text-text-main mb-3">
        Нашёл <strong>{subtasks.length} задач{subtasks.length === 1 ? "у" : subtasks.length < 5 ? "и" : ""}</strong>.
        Снимите галочки с ненужного и нажмите <strong>Запустить</strong>.
      </p>
      <div className="flex flex-wrap gap-1.5 mb-4">
        <span className="text-xs bg-surface-2 border border-border text-text-sub px-2 py-1 rounded-lg">~{est.estimated_minutes} мин</span>
        <span className="text-xs bg-surface-2 border border-border text-text-sub px-2 py-1 rounded-lg">{est.total_credits.toFixed(0)} кредитов</span>
        <span className={`text-xs px-2 py-1 rounded-lg border ${
          est.confidence === "high" ? "bg-emerald-50 border-emerald-100 text-emerald-700" :
          est.confidence === "medium" ? "bg-amber-50 border-amber-100 text-amber-700" :
          "bg-red-50 border-red-100 text-red-600"
        }`}>
          {est.confidence === "high" ? "✓ Высокая точность" : est.confidence === "medium" ? "~ Средняя" : "⚠ Низкая точность"}
        </span>
      </div>

      {/* Subtask list */}
      <div className="border border-border rounded-xl overflow-hidden mb-3">
        {subtasks.map((st) => (
          <label key={st.id} className={`flex items-start gap-3 px-3.5 py-3 cursor-pointer transition-colors border-b last:border-0 border-border ${st.enabled ? "bg-surface hover:bg-surface-2" : "bg-surface-2 opacity-60"}`}>
            <input type="checkbox" checked={st.enabled} onChange={() => onToggle(st.id)} className="mt-0.5 accent-accent flex-shrink-0"/>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-text-main">{st.title}</span>
                <span className="text-xs text-text-muted flex-shrink-0">~{st.estimated_credits} кр.</span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">{st.description}</p>
              <div className="flex items-center gap-1.5 mt-1.5">
                {st.files_to_touch[0] && (
                  <span className="text-[10px] font-mono text-text-muted bg-surface-3 border border-border px-1.5 py-0.5 rounded truncate max-w-[200px]">
                    {st.files_to_touch[0].split("/").pop()}
                  </span>
                )}
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${RISK[st.risk]}`}>
                  {st.risk === "low" ? "низкий" : st.risk === "medium" ? "средний" : "высокий"} риск
                </span>
              </div>
            </div>
          </label>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">
          {enabledCount} из {subtasks.length} задач · {totalEnabled.toFixed(0)} кредитов
        </span>
        <button
          onClick={onApprove}
          disabled={busy || enabledCount === 0}
          className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-medium px-5 py-2 rounded-xl transition-colors flex items-center gap-2"
        >
          {busy ? (
            <>
              <svg className="animate-spin" width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="14 10"/>
              </svg>
              Запускаю...
            </>
          ) : "▶ Запустить"}
        </button>
      </div>
    </AgentBubble>
  );
}
