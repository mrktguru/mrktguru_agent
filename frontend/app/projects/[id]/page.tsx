"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { MindMap } from "@/components/viz/MindMap";
import { FeatureBoard } from "@/components/viz/FeatureBoard";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { ArchDiagram } from "@/components/viz/ArchDiagram";

type Message = { role: "user" | "assistant"; content: string };

type DeployLog = {
  id?: string;
  step: string;
  status: "running" | "success" | "error" | "fixed" | string;
  message: string;
  timestamp?: string;
};

const PHASE_LABELS: Record<number, string> = {
  1: "1. Идея",
  2: "2. Продукт",
  3: "3. Workflow",
  4: "4. Деплой",
};

const STATUS_ICON: Record<string, string> = {
  running: "🔄",
  success: "✓",
  error: "✗",
  fixed: "⚠",
};

function wsUrl(path: string): string {
  if (typeof window === "undefined") return "";
  const base = process.env.NEXT_PUBLIC_WS_URL || `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
  return `${base}${path}`;
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState(1);
  const [spec, setSpec] = useState<any>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<DeployLog[]>([]);
  const [deployState, setDeployState] = useState<"idle" | "running" | "deployed" | "error">("idle");
  const endRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [sideTab, setSideTab] = useState<"arch" | "flow" | "mvp" | "deploy">("arch");

  async function load() {
    const { data } = await api.get(`/api/agent/${projectId}/history`);
    setMessages(data.messages || []);
    setPhase(data.phase);
    setSpec(data.spec);
  }

  async function loadLogs() {
    try {
      const { data } = await api.get<DeployLog[]>(`/api/projects/${projectId}/deploy/logs`);
      setLogs(data);
    } catch {
      // no logs yet — ignore
    }
  }

  useEffect(() => {
    load();
    loadLogs();
  }, [projectId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const userMsg: Message = { role: "user", content: input };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const { data } = await api.post(`/api/agent/${projectId}/chat`, {
        message: userMsg.content,
      });
      // Never render raw JSON code blocks that leaked from code generation
      const safeReply = /^```json/i.test((data.reply ?? "").trim()) ? null : data.reply;
      if (safeReply) {
        setMessages((m) => [...m, { role: "assistant", content: safeReply }]);
      }
      const prevPhase = phase;
      setPhase(data.phase);
      setSpec(data.spec);
      // Auto-open deploy stream when entering phase 4
      if (data.phase === 4 && prevPhase < 4) {
        setSideTab("arch");
        setTimeout(connectDeployStream, 1500);
      }
      if (data.phase_complete && data.phase > 4) {
        setSideTab("deploy");
        connectDeployStream();
      }
    } catch (err: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Ошибка: ${err?.response?.data?.detail ?? err.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function connectDeployStream() {
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
    }
    const token = typeof window !== "undefined" ? window.localStorage.getItem("token") : null;
    if (!token) return;
    const ws = new WebSocket(`${wsUrl(`/ws/deploy/${projectId}`)}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === "log") {
          setLogs((prev) => {
            const next = prev.filter((p) => p.id !== data.id);
            next.push({ id: data.id, step: data.step, status: data.status, message: data.message, timestamp: data.timestamp });
            return next;
          });
        } else if (data.type === "deploy_complete") {
          setDeployState(data.status === "deployed" ? "deployed" : "error");
        } else if (data.type === "error") {
          setDeployState("error");
        }
      } catch {}
    };
    ws.onclose = () => {
      wsRef.current = null;
    };
  }

  async function startDeploy() {
    setLogs([]);
    setDeployState("running");
    setSideTab("deploy");
    try {
      await api.post(`/api/projects/${projectId}/deploy`, {});
      connectDeployStream();
    } catch (err: any) {
      setDeployState("error");
      setLogs([{ step: "init", status: "error", message: err?.response?.data?.detail ?? err.message }]);
    }
  }

  useEffect(() => {
    return () => {
      try { wsRef.current?.close(); } catch {}
    };
  }, []);

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 py-8 lg:grid-cols-[1fr_360px]">
      <section className="flex h-[calc(100vh-8rem)] flex-col rounded-xl border border-gray-800">
        <header className="flex items-center justify-between border-b border-gray-800 px-4 py-3 text-sm text-gray-400">
          <div>
            Фаза: <span className="text-white">{PHASE_LABELS[phase] ?? phase}</span>
          </div>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-gray-500">
              Напишите первое сообщение — расскажите идею проекта в свободной форме.
            </div>
          )}
          {messages
            .filter((m) => !/^```json/i.test((m.content ?? "").trim()))
            .map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-12 rounded-lg bg-indigo-500/10 p-3"
                    : "mr-12 rounded-lg bg-gray-800/40 p-3"
                }
              >
                <div className="text-xs text-gray-500">{m.role === "user" ? "Вы" : "Агент"}</div>
                <div className="mt-1 whitespace-pre-wrap text-sm">{m.content}</div>
              </div>
            ))}
          {loading && <div className="text-sm text-gray-500">Агент печатает…</div>}
          <div ref={endRef} />
        </div>
        <form onSubmit={send} className="flex gap-2 border-t border-gray-800 p-3">
          <input
            className="flex-1 rounded-md border border-gray-700 bg-transparent px-3 py-2"
            placeholder="сообщение…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            className="rounded-md bg-accent px-4 py-2 text-white disabled:opacity-50"
            disabled={loading}
          >
            Отправить
          </button>
        </form>
      </section>

      <aside className="flex flex-col gap-4">
        {phase <= 1 && <MindMap spec={spec} />}
        {phase === 2 && (
          <FeatureBoard spec={spec} projectId={projectId} onSpecChanged={setSpec} />
        )}
        {phase === 3 && (
          <>
            <FlowDiagram spec={spec} flow="user_flow" title="Пользовательский флоу" />
            <FlowDiagram spec={spec} flow="admin_flow" title="Админ-флоу" />
            <ArchDiagram spec={spec} />
          </>
        )}
        {phase >= 4 && (
          <div className="flex flex-col rounded-xl border border-gray-800 overflow-hidden" style={{ height: "calc(100vh - 8rem)" }}>
            {/* Tab bar */}
            <div className="flex shrink-0 border-b border-gray-800 text-xs">
              {(["arch", "flow", "mvp", "deploy"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setSideTab(tab)}
                  className={`flex-1 py-2.5 font-medium transition-colors ${
                    sideTab === tab
                      ? "border-b-2 border-indigo-500 text-white"
                      : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {tab === "arch" ? "Архитектура" : tab === "flow" ? "Флоу" : tab === "mvp" ? "MVP" : "Деплой"}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto">
              {sideTab === "arch" && (
                <div className="p-3 space-y-3">
                  <ArchDiagram spec={spec} />
                </div>
              )}
              {sideTab === "flow" && (
                <div className="p-3 space-y-3">
                  <FlowDiagram spec={spec} flow="user_flow" title="Пользовательский флоу" />
                  <FlowDiagram spec={spec} flow="admin_flow" title="Админ-флоу" />
                </div>
              )}
              {sideTab === "mvp" && (
                <div className="p-4 space-y-4">
                  {/* Stack summary */}
                  {spec?.workflow?.stack && (
                    <div>
                      <div className="text-xs font-medium text-gray-400 mb-2">Стек</div>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.values(spec.workflow.stack as Record<string, string>)
                          .filter(Boolean)
                          .map((v, i) => (
                            <span key={i} className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs text-indigo-300">
                              {String(v)}
                            </span>
                          ))}
                      </div>
                    </div>
                  )}
                  {/* MVP features */}
                  {(spec?.product?.features?.mvp ?? []).length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-400 mb-2">MVP-фичи</div>
                      <ul className="space-y-1.5">
                        {(spec.product.features.mvp as any[]).map((f: any, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-xs">
                            <span className="mt-0.5 text-emerald-400">✓</span>
                            <span className="text-gray-200">{typeof f === "string" ? f : f.title}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {/* Assumptions */}
                  {(spec?.assumptions ?? []).length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-gray-400 mb-2">Допущения</div>
                      <ul className="space-y-1 text-xs text-gray-400">
                        {(spec.assumptions as string[]).map((a, i) => (
                          <li key={i}>• {a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {sideTab === "deploy" && (
                <div className="flex flex-col h-full p-4 gap-3">
                  <button
                    onClick={startDeploy}
                    disabled={deployState === "running"}
                    className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
                  >
                    {deployState === "running" ? "⏳ Деплоится…" : deployState === "deployed" ? "✅ Задеплоено — передеплоить" : "🚀 Задеплоить"}
                  </button>
                  {deployState === "deployed" && spec?.domain && (
                    <a
                      href={`https://${spec.domain}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full rounded-lg border border-emerald-600 px-4 py-2.5 text-center text-sm font-medium text-emerald-400 hover:bg-emerald-600/10 transition-colors"
                    >
                      Открыть сайт →
                    </a>
                  )}
                  <div className="flex-1 space-y-1 overflow-auto text-xs mt-1">
                    {logs.length === 0 && <div className="text-gray-500">— нет записей —</div>}
                    {logs.map((l, i) => (
                      <div key={l.id ?? i} className="flex gap-2">
                        <span className="w-4 shrink-0">{STATUS_ICON[l.status] ?? "•"}</span>
                        <span className="w-20 shrink-0 text-gray-500">{l.step}</span>
                        <span className={l.status === "error" ? "text-red-400" : l.status === "success" ? "text-emerald-400" : "text-gray-300"}>
                          {l.message}
                        </span>
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* JSON spec — only visible on phases 1-3 */}
        {phase < 4 && (
          <div className="rounded-xl border border-gray-800 p-4">
            <div className="text-sm text-gray-400">Спецификация (JSON)</div>
            <pre className="mt-3 max-h-60 overflow-auto text-xs text-gray-300">
{spec ? JSON.stringify(spec, null, 2) : "—"}
            </pre>
          </div>
        )}

        {/* Deploy logs — only visible on phases 1-3 (in phase 4 they're in the tab) */}
        {phase < 4 && (
          <div className="flex-1 rounded-xl border border-gray-800 p-4">
            <div className="text-sm text-gray-400">Лог деплоя</div>
            <div className="mt-3 max-h-[calc(100vh-22rem)] space-y-1 overflow-auto text-xs">
              {logs.length === 0 && <div className="text-gray-500">— нет записей —</div>}
              {logs.map((l, i) => (
                <div key={l.id ?? i} className="flex gap-2">
                  <span className="w-4">{STATUS_ICON[l.status] ?? "•"}</span>
                  <span className="w-20 shrink-0 text-gray-500">{l.step}</span>
                  <span className={l.status === "error" ? "text-red-400" : l.status === "success" ? "text-emerald-400" : "text-gray-300"}>
                    {l.message}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}
      </aside>
    </main>
  );
}
