"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

/* ─── Types ──────────────────────────────────────────────────────────────── */
type ConnectMethod = "ssh_password" | "ssh_key" | "ftp" | "sftp";

type FormState = {
  // Step 1
  projectName: string;
  // Step 2
  tzRaw: string;
  // Step 3
  connectMethod: ConnectMethod;
  host: string;
  port: string;
  user: string;
  password: string;
  privateKey: string;
  siteUrl: string;
};

type StepId = 1 | 2 | 3 | 4;

/* ─── Helpers ─────────────────────────────────────────────────────────────── */
const STEP_LABELS = ["Проект", "Задача", "Подключение", "Анализ"];

function ProgressBar({ step }: { step: StepId }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEP_LABELS.map((label, i) => {
        const n = (i + 1) as StepId;
        const done = step > n;
        const active = step === n;
        return (
          <div key={n} className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors
              ${done ? "bg-accent text-white" : active ? "bg-accent text-white" : "bg-surface-3 text-text-muted"}`}>
              {done ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5L4.5 7.5L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : n}
            </div>
            <span className={`text-xs hidden sm:block ${active ? "text-text-main font-medium" : "text-text-muted"}`}>{label}</span>
            {i < STEP_LABELS.length - 1 && (
              <div className={`h-px w-6 sm:w-12 ${done ? "bg-accent" : "bg-border"}`} />
            )}
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
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </button>
        </div>
        <ol className="space-y-3 text-sm">
          {[
            { title: "Откройте терминал", cmd: null, desc: "macOS/Linux: Terminal. Windows: PowerShell или WSL" },
            { title: "Создайте ключ", cmd: "ssh-keygen -t ed25519 -C \"sitedoc\"", desc: "Нажмите Enter три раза (без пароля)" },
            { title: "Скопируйте публичный ключ", cmd: "cat ~/.ssh/id_ed25519.pub", desc: "Добавьте его в ~/.ssh/authorized_keys на сервере" },
            { title: "Скопируйте приватный ключ", cmd: "cat ~/.ssh/id_ed25519", desc: "Вставьте его ниже в поле «SSH-ключ»" },
          ].map((item, i) => (
            <li key={i} className="flex gap-3">
              <span className="w-5 h-5 rounded-full bg-accent/10 text-accent flex items-center justify-center text-xs font-medium flex-shrink-0 mt-0.5">{i + 1}</span>
              <div>
                <p className="font-medium text-text-main">{item.title}</p>
                {item.cmd && (
                  <code className="block bg-surface-3 border border-border rounded-lg px-3 py-1.5 text-xs font-mono my-1">{item.cmd}</code>
                )}
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

/* ─── Main component ──────────────────────────────────────────────────────── */
export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState<StepId>(1);
  const [form, setForm] = useState<FormState>({
    projectName: "", tzRaw: "", connectMethod: "ssh_password",
    host: "", port: "", user: "root", password: "", privateKey: "", siteUrl: "",
  });
  const [showSshHint, setShowSshHint] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scanLog, setScanLog] = useState<string[]>([]);

  const set = (k: keyof FormState, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const defaultPort = form.connectMethod === "ftp" ? "21" : form.connectMethod === "sftp" ? "22" : "22";

  /* ── Navigation ── */
  function next() { setStep((s) => Math.min(s + 1, 4) as StepId); setError(""); }
  function back() { setStep((s) => Math.max(s - 1, 1) as StepId); setError(""); }

  /* ── Submit (step 3 → 4: connect + scan) ── */
  async function handleConnect() {
    setLoading(true);
    setError("");
    setStep(4);
    setScanLog(["🔌 Подключаюсь к серверу..."]);

    try {
      const authType = form.connectMethod === "ssh_key" || form.connectMethod === "sftp"
        ? "platform_key" : form.connectMethod === "ftp" ? "ftp" : "password";

      const portNum = parseInt(form.port || defaultPort);

      const { data: site } = await api.post<{ id: string }>("/api/sites", {
        name: form.projectName,
        url: form.siteUrl || undefined,
        ssh_host: form.host,
        ssh_port: portNum,
        ssh_user: form.user,
        auth_type: authType,
        password: ["ssh_password", "ftp"].includes(form.connectMethod) ? form.password : undefined,
        private_key: ["ssh_key", "sftp"].includes(form.connectMethod) ? form.privateKey : undefined,
      });

      setScanLog((p) => [...p, "✓ Подключено", "🔍 Определяю CMS и стек..."]);

      const { data: scan } = await api.post<any>(`/api/sites/${site.id}/scan`);

      const cmsLine = [scan.cms, scan.cms_version].filter(Boolean).join(" ");
      setScanLog((p) => [
        ...p,
        `✓ CMS: ${cmsLine || "не определена"}`,
        scan.php_version ? `✓ PHP ${scan.php_version}` : null,
        scan.web_server ? `✓ ${scan.web_server}` : null,
        scan.site_root_path ? `✓ Корень: ${scan.site_root_path}` : null,
        "✓ Готово! Открываю проект...",
      ].filter(Boolean) as string[]);

      await new Promise((r) => setTimeout(r, 800));
      router.push(`/site/${site.id}`);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Ошибка подключения";
      setError(msg);
      setScanLog((p) => [...p, `✗ ${msg}`]);
      setLoading(false);
    }
  }

  /* ── Render steps ── */
  return (
    <main className="min-h-screen bg-surface-2 flex flex-col items-center justify-center px-6 py-12">
      {showSshHint && <SshHint onClose={() => setShowSshHint(false)} />}

      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-xl bg-accent flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-text-main">SiteDoc</span>
        </div>

        <ProgressBar step={step} />

        {/* ── Step 1: Project name ── */}
        {step === 1 && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-text-main mb-1">Как называется ваш проект?</h2>
              <p className="text-sm text-text-muted">Это может быть название сайта или компании</p>
            </div>

            <input
              className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-base text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
              placeholder="Например: Интернет-магазин TechShop"
              value={form.projectName}
              onChange={(e) => set("projectName", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && form.projectName.trim() && next()}
              autoFocus
            />

            <div className="flex justify-end mt-5">
              <button
                onClick={next}
                disabled={!form.projectName.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                Далее
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: TZ ── */}
        {step === 2 && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-text-main mb-1">Что нужно сделать?</h2>
              <p className="text-sm text-text-muted">Опишите задачу своими словами — система сама разберётся в деталях</p>
            </div>

            <textarea
              className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors resize-none h-36"
              placeholder={"Например:\n«Нужно исправить баннеры на главной странице — они отображаются неровно. Добавить слайдер на мобильной версии. Шрифт сделать одинаковым»"}
              value={form.tzRaw}
              onChange={(e) => set("tzRaw", e.target.value)}
              autoFocus
            />

            <div className="flex items-center gap-2 mt-3 p-3 bg-accent/5 border border-accent/15 rounded-xl">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-accent flex-shrink-0">
                <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M7 4V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <p className="text-xs text-accent/80">ИИ проанализирует сайт с учётом вашей задачи после подключения</p>
            </div>

            <div className="flex justify-between mt-5">
              <button onClick={back} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                Назад
              </button>
              <button
                onClick={next}
                disabled={!form.tzRaw.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                Далее
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Connection ── */}
        {step === 3 && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-text-main mb-1">Подключите сайт</h2>
              <p className="text-sm text-text-muted">Выберите способ доступа к серверу</p>
            </div>

            {/* Method selector */}
            <div className="grid grid-cols-2 gap-2 mb-5">
              {([
                { id: "ssh_password", icon: "🔑", label: "SSH", sub: "Пароль" },
                { id: "ssh_key",      icon: "🗝️", label: "SSH", sub: "Ключ" },
                { id: "ftp",          icon: "📂", label: "FTP", sub: "Пароль" },
                { id: "sftp",         icon: "🔒", label: "SFTP", sub: "Ключ" },
              ] as { id: ConnectMethod; icon: string; label: string; sub: string }[]).map((m) => (
                <button
                  key={m.id}
                  onClick={() => set("connectMethod", m.id)}
                  className={`flex items-center gap-2.5 px-3.5 py-3 rounded-xl border text-left transition-colors ${
                    form.connectMethod === m.id
                      ? "border-accent bg-accent/5 text-text-main"
                      : "border-border bg-surface-2 text-text-sub hover:border-accent/30"
                  }`}
                >
                  <span className="text-xl leading-none">{m.icon}</span>
                  <div>
                    <p className="text-sm font-medium leading-tight">{m.label}</p>
                    <p className="text-xs text-text-muted">{m.sub}</p>
                  </div>
                </button>
              ))}
            </div>

            {/* URL */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-text-sub mb-1.5">URL сайта</label>
              <input className="field" placeholder="https://example.ru" value={form.siteUrl} onChange={(e) => set("siteUrl", e.target.value)} />
            </div>

            {/* Host + port + user */}
            <div className="flex gap-2 mb-3">
              <div className="flex-1">
                <label className="block text-xs font-medium text-text-sub mb-1.5">
                  {["ftp", "sftp"].includes(form.connectMethod) ? "FTP-хост" : "SSH-хост"}
                </label>
                <input className="field" placeholder="185.100.50.1 или example.ru" value={form.host} onChange={(e) => set("host", e.target.value)} required />
              </div>
              <div className="w-20">
                <label className="block text-xs font-medium text-text-sub mb-1.5">Порт</label>
                <input className="field" placeholder={defaultPort} value={form.port} onChange={(e) => set("port", e.target.value)} />
              </div>
            </div>

            <div className="mb-3">
              <label className="block text-xs font-medium text-text-sub mb-1.5">Логин</label>
              <input className="field" value={form.user} onChange={(e) => set("user", e.target.value)} />
            </div>

            {/* Auth fields */}
            {["ssh_password", "ftp"].includes(form.connectMethod) && (
              <div className="mb-3">
                <label className="block text-xs font-medium text-text-sub mb-1.5">Пароль</label>
                <input type="password" className="field" placeholder="••••••••" value={form.password} onChange={(e) => set("password", e.target.value)} />
              </div>
            )}

            {["ssh_key", "sftp"].includes(form.connectMethod) && (
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-text-sub">SSH-ключ (приватный)</label>
                  <button onClick={() => setShowSshHint(true)} className="text-xs text-accent hover:underline">
                    Как создать? →
                  </button>
                </div>
                <textarea
                  className="field font-mono text-xs h-28 resize-none"
                  placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"}
                  value={form.privateKey}
                  onChange={(e) => set("privateKey", e.target.value)}
                />
              </div>
            )}

            {/* FTP hint */}
            {form.connectMethod === "ftp" && (
              <div className="mb-3 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700">
                ⚠️ FTP не шифрует данные. Рекомендуем SFTP или SSH для безопасности.
              </div>
            )}

            {/* Where to find creds */}
            <details className="mb-4">
              <summary className="text-xs text-text-muted cursor-pointer hover:text-text-sub select-none">
                Где найти данные для подключения?
              </summary>
              <div className="mt-2 p-3 bg-surface-3 rounded-xl text-xs text-text-sub space-y-1.5">
                <p>• <strong>Хостинг-провайдеры</strong> (Timeweb, SpaceWeb, Beget): панель управления → SSH / FTP → настройки</p>
                <p>• <strong>VPS/VDS</strong>: в письме от провайдера при заказе</p>
                <p>• <strong>ISPmanager</strong>: Главное меню → Пользователи → SSH</p>
                <p>• Нет доступа? Попросите администратора выдать SSH-пользователя</p>
              </div>
            </details>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-3">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/><path d="M7 4.5V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                {error}
                <button onClick={() => { setError(""); setStep(3); }} className="ml-auto text-xs underline">Исправить</button>
              </div>
            )}

            <div className="flex justify-between">
              <button onClick={back} className="text-sm text-text-muted hover:text-text-main px-4 py-2.5 rounded-xl hover:bg-surface-3 transition-colors">
                Назад
              </button>
              <button
                onClick={handleConnect}
                disabled={loading || !form.host.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
              >
                Подключить и проанализировать
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Step 4: Scanning ── */}
        {step === 4 && (
          <div className="bg-surface rounded-2xl border border-border shadow-card p-6">
            <div className="mb-5">
              <h2 className="text-xl font-semibold text-text-main mb-1">
                {error ? "Ошибка подключения" : loading ? "Анализирую сайт..." : "Готово!"}
              </h2>
              {!error && <p className="text-sm text-text-muted">Это займёт около 20–30 секунд</p>}
            </div>

            <div className="bg-surface-2 border border-border rounded-xl p-4 font-mono text-xs space-y-1.5 min-h-32">
              {scanLog.map((line, i) => (
                <p key={i} className={
                  line.startsWith("✗") ? "text-red-500" :
                  line.startsWith("✓") ? "text-emerald-600" :
                  "text-text-sub"
                }>{line}</p>
              ))}
              {loading && (
                <div className="flex items-center gap-2 text-text-muted">
                  <svg className="animate-spin" width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" strokeDasharray="14 10"/>
                  </svg>
                  <span>работаю...</span>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-4 flex gap-2">
                <button onClick={() => { setStep(3); setError(""); }} className="flex-1 border border-border rounded-xl py-2.5 text-sm text-text-sub hover:bg-surface-2 transition-colors">
                  Изменить данные
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
        .field::placeholder { color: #9ca3af; }
        .field:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
          background: #fff;
          outline: none;
        }
      `}</style>
    </main>
  );
}
