"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Site = {
  id: string;
  name: string;
  url: string | null;
  status: string;
  cms: string | null;
  cms_version: string | null;
  web_server: string | null;
};

type Subtask = {
  id: string;
  title: string;
  description: string;
  files_to_touch: string[];
  estimated_credits: number;
  risk: "low" | "medium" | "high";
  enabled: boolean;
};

type TaskEstimate = {
  task_id: string;
  subtasks: Subtask[];
  total_credits: number;
  confidence: string;
  estimated_minutes: number;
};

type LogMessage = {
  type: string;
  subtask_index: number | null;
  status: string;
  message: string;
  timestamp: string;
};

type Tab = "tasks" | "audit" | "history";

const RISK_COLOR = { low: "text-green-400", medium: "text-yellow-400", high: "text-red-400" };
const STATUS_ICON: Record<string, string> = {
  running: "🔄",
  success: "✅",
  error: "✗",
  rollback: "↩",
};

export default function SitePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("tasks");
  const [site, setSite] = useState<Site | null>(null);

  // TZ input
  const [tz, setTz] = useState("");
  const [referenceUrl, setReferenceUrl] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [sending, setSending] = useState(false);

  // Estimate
  const [estimate, setEstimate] = useState<TaskEstimate | null>(null);
  const [subtasks, setSubtasks] = useState<Subtask[]>([]);
  const [approving, setApproving] = useState(false);

  // Live log
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [taskDone, setTaskDone] = useState(false);
  const [taskStatus, setTaskStatus] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Stage: input | estimated | running | done
  const [stage, setStage] = useState<"input" | "estimated" | "running" | "done">("input");

  useEffect(() => {
    loadSite();
  }, [id]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  async function loadSite() {
    try {
      const { data } = await api.get<Site>(`/api/sites/${id}`);
      setSite(data);
    } catch {
      router.push("/dashboard");
    }
  }

  // ── Submit TZ ─────────────────────────────────────────────────────────────

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
    } finally {
      setSending(false);
    }
  }

  // ── Approve ───────────────────────────────────────────────────────────────

  async function handleApprove() {
    if (!estimate) return;
    setApproving(true);
    const enabledIds = subtasks.filter((s) => s.enabled).map((s) => s.id);
    try {
      await api.post(`/api/sites/${id}/tasks/${estimate.task_id}/approve`, enabledIds);
      setStage("running");
      startWs(estimate.task_id);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка запуска");
    } finally {
      setApproving(false);
    }
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  function startWs(taskId: string) {
    const token = localStorage.getItem("token");
    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/tasks/${taskId}?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "log") {
        setLogs((prev) => [...prev, msg]);
      } else if (msg.type === "task_complete") {
        setTaskDone(true);
        setTaskStatus(msg.status);
        setStage("done");
        ws.close();
      }
    };
    ws.onerror = () => {
      setLogs((prev) => [...prev, { type: "log", subtask_index: null, status: "error", message: "WebSocket disconnected", timestamp: new Date().toISOString() }]);
    };
  }

  // ── File attachment ───────────────────────────────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const base64 = (ev.target?.result as string).split(",")[1];
        setAttachments((prev) => [...prev, base64]);
      };
      reader.readAsDataURL(file);
    });
  }

  // ── Rollback ──────────────────────────────────────────────────────────────

  async function handleRollback() {
    if (!estimate) return;
    if (!confirm("Откатить все изменения?")) return;
    try {
      await api.post(`/api/sites/${id}/tasks/${estimate.task_id}/rollback`);
      alert("Изменения откатены");
      resetAll();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Ошибка отката");
    }
  }

  function resetAll() {
    setStage("input");
    setTz("");
    setReferenceUrl("");
    setAttachments([]);
    setEstimate(null);
    setSubtasks([]);
    setLogs([]);
    setTaskDone(false);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const totalEnabled = subtasks.filter((s) => s.enabled).reduce((a, s) => a + s.estimated_credits, 0);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar nav */}
      <nav className="w-14 bg-gray-900 flex flex-col items-center py-4 gap-2 border-r border-gray-800">
        <button onClick={() => router.push("/dashboard")} className="text-gray-600 hover:text-white text-lg mb-4">←</button>
        {(["tasks", "audit", "history"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`w-10 h-10 rounded-lg text-xs flex flex-col items-center justify-center gap-0.5 transition-colors ${
              tab === t ? "bg-gray-700 text-white" : "text-gray-500 hover:text-white"
            }`}
          >
            {t === "tasks" ? "💬" : t === "audit" ? "🔍" : "📋"}
            <span className="text-[9px]">{t === "tasks" ? "задачи" : t === "audit" ? "аудит" : "история"}</span>
          </button>
        ))}
      </nav>

      {/* Main */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Site header */}
        {site && (
          <div className="px-4 py-2 border-b border-gray-800 flex items-center gap-3 text-sm">
            <span className={`w-2 h-2 rounded-full ${site.status === "active" ? "bg-green-400" : "bg-red-400"}`} />
            <span className="font-medium">{site.name}</span>
            {site.url && <span className="text-gray-500">{site.url}</span>}
            {site.cms && <span className="text-xs bg-gray-800 px-2 py-0.5 rounded">{site.cms} {site.cms_version || ""}</span>}
            {site.web_server && <span className="text-xs text-gray-600">{site.web_server}</span>}
          </div>
        )}

        {tab === "tasks" && (
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Log / chat area */}
            <div ref={logRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-1 text-sm">
              {stage === "input" && (
                <div className="text-gray-500 italic">💬 Готов к работе. Вставьте ТЗ или опишите задачу.</div>
              )}

              {/* Estimated subtasks */}
              {stage === "estimated" && estimate && (
                <div className="space-y-3">
                  <div className="text-gray-300">
                    Проанализировал ТЗ. Нашёл <strong>{subtasks.length}</strong> задач:
                  </div>
                  {subtasks.map((st, i) => (
                    <div key={st.id} className={`rounded-lg border p-3 ${st.enabled ? "border-gray-700" : "border-gray-800 opacity-50"}`}>
                      <div className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          checked={st.enabled}
                          onChange={() => setSubtasks((prev) => prev.map((s) => s.id === st.id ? { ...s, enabled: !s.enabled } : s))}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-sm">{st.title}</span>
                            <span className="text-xs text-gray-400 flex-shrink-0">~{st.estimated_credits} кред.</span>
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">{st.description}</div>
                          {st.files_to_touch.length > 0 && (
                            <div className="text-xs text-gray-600 mt-1 font-mono truncate">{st.files_to_touch[0]}{st.files_to_touch.length > 1 ? ` +${st.files_to_touch.length - 1}` : ""}</div>
                          )}
                          <span className={`text-xs ${RISK_COLOR[st.risk]}`}>риск: {st.risk}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                  <div className="border-t border-gray-800 pt-3 flex items-center justify-between">
                    <div className="text-sm text-gray-400">
                      Итого: <strong className="text-white">{totalEnabled.toFixed(0)} кредитов</strong>
                      {" · ~"}{estimate.estimated_minutes} мин
                      {" · "}
                      <span className={estimate.confidence === "high" ? "text-green-400" : estimate.confidence === "medium" ? "text-yellow-400" : "text-red-400"}>
                        {estimate.confidence === "high" ? "высокая" : estimate.confidence === "medium" ? "средняя" : "низкая"} уверенность
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={resetAll} className="text-sm text-gray-500 hover:text-white px-3 py-1.5">Отмена</button>
                      <button
                        onClick={handleApprove}
                        disabled={approving || subtasks.filter((s) => s.enabled).length === 0}
                        className="rounded-md bg-accent px-4 py-1.5 text-sm text-white disabled:opacity-50"
                      >
                        {approving ? "Запускаю..." : "✓ Запустить все"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Live logs */}
              {(stage === "running" || stage === "done") && logs.map((log, i) => (
                <div key={i} className={`font-mono text-xs ${
                  log.status === "error" ? "text-red-400" :
                  log.status === "success" ? "text-green-400" :
                  log.status === "rollback" ? "text-yellow-400" :
                  "text-gray-300"
                }`}>
                  {STATUS_ICON[log.status] || "  "} {log.message}
                </div>
              ))}

              {stage === "running" && !taskDone && (
                <div className="text-gray-500 text-xs animate-pulse">выполняется...</div>
              )}

              {stage === "done" && (
                <div className={`mt-4 p-3 rounded-lg border ${taskStatus === "done" ? "border-green-700 bg-green-900/20" : "border-red-700 bg-red-900/20"}`}>
                  <div className="font-medium">{taskStatus === "done" ? "✅ Все задачи выполнены" : "✗ Задача завершена с ошибками"}</div>
                  <div className="flex gap-2 mt-3">
                    <button onClick={handleRollback} className="text-sm text-gray-400 border border-gray-700 px-3 py-1 rounded hover:text-white">
                      ↩ Откатить
                    </button>
                    <button onClick={resetAll} className="text-sm text-white bg-accent px-3 py-1 rounded">
                      Новая задача
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Input area (only in input stage) */}
            {stage === "input" && (
              <form onSubmit={handleSubmitTz} className="border-t border-gray-800 p-4 space-y-3">
                {/* Reference */}
                <div className="flex gap-2">
                  <input
                    className="flex-1 rounded-md border border-gray-700 bg-transparent px-3 py-1.5 text-sm"
                    placeholder="🔗 URL референса (опционально)"
                    value={referenceUrl}
                    onChange={(e) => setReferenceUrl(e.target.value)}
                  />
                  <label className="flex items-center gap-1 text-sm text-gray-500 hover:text-white cursor-pointer border border-gray-700 rounded-md px-3 py-1.5">
                    📎 Файл
                    <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileChange} />
                  </label>
                  {attachments.length > 0 && (
                    <span className="text-xs text-gray-500 self-center">{attachments.length} прикреплено</span>
                  )}
                </div>

                {/* TZ textarea */}
                <textarea
                  className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm resize-none h-28"
                  placeholder="Введите задачу или вставьте ТЗ..."
                  value={tz}
                  onChange={(e) => setTz(e.target.value)}
                />

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={sending || !tz.trim()}
                    className="rounded-md bg-accent px-5 py-2 text-sm text-white disabled:opacity-50"
                  >
                    {sending ? "Анализирую..." : "Отправить →"}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {tab === "audit" && (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            🔍 Аудит — в разработке
          </div>
        )}

        {tab === "history" && (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            📋 История задач — в разработке
          </div>
        )}
      </div>
    </div>
  );
}
