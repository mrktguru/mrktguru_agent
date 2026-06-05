"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { MindMap } from "@/components/viz/MindMap";
import { FeatureBoard } from "@/components/viz/FeatureBoard";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { ArchDiagram } from "@/components/viz/ArchDiagram";
import { UIMockup } from "@/components/viz/UIMockup";

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

  const [sideTab, setSideTab] = useState<"chat" | "arch" | "flow" | "mvp" | "deploy">("chat");

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
        setSideTab("chat");
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

  // ---- Shared chat panel (used in both layouts) ----
  function ChatPanel({ fullHeight }: { fullHeight?: boolean }) {
    return (
      <div className={`flex flex-col ${fullHeight ? "h-full" : "h-[calc(100vh-8rem)]"} rounded-xl border border-gray-800`}>
        <header className="flex items-center justify-between border-b border-gray-800 px-4 py-3 text-sm text-gray-400 shrink-0">
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
                    ? "ml-6 md:ml-12 rounded-lg bg-indigo-500/10 p-3"
                    : "mr-6 md:mr-12 rounded-lg bg-gray-800/40 p-3"
                }
              >
                <div className="text-xs text-gray-500">{m.role === "user" ? "Вы" : "Агент"}</div>
                <div className="mt-1 whitespace-pre-wrap text-sm">{m.content}</div>
              </div>
            ))}
          {loading && <div className="text-sm text-gray-500">Агент печатает…</div>}
          <div ref={endRef} />
        </div>
        <form onSubmit={send} className="flex gap-2 border-t border-gray-800 p-3 shrink-0">
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
      </div>
    );
  }

  // ---- Phase 4: full-screen left-nav layout ----
  if (phase >= 4) {
    const NAV_TABS = [
      { id: "chat" as const, icon: "💬", label: "Чат" },
      { id: "arch" as const, icon: "🏗️", label: "Арх." },
      { id: "flow" as const, icon: "🔀", label: "Флоу" },
      { id: "mvp" as const, icon: "📱", label: "MVP" },
      { id: "deploy" as const, icon: "🚀", label: "Деплой" },
    ] as const;

    return (
      <div className="flex h-screen overflow-hidden" style={{ background: "#080a12" }}>
        {/* Left vertical nav */}
        <nav
          className="flex flex-col items-center gap-1 py-4 shrink-0"
          style={{ width: 72, background: "#0d0f17", borderRight: "1px solid rgba(255,255,255,0.07)" }}
        >
          {NAV_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSideTab(tab.id)}
              className="flex flex-col items-center gap-1 w-full py-3 px-1 rounded-lg mx-1 transition-all"
              style={{
                background: sideTab === tab.id ? "rgba(99,102,241,0.18)" : "transparent",
                color: sideTab === tab.id ? "#a5b4fc" : "#6b7280",
              }}
            >
              <span className="text-lg leading-none">{tab.icon}</span>
              <span className="text-[9px] font-medium leading-none">{tab.label}</span>
            </button>
          ))}
        </nav>

        {/* Content area */}
        <div className="flex-1 overflow-hidden">
          {sideTab === "chat" && (
            <div className="h-full p-4">
              <ChatPanel fullHeight />
            </div>
          )}

          {sideTab === "arch" && (
            <div className="h-full p-6 overflow-y-auto">
              <div className="mb-4 text-sm font-semibold text-gray-300">Архитектура</div>
              <ArchDiagram spec={spec} />
            </div>
          )}

          {sideTab === "flow" && (
            <div className="h-full p-6 overflow-y-auto space-y-4">
              <div className="mb-4 text-sm font-semibold text-gray-300">Флоу</div>
              <FlowDiagram spec={spec} flow="user_flow" title="Пользовательский флоу" />
              <FlowDiagram spec={spec} flow="admin_flow" title="Админ-флоу" />
            </div>
          )}

          {sideTab === "mvp" && (
            <div className="h-full p-6 flex flex-col">
              <UIMockup
                spec={spec}
                projectId={projectId}
                onDeploy={() => {
                  startDeploy();
                  setSideTab("deploy");
                }}
              />
            </div>
          )}

          {sideTab === "deploy" && (
            <div className="h-full p-6 flex flex-col gap-4">
              <div className="text-sm font-semibold text-gray-300 shrink-0">Деплой</div>
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
              <div
                className="flex-1 rounded-xl p-4 space-y-1 overflow-auto text-xs"
                style={{ background: "#0d0f17", border: "1px solid rgba(255,255,255,0.07)" }}
              >
                {logs.length === 0 && <div className="text-gray-500">— Ожидание деплоя… —</div>}
                {logs.map((l, i) => (
                  <div key={l.id ?? i} className="flex gap-2">
                    <span className="w-4 shrink-0">{STATUS_ICON[l.status] ?? "•"}</span>
                    <span className="w-24 shrink-0 text-gray-500">{l.step}</span>
                    <span
                      className={
                        l.status === "error"
                          ? "text-red-400"
                          : l.status === "success"
                          ? "text-emerald-400"
                          : "text-gray-300"
                      }
                    >
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
    );
  }

  // ---- Phases 1-3: classic two-column layout ----
  return (
    <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 md:px-6 py-8 lg:grid-cols-[1fr_360px]">
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
                    ? "ml-6 md:ml-12 rounded-lg bg-indigo-500/10 p-3"
                    : "mr-6 md:mr-12 rounded-lg bg-gray-800/40 p-3"
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

        {/* JSON spec */}
        <div className="rounded-xl border border-gray-800 p-4">
          <div className="text-sm text-gray-400">Спецификация (JSON)</div>
          <pre className="mt-3 max-h-60 overflow-auto text-xs text-gray-300">
{spec ? JSON.stringify(spec, null, 2) : "—"}
          </pre>
        </div>

        {/* Deploy logs */}
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
      </aside>
    </main>
  );
}
