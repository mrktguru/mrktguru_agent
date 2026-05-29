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

type Clarification = {
  task_id: string; status: "needs_clarification";
  summary: string; questions: string[];
};

type LogLine = {
  type: string; subtask_index: number | null;
  status: string; message: string; timestamp: string;
};

type Stage = "input" | "clarifying" | "estimated" | "running" | "done";
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
  const [clarification, setClarification] = useState<Clarification | null>(null);
  const [clarifyAnswer, setClarifyAnswer] = useState("");
  const [subtasks, setSubtasks] = useState<Subtask[]>([]);
  const [approving, setApproving] = useState(false);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [taskStatus, setTaskStatus] = useState("");
  const [stage, setStage] = useState<Stage>("input");
  const [loadingPending, setLoadingPending] = useState(false);
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
      // Check if there's a pending task from onboarding quiz
      const pendingTaskId = localStorage.getItem(`pendingTask_${id}`);
      if (pendingTaskId) {
        localStorage.removeItem(`pendingTask_${id}`);
        loadPendingTask(pendingTaskId);
      }
    } catch { router.push("/dashboard"); }
  }

  async function loadPendingTask(taskId: string) {
    setLoadingPending(true);
    try {
      // Fetch the already-estimated task
      const { data } = await api.get<TaskEstimate & { tz_text?: string }>(`/api/tasks/${taskId}`);
      setEstimate({ task_id: taskId, subtasks: data.subtasks || [], total_credits: data.total_credits || 0, confidence: data.confidence || "medium", estimated_minutes: data.estimated_minutes || 10 });
      setSubtasks((data.subtasks || []).map((s: Subtask) => ({ ...s, enabled: true })));
      setStage("estimated");
    } catch {
      // Task might not be in the right format, ignore
    } finally {
      setLoadingPending(false);
    }
  }

  async function handleSubmitTz(e: React.FormEvent) {
    e.preventDefault();
    if (!tz.trim()) return;
    setSending(true);
    try {
      const { data } = await api.post<TaskEstimate | Clarification>(`/api/sites/${id}/tasks`, {
        tz_text: tz,
        reference_urls: referenceUrl ? [referenceUrl] : undefined,
        attachments: attachments.length ? attachments : undefined,
      });
      if ((data as Clarification).status === "needs_clarification") {
        setClarification(data as Clarification);
        setClarifyAnswer("");
        setStage("clarifying");
      } else {
        const est = data as TaskEstimate;
        setEstimate(est);
        setSubtasks(est.subtasks.map((s) => ({ ...s, enabled: true })));
        setStage("estimated");
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка анализа ТЗ");
    } finally { setSending(false); }
  }

  async function handleSubmitClarification(e: React.FormEvent) {
    e.preventDefault();
    if (!clarifyAnswer.trim() || !clarification) return;
    setSending(true);
    try {
      const { data } = await api.post<TaskEstimate | Clarification>(
        `/api/sites/${id}/tasks/${clarification.task_id}/clarify`,
        { answers: clarifyAnswer }
      );
      if ((data as Clarification).status === "needs_clarification") {
        setClarification(data as Clarification);
        setClarifyAnswer("");
      } else {
        const est = data as TaskEstimate;
        setEstimate(est);
        setSubtasks(est.subtasks.map((s) => ({ ...s, enabled: true })));
        setClarification(null);
        setStage("estimated");
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка");
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
    setEstimate(null); setClarification(null); setClarifyAnswer("");
    setSubtasks([]); setLogs([]); setTaskStatus("");
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

              {/* Loading pending task from onboarding */}
              {loadingPending && (
                <div className="max-w-xl mx-auto flex flex-col items-center justify-center mt-20 gap-3">
                  <svg className="animate-spin text-accent" width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" strokeDasharray="40 20"/>
                  </svg>
                  <p className="text-sm text-text-sub">Загружаю анализ вашего ТЗ...</p>
                </div>
              )}

              {stage === "input" && !loadingPending && (
                <div className="max-w-xl mx-auto text-center mt-16">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl">✏️</span>
                  </div>
                  <h2 className="text-lg font-semibold text-text-main mb-2">Опишите задачу</h2>
                  <p className="text-sm text-text-muted">Вставьте ТЗ или напишите что нужно изменить на сайте</p>
                </div>
              )}

              {/* ── Clarification flow ── */}
              {stage === "clarifying" && clarification && (
                <div className="max-w-2xl mx-auto space-y-4">
                  {/* User's original message */}
                  <div className="flex justify-end">
                    <div className="bg-accent text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-lg">
                      <p className="text-sm">{tz}</p>
                    </div>
                  </div>

                  {/* Agent clarification bubble */}
                  <div className="flex gap-3">
                    <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                        <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div className="bg-surface rounded-2xl rounded-tl-sm border border-border shadow-card px-4 py-3 flex-1">
                      <p className="text-xs font-semibold text-accent mb-2">SiteDoc AI</p>
                      {clarification.summary && (
                        <p className="text-sm text-text-sub mb-3 pb-3 border-b border-border">{clarification.summary}</p>
                      )}
                      <p className="text-sm font-medium text-text-main mb-2">Уточните, пожалуйста:</p>
                      <ol className="space-y-1.5 mb-1">
                        {clarification.questions.map((q, i) => (
                          <li key={i} className="flex gap-2 text-sm text-text-main">
                            <span className="text-accent font-semibold flex-shrink-0">{i + 1}.</span>
                            <span>{q}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  {/* Answer input */}
                  <form onSubmit={handleSubmitClarification} className="ml-10">
                    <textarea
                      className="w-full border border-border rounded-xl px-3.5 py-3 text-sm bg-surface-2 text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors resize-none h-24"
                      placeholder="Ваш ответ..."
                      value={clarifyAnswer}
                      onChange={(e) => setClarifyAnswer(e.target.value)}
                      autoFocus
                    />
                    <div className="flex items-center justify-between mt-2">
                      <button type="button" onClick={resetAll} className="text-sm text-text-muted hover:text-text-main">
                        ← Начать заново
                      </button>
                      <button
                        type="submit"
                        disabled={sending || !clarifyAnswer.trim()}
                        className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-medium px-5 py-2 rounded-xl transition-colors flex items-center gap-2"
                      >
                        {sending ? (
                          <>
                            <svg className="animate-spin" width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="14 10"/>
                            </svg>
                            Анализирую...
                          </>
                        ) : "Ответить →"}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {stage === "estimated" && estimate && (
                <div className="max-w-2xl mx-auto space-y-4">
                  {/* Agent summary bubble */}
                  <div className="flex gap-3">
                    <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                        <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div className="bg-surface rounded-2xl rounded-tl-sm border border-border shadow-card px-4 py-3 flex-1">
                      <p className="text-xs font-semibold text-accent mb-2">SiteDoc AI</p>
                      <p className="text-sm text-text-main leading-relaxed mb-3">
                        Я изучил ваше ТЗ и проанализировал структуру сайта.
                        Нашёл <strong>{subtasks.length} задач{subtasks.length === 1 ? "у" : subtasks.length < 5 ? "и" : ""}</strong> для выполнения.
                        Проверьте список ниже — снимите галочки с того, что пока не нужно, и нажмите <strong>«Запустить»</strong>.
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="bg-surface-2 border border-border text-text-sub px-2 py-1 rounded-lg">
                          ~{estimate.estimated_minutes} мин
                        </span>
                        <span className="bg-surface-2 border border-border text-text-sub px-2 py-1 rounded-lg">
                          {estimate.total_credits.toFixed(0)} кредитов
                        </span>
                        <span className={`px-2 py-1 rounded-lg border ${
                          estimate.confidence === "high" ? "bg-emerald-50 border-emerald-100 text-emerald-700" :
                          estimate.confidence === "medium" ? "bg-amber-50 border-amber-100 text-amber-700" :
                          "bg-red-50 border-red-100 text-red-600"
                        }`}>
                          {estimate.confidence === "high" ? "✓ Высокая точность" : estimate.confidence === "medium" ? "~ Средняя точность" : "⚠ Низкая точность — уточните ТЗ"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Subtasks card */}
                  <div className="ml-10">
                    <div className="flex items-center gap-2 mb-2 px-1">
                      <p className="text-xs font-semibold text-text-sub uppercase tracking-wide">Задачи</p>
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

            {/* Input panel — only in input stage */}
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
