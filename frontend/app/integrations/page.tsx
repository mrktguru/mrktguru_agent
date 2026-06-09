"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function IntegrationsPage() {
  const router = useRouter();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { router.replace("/login"); return; }
    api.get("/api/integrations/figma")
      .then(r => setConnected(r.data.connected))
      .catch(() => router.replace("/login"));
  }, [router]);

  async function save() {
    if (!token.trim()) return;
    setSaving(true);
    setMsg(null);
    try {
      await api.post("/api/integrations/figma", { token: token.trim() });
      setConnected(true);
      setToken("");
      setMsg({ type: "ok", text: "Figma подключена" });
    } catch {
      setMsg({ type: "err", text: "Не удалось сохранить токен. Проверьте что токен корректный." });
    } finally {
      setSaving(false);
    }
  }

  async function disconnect() {
    setDeleting(true);
    setMsg(null);
    try {
      await api.delete("/api/integrations/figma");
      setConnected(false);
      setMsg({ type: "ok", text: "Figma отключена" });
    } catch {
      setMsg({ type: "err", text: "Ошибка при отключении" });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="min-h-screen bg-surface-2 px-4 py-8">
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <a href="/dashboard" className="text-text-muted hover:text-text-main transition-colors text-sm">
            ← Назад
          </a>
        </div>

        <h1 className="text-2xl font-semibold text-text-main mb-1">Интеграции</h1>
        <p className="text-sm text-text-muted mb-6">Подключите сервисы для расширенных возможностей агента.</p>

        {/* Figma card */}
        <div className="bg-surface rounded-2xl border border-border p-6 shadow-card">
          <div className="flex items-start gap-4">
            {/* Figma logo */}
            <div className="w-10 h-10 rounded-xl bg-[#1E1E1E] flex items-center justify-center flex-shrink-0">
              <svg width="20" height="20" viewBox="0 0 38 57" fill="none">
                <path d="M19 28.5C19 22.425 23.925 17.5 30 17.5C36.075 17.5 41 22.425 41 28.5C41 34.575 36.075 39.5 30 39.5C23.925 39.5 19 34.575 19 28.5Z" fill="#1ABCFE"/>
                <path d="M0 46.5C0 40.425 4.925 35.5 11 35.5H19V46.5C19 52.575 14.075 57.5 8 57.5C1.925 57.5 0 52.575 0 46.5Z" fill="#0ACF83"/>
                <path d="M19 0.5V17.5H30C36.075 17.5 41 12.575 41 6.5C41 0.425 36.075 -4.5 30 -4.5H19V0.5Z" fill="#FF7262"/>
                <path d="M0 6.5C0 12.575 4.925 17.5 11 17.5H19V-4.5H8C1.925 -4.5 0 0.425 0 6.5Z" fill="#F24E1E"/>
                <path d="M0 28.5C0 34.575 4.925 39.5 11 39.5H19V17.5H11C4.925 17.5 0 22.425 0 28.5Z" fill="#FF7262"/>
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="font-semibold text-text-main">Figma</span>
                {connected === true && (
                  <span className="text-xs bg-green-50 text-green-600 border border-green-100 rounded-full px-2 py-0.5">
                    Подключена
                  </span>
                )}
                {connected === false && (
                  <span className="text-xs bg-surface-3 text-text-muted border border-border rounded-full px-2 py-0.5">
                    Не подключена
                  </span>
                )}
              </div>
              <p className="text-sm text-text-muted">
                Вёрстка сайта по Figma-макету. Агент анализирует дизайн и генерирует HTML/CSS.
              </p>
            </div>
          </div>

          {/* Status message */}
          {msg && (
            <div className={`mt-4 text-sm rounded-xl px-3 py-2 border ${
              msg.type === "ok"
                ? "bg-green-50 text-green-700 border-green-100"
                : "bg-red-50 text-red-600 border-red-100"
            }`}>
              {msg.text}
            </div>
          )}

          {/* Connected state */}
          {connected === true && (
            <div className="mt-5 pt-4 border-t border-border flex items-center justify-between gap-3">
              <p className="text-sm text-text-muted">
                Токен сохранён. Просто вставьте ссылку на Figma в задаче — агент всё сделает сам.
              </p>
              <button
                onClick={disconnect}
                disabled={deleting}
                className="flex-shrink-0 text-sm text-red-500 hover:text-red-600 border border-red-200 hover:border-red-300 rounded-xl px-3 py-1.5 transition-colors disabled:opacity-50"
              >
                {deleting ? "Отключаю…" : "Отключить"}
              </button>
            </div>
          )}

          {/* Disconnected state */}
          {connected === false && (
            <div className="mt-5 pt-4 border-t border-border space-y-3">
              <div>
                <label className="block text-xs font-medium text-text-sub mb-1.5">
                  Personal Access Token
                </label>
                <input
                  type="password"
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && save()}
                  placeholder="figd_…"
                  className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors font-mono"
                />
              </div>

              <button
                onClick={() => setShowGuide(v => !v)}
                className="text-xs text-accent hover:underline"
              >
                {showGuide ? "Скрыть инструкцию" : "Как получить токен?"}
              </button>

              {showGuide && (
                <div className="bg-surface-2 rounded-xl border border-border p-4 text-sm text-text-sub space-y-1.5">
                  <p className="font-medium text-text-main">Получить токен Figma:</p>
                  <ol className="list-decimal list-inside space-y-1 text-text-muted">
                    <li>Откройте <a href="https://www.figma.com" target="_blank" rel="noreferrer" className="text-accent hover:underline">figma.com</a> и войдите в аккаунт</li>
                    <li>Нажмите на иконку профиля → <strong>Settings</strong></li>
                    <li>Прокрутите до раздела <strong>Security</strong></li>
                    <li>Нажмите <strong>Generate new token</strong></li>
                    <li>Скопируйте токен (начинается с <code className="bg-surface-3 px-1 rounded">figd_</code>) и вставьте выше</li>
                  </ol>
                  <p className="text-text-muted text-xs pt-1">
                    Токен хранится зашифрованно и используется только для чтения ваших файлов.
                  </p>
                </div>
              )}

              <button
                onClick={save}
                disabled={saving || !token.trim()}
                className="w-full rounded-xl bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors disabled:opacity-50"
              >
                {saving ? "Сохраняю…" : "Подключить Figma"}
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
