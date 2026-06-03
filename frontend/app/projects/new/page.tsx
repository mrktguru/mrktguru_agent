"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

/* ─── Types ──────────────────────────────────────────────────────────────── */
type AuthType = "password" | "platform_key";

type Server = {
  id: string;
  name: string;
  ip: string;
  ssh_user: string;
  ssh_port: number;
  auth_type: string;
  status: string;
};

type DiscoveredSite = {
  name: string;
  url: string | null;
  root_path: string | null;
  cms: string | null;
  framework: string | null;
  is_docker: boolean;
  docker_compose_dir: string | null;
  docker_container_name: string | null;
  source_path: string | null;
};

type Screen =
  | "name"
  | "server"
  | "discovery"
  | "new_git"
  | "new_describe"
  | "working";

/* ─── Progress bar ───────────────────────────────────────────────────────── */
const STEP_LABELS = ["Проект", "Сервер", "Выбор"];

function screenToStep(s: Screen): number {
  switch (s) {
    case "name":
      return 1;
    case "server":
      return 2;
    case "discovery":
      return 3;
    default:
      return 4;
  }
}

function ProgressBar({ screen }: { screen: Screen }) {
  const step = screenToStep(screen);
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEP_LABELS.map((label, i) => {
        const n = i + 1;
        const done = step > n;
        const active = step === n;
        return (
          <div key={n} className="flex items-center gap-2">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors
              ${done ? "bg-accent text-white" : active ? "bg-accent text-white" : "bg-surface-3 text-text-muted"}`}
            >
              {done ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5L4.5 7.5L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                n
              )}
            </div>
            <span className={`text-xs hidden sm:block ${active ? "text-text-main font-medium" : "text-text-muted"}`}>{label}</span>
            {i < STEP_LABELS.length - 1 && <div className={`h-px w-6 sm:w-12 ${done ? "bg-accent" : "bg-border"}`} />}
          </div>
        );
      })}
    </div>
  );
}

/* ─── SSH Key hint modal ──────────────────────────────────────────────────── */
function SshHint({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface rounded-2xl border border-border shadow-modal max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-text-main">Как создать SSH-ключ</h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-main">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <ol className="space-y-3 text-sm">
          {[
            { title: "Откройте терминал", cmd: null, desc: "macOS/Linux: Terminal. Windows: PowerShell или WSL" },
            { title: "Создайте ключ", cmd: 'ssh-keygen -t ed25519 -C "sitedoc"', desc: "Нажмите Enter три раза (без пароля)" },
            { title: "Скопируйте публичный ключ", cmd: "cat ~/.ssh/id_ed25519.pub", desc: "Добавьте его в ~/.ssh/authorized_keys на сервере" },
            { title: "Скопируйте приватный ключ", cmd: "cat ~/.ssh/id_ed25519", desc: "Вставьте его ниже в поле «SSH-ключ»" },
          ].map((item, i) => (
            <li key={i} className="flex gap-3">
              <span className="w-5 h-5 rounded-full bg-accent/10 text-accent flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">{i + 1}</span>
              <div>
                <p className="font-medium text-text-main">{item.title}</p>
                {item.cmd && <code className="block bg-surface-3 border border-border rounded-lg px-3 py-1.5 text-xs font-mono my-1">{item.cmd}</code>}
                <p className="text-text-muted text-xs">{item.desc}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-4 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700">
          💡 Альтернатива: используйте пароль SSH — проще, но менее безопасно
        </div>
      </div>
    </div>
  );
}

/* ─── Tech-stack badge for discovery cards ────────────────────────────────── */
function StackBadge({ site }: { site: DiscoveredSite }) {
  const label = site.framework || site.cms;
  if (!label) return null;
  return <span className="px-2 py-0.5 rounded-md bg-accent/10 text-accent text-xs font-medium">{label}</span>;
}

/* ─── Log terminal (discovery / working) ──────────────────────────────────── */
function LogTerminal({ lines, loading }: { lines: string[]; loading: boolean }) {
  return (
    <div className="bg-surface-2 border border-border rounded-xl p-4 font-mono text-xs space-y-1.5 min-h-32">
      {lines.map((line, i) => (
        <p key={i} className={line.startsWith("✗") ? "text-red-500" : line.startsWith("✓") ? "text-emerald-600" : "text-text-sub"}>
          {line}
        </p>
      ))}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted">
          <svg className="animate-spin" width="11" height="11" viewBox="0 0 11 11" fill="none">
            <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" strokeDasharray="14 10" />
          </svg>
          <span>работаю...</span>
        </div>
      )}
    </div>
  );
}

/* ─── Main component ──────────────────────────────────────────────────────── */
export default function NewProjectPage() {
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>("name");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSshHint, setShowSshHint] = useState(false);

  // Step 1
  const [projectName, setProjectName] = useState("");

  // Step 2 — server registry
  const [servers, setServers] = useState<Server[]>([]);
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [addingServer, setAddingServer] = useState(false);
  const [srv, setSrv] = useState({
    name: "",
    ip: "",
    port: "22",
    user: "root",
    authType: "password" as AuthType,
    password: "",
    privateKey: "",
  });

  // Step 3 — discovery
  const [scanLog, setScanLog] = useState<string[]>([]);
  const [discovered, setDiscovered] = useState<DiscoveredSite[]>([]);

  // Step 4 — fork
  const [selectedSite, setSelectedSite] = useState<DiscoveredSite | null>(null);
  const [projectDesc, setProjectDesc] = useState("");

  const setS = (k: keyof typeof srv, v: string) => setSrv((f) => ({ ...f, [k]: v }));

  /* ── Load existing servers when entering step 2 ── */
  useEffect(() => {
    if (screen !== "server") return;
    api
      .get<Server[]>("/api/servers")
      .then(({ data }) => {
        setServers(data);
        if (data.length === 0) setAddingServer(true);
      })
      .catch(() => setAddingServer(true));
  }, [screen]);

  /* ── Step 2 → create server (if adding) then discover ── */
  async function handleServerContinue() {
    setError("");
    let serverId = selectedServerId;

    if (addingServer || !serverId) {
      if (!srv.ip.trim()) {
        setError("Укажите IP или хост сервера");
        return;
      }
      setLoading(true);
      try {
        const { data } = await api.post<Server>("/api/servers", {
          name: srv.name || srv.ip,
          ip: srv.ip,
          ssh_user: srv.user,
          ssh_port: parseInt(srv.port || "22"),
          auth_type: srv.authType,
          password: srv.authType === "password" ? srv.password : undefined,
          private_key: srv.authType === "platform_key" ? srv.privateKey : undefined,
        });
        serverId = data.id;
        setSelectedServerId(data.id);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Не удалось добавить сервер");
        setLoading(false);
        return;
      }
      setLoading(false);
    }

    if (serverId) runDiscovery(serverId);
  }

  /* ── Step 3 — discovery ── */
  async function runDiscovery(serverId: string) {
    setScreen("discovery");
    setLoading(true);
    setError("");
    setDiscovered([]);
    setScanLog(["🔌 Подключаюсь к серверу...", "🔍 Ищу сайты и проекты..."]);
    try {
      const { data } = await api.post<DiscoveredSite[]>(`/api/servers/${serverId}/discover`);
      setDiscovered(data);
      setScanLog((p) => [...p, `✓ Найдено проектов: ${data.length}`]);
      setLoading(false);
      // Nothing found → go straight to "create new"
      if (data.length === 0) {
        setScanLog((p) => [...p, "Готовых проектов не найдено — создадим новый"]);
        setTimeout(() => setScreen("new_git"), 800);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Ошибка обнаружения");
      setScanLog((p) => [...p, `✗ ${err?.response?.data?.detail || "Ошибка обнаружения"}`]);
      setLoading(false);
    }
  }

  /* ── Fork A — connect existing site (scan, then open chat) ── */
  async function pickSite(site: DiscoveredSite) {
    if (!selectedServerId) return;
    setSelectedSite(site);
    setError("");
    setScreen("working");
    setLoading(true);
    setScanLog(["🔧 Подключаю проект..."]);
    try {
      const { data: createdSite } = await api.post<{ id: string }>("/api/sites", {
        name: projectName || site.name,
        url: site.url || undefined,
        server_id: selectedServerId,
        cms: site.cms || undefined,
        framework: site.framework || undefined,
        site_root_path: site.source_path || site.root_path || undefined,
        is_docker: site.is_docker,
        docker_compose_dir: site.docker_compose_dir || undefined,
        docker_container_name: site.docker_container_name || undefined,
      });
      setScanLog((p) => [...p, "✓ Проект подключён", "🔍 Сканирую структуру файлов..."]);
      try {
        await api.post(`/api/sites/${createdSite.id}/scan`);
        setScanLog((p) => [...p, "✓ Структура изучена"]);
      } catch {
        setScanLog((p) => [...p, "⚠ Скан не удался, продолжаем без файловой структуры"]);
      }
      setScanLog((p) => [...p, "✓ Открываю проект..."]);
      await new Promise((r) => setTimeout(r, 500));
      router.push(`/site/${createdSite.id}`);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Ошибка подключения";
      setError(msg);
      setScanLog((p) => [...p, `✗ ${msg}`]);
      setLoading(false);
    }
  }

  /* ── Fork B — create new project ── */
  async function handleCreateProject() {
    setScreen("working");
    setLoading(true);
    setError("");
    setScanLog(["📦 Создаю проект..."]);
    try {
      const { data: project } = await api.post<{ id: string }>("/api/projects", {
        name: projectName,
        server_id: selectedServerId || undefined,
      });
      setScanLog((p) => [...p, "✓ Проект создан", "🤖 Анализирую описание..."]);
      if (projectDesc.trim()) {
        try {
          await api.post(`/api/agent/${project.id}/chat`, { message: projectDesc });
          setScanLog((p) => [...p, "✓ Описание проанализировано"]);
        } catch {
          setScanLog((p) => [...p, "⚠ Анализ продолжим в чате проекта"]);
        }
      }
      setScanLog((p) => [...p, "✓ Открываю проект..."]);
      await new Promise((r) => setTimeout(r, 500));
      router.push(`/projects/${project.id}`);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Ошибка создания проекта";
      setError(msg);
      setScanLog((p) => [...p, `✗ ${msg}`]);
      setLoading(false);
    }
  }

  /* ── Render ── */
  return (
    <main className="min-h-screen bg-surface-2 flex flex-col items-center justify-center px-6 py-12">
      {showSshHint && <SshHint onClose={() => setShowSshHint(false)} />}

      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-xl bg-accent flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="font-semibold text-text-main">SiteDoc</span>
        </div>

        <ProgressBar screen={screen} />

        {/* ── Step 1: Project name ── */}
        {screen === "name" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-text-main mb-1">Как называется ваш проект?</h2>
              <p className="text-sm text-text-muted">Это может быть название сайта или компании</p>
            </div>
            <input
              className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-base text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
              placeholder="Например: Интернет-магазин TechShop"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && projectName.trim() && setScreen("server")}
              autoFocus
            />
            <div className="flex justify-end mt-5">
              <button
                onClick={() => setScreen("server")}
                disabled={!projectName.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                Далее
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: Server access ── */}
        {screen === "server" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-text-main mb-1">Подключите сервер</h2>
              <p className="text-sm text-text-muted">Выберите сервер или добавьте новый — мы найдём на нём ваши проекты</p>
            </div>

            {/* Existing servers */}
            {servers.length > 0 && !addingServer && (
              <div className="space-y-2 mb-4">
                {servers.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedServerId(s.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-colors ${
                      selectedServerId === s.id ? "border-accent bg-accent/5" : "border-border bg-surface-2 hover:border-accent/30"
                    }`}
                  >
                    <span className="text-xl">🖥️</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-main truncate">{s.name}</p>
                      <p className="text-xs text-text-muted">
                        {s.ssh_user}@{s.ip}:{s.ssh_port}
                      </p>
                    </div>
                    {selectedServerId === s.id && (
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-accent">
                        <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                ))}
                <button onClick={() => { setAddingServer(true); setSelectedServerId(null); }} className="text-sm text-accent hover:underline mt-1">
                  + Добавить другой сервер
                </button>
              </div>
            )}

            {/* Add new server form */}
            {addingServer && (
              <div className="space-y-3 mb-4">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setS("authType", "password")}
                    className={`flex items-center gap-2.5 px-3.5 py-3 rounded-xl border text-left transition-colors ${
                      srv.authType === "password" ? "border-accent bg-accent/5 text-text-main" : "border-border bg-surface-2 text-text-sub hover:border-accent/30"
                    }`}
                  >
                    <span className="text-xl leading-none">🔑</span>
                    <div>
                      <p className="text-sm font-medium leading-tight">SSH</p>
                      <p className="text-xs text-text-muted">Пароль</p>
                    </div>
                  </button>
                  <button
                    onClick={() => setS("authType", "platform_key")}
                    className={`flex items-center gap-2.5 px-3.5 py-3 rounded-xl border text-left transition-colors ${
                      srv.authType === "platform_key" ? "border-accent bg-accent/5 text-text-main" : "border-border bg-surface-2 text-text-sub hover:border-accent/30"
                    }`}
                  >
                    <span className="text-xl leading-none">🗝️</span>
                    <div>
                      <p className="text-sm font-medium leading-tight">SSH</p>
                      <p className="text-xs text-text-muted">Ключ</p>
                    </div>
                  </button>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-sub mb-1.5">Название сервера</label>
                  <input className="field" placeholder="Мой VPS" value={srv.name} onChange={(e) => setS("name", e.target.value)} />
                </div>

                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-text-sub mb-1.5">IP / хост</label>
                    <input className="field" placeholder="185.100.50.1 или example.ru" value={srv.ip} onChange={(e) => setS("ip", e.target.value)} />
                  </div>
                  <div className="w-20">
                    <label className="block text-xs font-medium text-text-sub mb-1.5">Порт</label>
                    <input className="field" placeholder="22" value={srv.port} onChange={(e) => setS("port", e.target.value)} />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-sub mb-1.5">Логин</label>
                  <input className="field" value={srv.user} onChange={(e) => setS("user", e.target.value)} />
                </div>

                {srv.authType === "password" ? (
                  <div>
                    <label className="block text-xs font-medium text-text-sub mb-1.5">Пароль</label>
                    <input type="password" className="field" placeholder="••••••••" value={srv.password} onChange={(e) => setS("password", e.target.value)} />
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium text-text-sub">SSH-ключ (приватный)</label>
                      <button onClick={() => setShowSshHint(true)} className="text-xs text-accent hover:underline">
                        Как создать? →
                      </button>
                    </div>
                    <textarea
                      className="field font-mono text-xs h-28 resize-none"
                      placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"}
                      value={srv.privateKey}
                      onChange={(e) => setS("privateKey", e.target.value)}
                    />
                  </div>
                )}

                <details>
                  <summary className="text-xs text-text-muted cursor-pointer hover:text-text-sub select-none">Где найти данные для подключения?</summary>
                  <div className="mt-2 p-3 bg-surface-3 rounded-xl text-xs text-text-sub space-y-1.5">
                    <p>• <strong>Timeweb / SpaceWeb / Beget</strong>: панель управления → SSH/SFTP → данные доступа</p>
                    <p>• <strong>VPS/VDS</strong>: в письме от провайдера при заказе сервера</p>
                    <p>• <strong>ISPmanager</strong>: Главное меню → Пользователи → SSH</p>
                  </div>
                </details>

                <details>
                  <summary className="text-xs text-text-muted cursor-pointer hover:text-text-sub select-none mt-1">Нет SSH-доступа? Как включить</summary>
                  <div className="mt-2 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-800 space-y-1.5">
                    <p className="font-medium mb-1">SSH доступен у большинства хостингов — обычно просто не включён по умолчанию:</p>
                    <p>• <strong>Timeweb</strong>: Хостинг → SSH/SFTP → «Разрешить SSH» (1 клик)</p>
                    <p>• <strong>Beget</strong>: Настройки аккаунта → SSH → «Активировать»</p>
                    <p>• <strong>SpaceWeb</strong>: Панель → Настройки → SSH Доступ → Включить</p>
                    <p>• <strong>Reg.ru</strong>: Конфигуратор хостинга → SSH → Подключить</p>
                    <p>• <strong>ISPmanager</strong>: Пользователи → [ваш логин] → SSH → поставить галочку</p>
                    <p>• <strong>Другой хостинг</strong>: найдите раздел «SSH», «Терминал» или «Shell» в панели управления</p>
                  </div>
                </details>
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-3">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M7 4.5V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                {error}
              </div>
            )}

            <div className="flex justify-between">
              <button onClick={() => setScreen("name")} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                Назад
              </button>
              <button
                onClick={handleServerContinue}
                disabled={loading || (!selectedServerId && !srv.ip.trim())}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                {loading ? "Подключаю..." : "Найти проекты"}
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Discovery ── */}
        {screen === "discovery" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-5">
              <h2 className="text-xl font-semibold text-text-main mb-1">{loading ? "Ищу проекты на сервере..." : "Что нашлось на сервере"}</h2>
              {!loading && discovered.length > 0 && <p className="text-sm text-text-muted">Выберите проект для доработки или создайте новый</p>}
            </div>

            <LogTerminal lines={scanLog} loading={loading} />

            {!loading && (
              <div className="mt-4 space-y-2">
                {discovered.map((site, i) => (
                  <button
                    key={i}
                    onClick={() => pickSite(site)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-surface-2 hover:border-accent/40 hover:bg-accent/5 text-left transition-colors"
                  >
                    <span className="text-xl">{site.is_docker ? "🐳" : "🌐"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-text-main truncate">{site.name}</p>
                        <StackBadge site={site} />
                      </div>
                      {site.root_path && <p className="text-xs text-text-muted truncate font-mono">{site.root_path}</p>}
                    </div>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-text-muted flex-shrink-0">
                      <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                ))}

                {/* Create new project */}
                <button
                  onClick={() => setScreen("new_git")}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-dashed border-accent/40 bg-accent/5 hover:bg-accent/10 text-left transition-colors"
                >
                  <span className="text-xl">✨</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-accent">Создать новый проект</p>
                    <p className="text-xs text-text-muted">Собрать новый сайт или приложение с нуля</p>
                  </div>
                </button>

                <div className="flex justify-start pt-1">
                  <button onClick={() => setScreen("server")} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                    Назад
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Fork B step 1: Git repository (optional) ── */}
        {screen === "new_git" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-5">
              <h2 className="text-xl font-semibold text-text-main mb-1">Хранилище кода</h2>
              <p className="text-sm text-text-muted">Подключите Git-репозиторий для версий кода — или пропустите, можно добавить позже</p>
            </div>

            <div className="space-y-2 mb-4">
              <div className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-surface-2 opacity-60">
                <span className="text-xl">🐙</span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-text-main">Создать GitHub-репозиторий</p>
                  <p className="text-xs text-text-muted">Скоро — подключение по токену доступа</p>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-md bg-surface-3 text-text-muted">скоро</span>
              </div>
            </div>

            <div className="flex justify-between">
              <button onClick={() => setScreen("discovery")} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                Назад
              </button>
              <button onClick={() => setScreen("new_describe")} className="bg-accent hover:bg-accent-hover text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2">
                Пропустить
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Fork B step 2: Describe new project ── */}
        {screen === "new_describe" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-4">
              <h2 className="text-xl font-semibold text-text-main mb-1">Опишите проект</h2>
              <p className="text-sm text-text-muted">Что нужно создать? Система проанализирует и уточнит детали</p>
            </div>

            <textarea
              className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors resize-none h-36"
              placeholder={"Например:\n«Лендинг для кофейни с меню, формой бронирования столика и картой проезда.»"}
              value={projectDesc}
              onChange={(e) => setProjectDesc(e.target.value)}
              autoFocus
            />

            <div className="flex justify-between mt-5">
              <button onClick={() => setScreen("new_git")} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                Назад
              </button>
              <button
                onClick={handleCreateProject}
                disabled={!projectDesc.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                Создать и проанализировать
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Working (final async) ── */}
        {screen === "working" && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-5">
              <h2 className="text-xl font-semibold text-text-main mb-1">{error ? "Ошибка" : loading ? "Готовлю проект..." : "Готово!"}</h2>
              {!error && <p className="text-sm text-text-muted">Это займёт несколько секунд</p>}
            </div>
            <LogTerminal lines={scanLog} loading={loading} />
            {error && (
              <div className="mt-4 flex gap-2">
                <button onClick={() => setScreen(selectedSite ? "discovery" : "new_describe")} className="flex-1 border border-border rounded-xl py-2.5 text-sm text-text-sub hover:bg-surface-2 transition-colors">
                  Назад
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <style jsx global>{`
        .field {
          width: 100%;
          border-radius: 12px;
          border: 1px solid #e8eaed;
          background: #f5f6f8;
          padding: 10px 14px;
          font-size: 13px;
          color: #111827;
          transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
        }
        .field::placeholder {
          color: #9ca3af;
        }
        .field:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
          background: #fff;
          outline: none;
        }
      `}</style>
    </main>
  );
}
