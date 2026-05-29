"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type ScanResult = {
  cms: string | null;
  cms_version: string | null;
  php_version: string | null;
  web_server: string | null;
  server_os: string | null;
  site_root_path: string | null;
};

export default function ConnectSitePage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "", url: "", ssh_host: "", ssh_port: "22", ssh_user: "root",
    auth_type: "password" as "password" | "platform_key",
    password: "", private_key: "",
  });
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [siteId, setSiteId] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post<{ id: string }>("/api/sites", {
        name: form.name, url: form.url || undefined,
        ssh_host: form.ssh_host, ssh_port: parseInt(form.ssh_port) || 22,
        ssh_user: form.ssh_user, auth_type: form.auth_type,
        password: form.auth_type === "password" ? form.password : undefined,
        private_key: form.auth_type === "platform_key" ? form.private_key : undefined,
      });
      setSiteId(data.id);
      setLoading(false);
      setScanning(true);
      const { data: scan } = await api.post<ScanResult>(`/api/sites/${data.id}/scan`);
      setScanResult(scan);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Ошибка подключения");
    } finally {
      setLoading(false);
      setScanning(false);
    }
  }

  const INFO_ROWS = scanResult ? [
    { label: "CMS", value: [scanResult.cms, scanResult.cms_version].filter(Boolean).join(" ") },
    { label: "PHP", value: scanResult.php_version },
    { label: "Web-сервер", value: scanResult.web_server },
    { label: "ОС", value: scanResult.server_os },
    { label: "Корень сайта", value: scanResult.site_root_path, mono: true },
  ].filter((r) => r.value) : [];

  if (scanResult && siteId) {
    return (
      <main className="min-h-screen flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8L6.5 11.5L13 5" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div>
                <p className="font-semibold text-text-main">Сайт подключён</p>
                <p className="text-xs text-text-muted">CMS определена</p>
              </div>
            </div>

            <div className="bg-surface-2 rounded-xl border border-border divide-y divide-border overflow-hidden mb-5">
              {INFO_ROWS.map((r) => (
                <div key={r.label} className="flex items-center justify-between px-3.5 py-2.5">
                  <span className="text-xs text-text-sub">{r.label}</span>
                  <span className={`text-xs font-medium text-text-main ${r.mono ? "font-mono" : ""}`}>{r.value}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => router.push(`/site/${siteId}`)}
              className="w-full bg-accent hover:bg-accent-hover text-white rounded-xl py-2.5 text-sm font-medium transition-colors"
            >
              Перейти к сайту →
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <button onClick={() => router.push("/dashboard")} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-main mb-6 transition-colors">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 11L5 7L9 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Назад
        </button>

        <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
          <h1 className="text-xl font-semibold text-text-main mb-5">Подключить сайт</h1>

          <form onSubmit={handleConnect} className="space-y-4">
            {/* Site info */}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-text-sub mb-1.5">Название *</label>
                <input className="input" placeholder="Мой интернет-магазин" value={form.name} onChange={(e) => set("name", e.target.value)} required />
              </div>
              <div>
                <label className="block text-xs font-medium text-text-sub mb-1.5">URL сайта</label>
                <input className="input" placeholder="https://example.ru" value={form.url} onChange={(e) => set("url", e.target.value)} />
              </div>
            </div>

            {/* SSH */}
            <div className="border-t border-border pt-4 space-y-3">
              <p className="text-xs font-medium text-text-sub">SSH доступ</p>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs text-text-muted mb-1">Хост</label>
                  <input className="input" placeholder="185.100.50.1" value={form.ssh_host} onChange={(e) => set("ssh_host", e.target.value)} required />
                </div>
                <div className="w-20">
                  <label className="block text-xs text-text-muted mb-1">Порт</label>
                  <input className="input" value={form.ssh_port} onChange={(e) => set("ssh_port", e.target.value)} />
                </div>
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1">Логин</label>
                <input className="input" value={form.ssh_user} onChange={(e) => set("ssh_user", e.target.value)} />
              </div>
            </div>

            {/* Auth */}
            <div className="space-y-2">
              <div className="flex gap-3 text-sm">
                {(["password", "platform_key"] as const).map((t) => (
                  <label key={t} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={form.auth_type === t} onChange={() => set("auth_type", t)} className="accent-accent" />
                    <span className="text-text-sub text-xs">{t === "password" ? "Пароль" : "SSH-ключ"}</span>
                  </label>
                ))}
              </div>
              {form.auth_type === "password" ? (
                <input type="password" className="input" placeholder="Пароль SSH" value={form.password} onChange={(e) => set("password", e.target.value)} />
              ) : (
                <textarea className="input font-mono h-24 resize-none text-xs" placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"} value={form.private_key} onChange={(e) => set("private_key", e.target.value)} />
              )}
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/><path d="M7 4.5V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading || scanning} className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl py-2.5 text-sm font-medium transition-colors">
              {loading ? "Подключаю..." : scanning ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin" width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.5" stroke="white" strokeWidth="1.5" strokeDasharray="20 14"/></svg>
                  Сканирую CMS...
                </span>
              ) : "Подключить и сканировать"}
            </button>
          </form>
        </div>
      </div>

      <style jsx global>{`
        .input {
          width: 100%;
          border-radius: 12px;
          border: 1px solid #e8eaed;
          background: #f5f6f8;
          padding: 10px 14px;
          font-size: 13px;
          color: #111827;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .input::placeholder { color: #9ca3af; }
        .input:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
          background: #fff;
        }
      `}</style>
    </main>
  );
}
