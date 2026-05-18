"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string };

const PHASE_LABELS: Record<number, string> = {
  1: "1. Идея",
  2: "2. Продукт",
  3: "3. Workflow",
  4: "4. Деплой",
};

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState(1);
  const [spec, setSpec] = useState<any>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function load() {
    const { data } = await api.get(`/api/agent/${projectId}/history`);
    setMessages(data.messages || []);
    setPhase(data.phase);
    setSpec(data.spec);
  }

  useEffect(() => {
    load();
  }, [projectId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
      setPhase(data.phase);
      setSpec(data.spec);
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

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 py-8 lg:grid-cols-[1fr_320px]">
      <section className="flex h-[calc(100vh-8rem)] flex-col rounded-xl border border-gray-800">
        <header className="border-b border-gray-800 px-4 py-3 text-sm text-gray-400">
          Фаза: <span className="text-white">{PHASE_LABELS[phase] ?? phase}</span>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-gray-500">
              Напишите первое сообщение — расскажите идею проекта в свободной форме.
            </div>
          )}
          {messages.map((m, i) => (
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

      <aside className="rounded-xl border border-gray-800 p-4">
        <div className="text-sm text-gray-400">Текущая спецификация</div>
        <pre className="mt-3 max-h-[calc(100vh-12rem)] overflow-auto text-xs text-gray-300">
{spec ? JSON.stringify(spec, null, 2) : "—"}
        </pre>
      </aside>
    </main>
  );
}
