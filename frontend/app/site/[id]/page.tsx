"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Site = {
  id: string; name: string; url: string | null; status: string;
  cms: string | null; cms_version: string | null; web_server: string | null;
};

type Subtask = {
  id: string; title: string; description: string;
  files_to_touch: string[]; estimated_credits: number;
  risk: "low" | "medium" | "high"; enabled: boolean;
};

type TaskEstimate = {
  task_id: string; subtasks: Subtask[];
  total_credits: number; confidence: string; estimated_minutes: number;
};

type LogLine = {
  type: string; subtask_index: number | null;
  status: string; message: string; timestamp: string;
};

type Stage = "input" | "estimated" | "running" | "done";
type Tab = "tasks" | "audit" | "history";

const RISK_COLOR = { low: "text-emerald-600 bg-emerald-50", medium: "text-amber-600 bg-amber-50", high: "text-red-600 bg-red-50" };
const LOG_COLOR: Record<string, string> = {
  success: "text-emerald-600", error: "text-red-500",
  rollback: "text-amber-600", running: "text-text-sub",
};
const LOG_ICON: Record<string, string> = {
  success: "✓", error: "✗", rollback: "↩", running: "·",
};

export default function SitePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("tasks");
  const [site, setSite] = useState<Site | null>(null);
  const [tz, setTz] = useState("");
  const [referenceUrl, setReferenceUrl] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const [estimate, setEstimate] = useState<TaskEstimate | null>(null);
  const [subtasks, setSubtasks] = useState<Subtask[]>([]);
  const [approving, setApproving] = useState(false);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [taskStatus, setTaskStatus] = useState("");
  const [stage, setStage] = useState<Stage>("input");
  const logRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => { loadSite(); }, [id]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  async function loadSite() {
    try {
      const { data } = await api.get<Site>(`/api/sites/${id}`);
      setSite(data);
    } catch { router.push("/dashboard"); }
  }

  async function handleSubmitTz(e: React.FormEvent) {
    e.preventDefault();
    if (!tz.trim()) return;
    setSending(true);
    try {
      const { data } = await api.post<TaskEstimate>(`/api/sites/${id}/tasks`, {
        tz_text: tz,
        reference_urls: referenceUrl ? [referenceUrl] : undefined,
        attachments: attachments.length ? attachments : undefined,
      });
      setEstimate(data);
      setSubtasks(data.subtasks.map((s) => ({ ...s, enabled: true })));
      setStage("estimated");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка анализа ТЗ");
    } finally { setSending(false); }
  }

  async function handleApprove() {
    if (!estimate) return;
    setApproving(true);
    try {
      const enabledIds = subtasks.filter((s) => s.enabled).map((s) => s.id);
      await api.post(`/api/sites/${id}/tasks/${estimate.task_id}/approve`, enabledIds);
      setStage("running");
      startWs(estimate.task_id);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка запуска");
    } finally { setApproving(false); }
  }

  function startWs(taskId: string) {
    const token = localStorage.getItem("token");
    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/tasks/${taskId}?token=${token}`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "log") setLogs((p) => [...p, msg]);
      else if (msg.type === "task_complete") {
        setTaskStatus(msg.status);
        setStage("done");
        ws.close();
      }
    };
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files || []).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const b64 = (ev.target?.result as string).split(",")[1];
        setAttachments((p) => [...p, b64]);
      };
      reader.readAsDataURL(file);
    });
  }

  async function handleRollback() {
    if (!estimate || !confirm("Откатить все изменения?")) return;
    await api.post(`/api/sites/${id}/tasks/${estimate.task_id}/rollback`);
    resetAll();
  }

  function resetAll() {
    setStage("input"); setTz(""); setReferenceUrl(""); setAttachments([]);
    setEstimate(null); setSubtasks([]); setLogs([]); setTaskStatus("");
  }

  const totalEnabled = subtasks.filter((s) => s.enabled).reduce((a, s) => a + s.estimated_credits, 0);

  const TABS = [
    { key: "tasks" as Tab, icon: "💬", label: "Задачи" },
    { key: "audit" as Tab, icon: "🔍", label: "Аудит" },
    { key: "history" as Tab, icon: "📋", label: "История" },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-surface-2">

      {/* Sidebar */}
      <aside className="w-56 bg-surface border-r border-border flex flex-col">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-border flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-sm text-text-main">SiteDoc</span>
        </div>

        {/* Back */}
        <button
          onClick={() => router.push("/dashboard")}
          className="flex items-center gap-2 px-4 py-2.5 text-xs text-text-muted hover:text-text-main hover:bg-surface-2 transition-colors mx-2 mt-2 rounded-xl"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M7.5 9.5L4 6L7.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Все сайты
        </button>

        {/* Site info */}
        {site && (
          <div className="mx-2 mt-1 px-3 py-3 bg-surface-2 rounded-xl border border-border">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${site.status === "active" ? "bg-emerald-400" : "bg-red-400"}`} />
              <span className="text-xs font-medium text-text-main truncate">{site.name}</span>
            </div>
            {site.cms && <span className="text-xs text-text-muted">{site.cms}{site.cms_version ? ` ${site.cms_version}` : ""}</span>}
          </div>
        )}

        {/* Nav tabs */}
        <nav className="flex-1 px-2 mt-3 space-y-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-colors ${
                tab === t.key
                  ? "bg-accent text-white font-medium"
                  : "text-text-sub hover:bg-surface-2 hover:text-text-main"
              }`}
            >
              <span className="text-base leading-none">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">

        {tab === "tasks" && (
          <>
            {/* Chat/log area */}
            <div ref={logRef} className="flex-1 overflow-y-auto p-6">

              {stage === "input" && (
                <div className="max-w-xl mx-auto text-center mt-16">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl">✏️</span>
                  </div>
                  <h2 className="text-lg font-semibold text-text-main mb-2">Опишите задачу</h2>
                  <p className="text-sm text-text-muted">Вставьте ТЗ или напишите что нужно изменить на сайте</p>
                </div>
              )}

              {stage === "estimated" && estimate && (
                <div className="max-w-2xl mx-auto">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6L5 9L10 3" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <p className="text-sm font-medium text-text-main">Анализ выполнен — найдено {subtasks.length} задач</p>
                  </div>

                  <div className="bg-surface rounded-2xl border border-border shadow-card overflow-hidden">
                    <div className="divide-y divide-border">
                      {subtasks.map((st) => (
                        <label key={st.id} className={`flex items-start gap-3 px-4 py-3.5 cursor-pointer transition-colors ${st.enabled ? "bg-surface hover:bg-surface-2" : "bg-surface-2 opacity-60"}`}>
                          <input
                            type="checkbox" checked={st.enabled}
                            onChange={() => setSubtasks((p) => p.map((s) => s.id === st.id ? { ...s, enabled: !s.enabled } : s))}
                            className="mt-0.5 accent-accent"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2 mb-0.5">
                              <span className="text-sm font-medium text-text-main">{st.title}</span>
                              <span className="text-xs text-text-sub flex-shrink-0">~{st.estimated_credits} кред.</span>
                            </div>
                            <p className="text-xs text-text-muted mb-1.5">{st.description}</p>
                            <div className="flex items-center gap-2">
                              {st.files_to_touch[0] && (
                                <span className="text-xs font-mono text-text-muted bg-surface-3 px-1.5 py-0.5 rounded-md truncate max-w-xs">
                                  {st.files_to_touch[0].split("/").pop()}
                                </span>
                              )}
                              <span className={`text-xs px-1.5 py-0.5 rounded-md font-medium ${RISK_COLOR[st.risk]}`}>
                                {st.risk === "low" ? "низкий риск" : st.risk === "medium" ? "средний" : "высокий риск"}
                              </span>
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>

                    {/* Summary */}
                    <div className="bg-surface-2 border-t border-border px-4 py-3 flex items-center justify-between gap-4">
                      <div className="text-sm text-text-sub">
                        <span className="font-semibold text-text-main">{totalEnabled.toFixed(0)} кредитов</span>
                        <span className="mx-1">·</span>
                        <span>~{estimate.estimated_minutes} мин</span>
                        <span className="mx-1">·</span>
                        <span className={
                          estimate.confidence === "high" ? "text-emerald-600" :
                          estimate.confidence === "medium" ? "text-amber-600" : "text-red-600"
                        }>
                          {estimate.confidence === "high" ? "высокая точность" : estimate.confidence === "medium" ? "средняя точность" : "низкая точность"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={resetAll} className="text-sm text-text-sub hover:text-text-main px-3 py-1.5 rounded-xl hover:bg-surface-3 transition-colors">
                          Отмена
                        </button>
                        <button
                          onClick={handleApprove}
                          disabled={approving || subtasks.filter((s) => s.enabled).length === 0}
                          className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-xl transition-colors"
                        >
                          {approving ? "Запускаю..." : "Запустить"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {(stage === "running" || stage === "done") && (
                <div className="max-w-2xl mx-auto">
                  <div className="bg-surface rounded-2xl border border-border shadow-card overflow-hidden">
                    <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                      {stage === "running" ? (
                        <>
                          <svg className="animate-spin text-accent" width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="20 14"/>
                          </svg>
                          <span className="text-sm font-medium text-text-main">Выполняю задачи...</span>
                        </>
                      ) : (
                        <>
                          <span className={`text-sm font-medium ${taskStatus === "done" ? "text-emerald-600" : "text-red-500"}`}>
                            {taskStatus === "done" ? "✓ Все задачи выполнены" : "✗ Завершено с ошибками"}
                          </span>
                        </>
                      )}
                    </div>

                    <div className="px-4 py-3 font-mono text-xs space-y-1 max-h-80 overflow-y-auto">
                      {logs.map((log, i) => (
                        <div key={i} className={`flex items-start gap-2 ${LOG_COLOR[log.status] || "text-text-sub"}`}>
                          <span className="flex-shrink-0 w-3 text-center">{LOG_ICON[log.status] || "·"}</span>
                          <span>{log.message}</span>
                        </div>
                      ))}
                    </div>

                    {stage === "done" && (
                      <div className="px-4 py-3 border-t border-border flex gap-2">
                        <button onClick={handleRollback} className="text-sm text-text-sub border border-border px-3 py-1.5 rounded-xl hover:bg-surface-2 transition-colors">
                          ↩ Откатить
                        </button>
                        <button onClick={resetAll} className="text-sm text-white bg-accent hover:bg-accent-hover px-4 py-1.5 rounded-xl transition-colors">
                          Новая задача
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Input panel */}
            {stage === "input" && (
              <div className="bg-surface border-t border-border p-4">
                <form onSubmit={handleSubmitTz} className="max-w-2xl mx-auto space-y-3">
                  {/* Attachments row */}
                  <div className="flex gap-2">
                    <input
                      className="flex-1 text-sm border border-border rounded-xl px-3.5 py-2 bg-surface-2 text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
                      placeholder="🔗 URL референса (необязательно)"
                      value={referenceUrl}
                      onChange={(e) => setReferenceUrl(e.target.value)}
                    />
                    <label className="flex items-center gap-1.5 text-xs text-text-sub hover:text-text-main border border-border bg-surface-2 hover:bg-surface-3 rounded-xl px-3 py-2 cursor-pointer transition-colors">
                      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                        <path d="M6.5 1.5V9M3 5.5L6.5 2L10 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M1.5 10.5H11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                      </svg>
                      Файл
                      <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileChange} />
                    </label>
                    {attachments.length > 0 && (
                      <span className="self-center text-xs text-text-muted bg-accent/10 text-accent px-2 py-1 rounded-lg">
                        {attachments.length} прикреплено
                      </span>
                    )}
                  </div>

                  {/* TZ textarea */}
                  <div className="relative">
                    <textarea
                      className="w-full border border-border rounded-xl px-3.5 py-3 text-sm bg-surface-2 text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors resize-none h-32"
                      placeholder="Опишите задачу или вставьте ТЗ целиком..."
                      value={tz}
                      onChange={(e) => setTz(e.target.value)}
                    />
                    <button
                      type="submit"
                      disabled={sending || !tz.trim()}
                      className="absolute bottom-3 right-3 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {sending ? (
                        <>
                          <svg className="animate-spin" width="11" height="11" viewBox="0 0 11 11" fill="none">
                            <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" strokeDasharray="14 10"/>
                          </svg>
                          Анализирую
                        </>
                      ) : (
                        <>Отправить <span>↵</span></>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            )}
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
