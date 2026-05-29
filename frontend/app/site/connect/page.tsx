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
    name: "",
    url: "",
    ssh_host: "",
    ssh_port: "22",
    ssh_user: "root",
    auth_type: "password" as "password" | "platform_key",
    password: "",
    private_key: "",
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
        name: form.name,
        url: form.url || undefined,
        ssh_host: form.ssh_host,
        ssh_port: parseInt(form.ssh_port) || 22,
        ssh_user: form.ssh_user,
        auth_type: form.auth_type,
        password: form.auth_type === "password" ? form.password : undefined,
        private_key: form.auth_type === "platform_key" ? form.private_key : undefined,
      });
      setSiteId(data.id);
      // Auto-scan after creation
      setScanning(true);
      const { data: scan } = await api.post<ScanResult>(`/api/sites/${data.id}/scan`);
      setScanResult(scan);
      setScanning(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Ошибка подключения");
    } finally {
      setLoading(false);
      setScanning(false);
    }
  }

  if (scanResult && siteId) {
    return (
      <main className="mx-auto max-w-lg px-6 py-12">
        <h1 className="text-2xl font-semibold mb-6">✅ Сайт подключён</h1>
        <div className="rounded-lg border border-gray-700 p-4 space-y-2 text-sm">
          {scanResult.cms && (
            <div className="flex justify-between">
              <span className="text-gray-400">CMS</span>
              <span>{scanResult.cms} {scanResult.cms_version || ""}</span>
            </div>
          )}
          {scanResult.php_version && (
            <div className="flex justify-between">
              <span className="text-gray-400">PHP</span>
              <span>{scanResult.php_version}</span>
            </div>
          )}
          {scanResult.web_server && (
            <div className="flex justify-between">
              <span className="text-gray-400">Web-сервер</span>
              <span>{scanResult.web_server}</span>
            </div>
          )}
          {scanResult.server_os && (
            <div className="flex justify-between">
              <span className="text-gray-400">ОС</span>
              <span>{scanResult.server_os}</span>
            </div>
          )}
          {scanResult.site_root_path && (
            <div className="flex justify-between">
              <span className="text-gray-400">Корневая папка</span>
              <span className="font-mono text-xs">{scanResult.site_root_path}</span>
            </div>
          )}
        </div>
        <button
          onClick={() => router.push(`/site/${siteId}`)}
          className="mt-6 w-full rounded-md bg-accent py-2 text-white font-medium"
        >
          Открыть сайт →
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <button
        className="text-sm text-gray-500 hover:text-white mb-6"
        onClick={() => router.push("/dashboard")}
      >
        ← Назад
      </button>
      <h1 className="text-2xl font-semibold mb-6">Подключить сайт</h1>

      <form onSubmit={handleConnect} className="space-y-4">
        {/* Site info */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Название сайта *</label>
          <input
            className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
            placeholder="Мой интернет-магазин"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">URL сайта</label>
          <input
            className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
            placeholder="https://example.ru"
            value={form.url}
            onChange={(e) => set("url", e.target.value)}
          />
        </div>

        {/* SSH */}
        <div className="border-t border-gray-800 pt-4">
          <div className="text-sm text-gray-400 mb-3">SSH доступ</div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">Хост</label>
              <input
                className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
                placeholder="185.100.50.1"
                value={form.ssh_host}
                onChange={(e) => set("ssh_host", e.target.value)}
                required
              />
            </div>
            <div className="w-20">
              <label className="block text-xs text-gray-500 mb-1">Порт</label>
              <input
                className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
                value={form.ssh_port}
                onChange={(e) => set("ssh_port", e.target.value)}
              />
            </div>
          </div>
          <div className="mt-2">
            <label className="block text-xs text-gray-500 mb-1">Логин</label>
            <input
              className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
              value={form.ssh_user}
              onChange={(e) => set("ssh_user", e.target.value)}
            />
          </div>
        </div>

        {/* Auth type */}
        <div>
          <div className="flex gap-4 text-sm mb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={form.auth_type === "password"}
                onChange={() => set("auth_type", "password")}
              />
              Пароль
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={form.auth_type === "platform_key"}
                onChange={() => set("auth_type", "platform_key")}
              />
              SSH-ключ
            </label>
          </div>
          {form.auth_type === "password" ? (
            <input
              type="password"
              className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm"
              placeholder="Пароль SSH"
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
            />
          ) : (
            <textarea
              className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2 text-sm font-mono h-28"
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----"
              value={form.private_key}
              onChange={(e) => set("private_key", e.target.value)}
            />
          )}
        </div>

        {error && <div className="text-red-400 text-sm">{error}</div>}

        <button
          type="submit"
          disabled={loading || scanning}
          className="w-full rounded-md bg-accent py-2 text-white font-medium disabled:opacity-50"
        >
          {loading ? "Подключаю..." : scanning ? "Сканирую CMS..." : "Подключить и сканировать"}
        </button>
      </form>
    </main>
  );
}
