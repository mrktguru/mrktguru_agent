"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import MobileTopBar from "@/components/layout/MobileTopBar";
import MobileDrawer from "@/components/layout/MobileDrawer";

/* ─── Types ──────────────────────────────────────────────────────────────── */
type Me = { email: string; is_admin?: boolean };
type Stats = { users: number; sites: number; tasks: number; tokens_used: number };
type AdminUser = { id: string; email: string; name: string | null; plan: string; is_admin: boolean; token_credits: number };
type AdminSite = { id: string; name: string; url: string | null; status: string; cms: string | null; cms_version: string | null; owner_email: string };
type AdminTask = { id: string; title: string | null; status: string; estimated_credits: number | null; actual_credits: number | null; owner_email: string; site_name: string; created_at: string | null };

type DialogTurn =
  | { role: "user"; type: "message"; text: string }
  | { role: "agent"; type: "clarify"; questions: string[] }
  | { role: "agent"; type: "estimate"; subtasks: any[]; total_credits: number | null; confidence: string | null }
  | { role: "agent"; type: "logs"; status: string; entries: { status: string; message: string; timestamp: string | null }[] };

type TaskDialog = {
  task_id: string; title: string | null; status: string;
  user_email: string; site_name: string; created_at: string | null;
  turns: DialogTurn[];
};
type Layer = {
  layer_key: string; name: string; description: string | null; product: string;
  model: string; system_prompt: string; max_tokens: number; temperature: number;
  enabled: boolean; is_default: boolean;
};

type Section = "overview" | "users" | "sites" | "tasks" | "models" | "billing";

const PRODUCT_LABEL: Record<string, string> = { sitedoc: "SiteDoc" };
const PRODUCT_COLOR: Record<string, string> = {
  sitedoc: "bg-indigo-50 text-indigo-600 border-indigo-100",
};
const STATUS_COLOR: Record<string, string> = {
  done: "text-emerald-600", failed: "text-red-500", running: "text-accent",
  rolled_back: "text-amber-600", estimated: "text-text-sub", pending: "text-text-muted", approved: "text-accent",
};

const NAV: { key: Section; icon: string; label: string }[] = [
  { key: "overview", icon: "📊", label: "Обзор" },
  { key: "users", icon: "👤", label: "Пользователи" },
  { key: "sites", icon: "🌐", label: "Сайты" },
  { key: "tasks", icon: "📋", label: "Логи задач" },
  { key: "models", icon: "🤖", label: "ИИ-модели" },
  { key: "billing", icon: "💳", label: "Оплаты" },
];

/* ─── Page ───────────────────────────────────────────────────────────────── */
export default function AdminPage() {
  const router = useRouter();
  const [section, setSection] = useState<Section>("overview");
  const [authorized, setAuthorized] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  function selectSection(key: Section) { setSection(key); setNavOpen(false); }

  useEffect(() => {
    api.get<Me>("/api/auth/me")
      .then(({ data }) => {
        if (!data.is_admin) { router.replace("/dashboard"); return; }
        setAuthorized(true);
      })
      .catch(() => router.replace("/login"));
  }, []);

  if (!authorized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-2">
        <svg className="animate-spin text-accent" width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" strokeDasharray="40 20"/>
        </svg>
      </div>
    );
  }

  const sidebarInner = (
    <>
        <div className="px-5 border-b border-border flex items-center gap-2.5 h-[57px] flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-sm text-text-main">Админка</span>
        </div>

        <nav className="flex-1 px-3 py-3 space-y-0.5">
          <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-2 mb-2">Разделы</p>
          {NAV.map((n) => (
            <button
              key={n.key}
              onClick={() => selectSection(n.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-colors text-left ${
                section === n.key ? "bg-accent/8 text-accent font-medium" : "text-text-sub hover:bg-surface-2 hover:text-text-main"
              }`}
            >
              <span className="text-base leading-none">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          <button
            onClick={() => router.push("/dashboard")}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-text-muted hover:text-text-main hover:bg-surface-2 transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M7.5 9.5L4 6L7.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Назад в дашборд
          </button>
        </div>
    </>
  );

  const sectionLabel = NAV.find((n) => n.key === section)?.label ?? "Админка";

  return (
    <div className="flex h-screen overflow-hidden bg-surface-2">
      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex w-60 bg-surface border-r border-border flex-col flex-shrink-0">
        {sidebarInner}
      </aside>

      {/* Mobile nav */}
      <MobileTopBar title={sectionLabel} onMenu={() => setNavOpen(true)} />
      <MobileDrawer open={navOpen} onClose={() => setNavOpen(false)}>
        {sidebarInner}
      </MobileDrawer>

      {/* Content */}
      <main className="flex-1 overflow-y-auto pt-[57px] md:pt-0">
        <div className="hidden md:flex sticky top-0 bg-surface border-b border-border px-8 items-center h-[57px] z-10">
          <h1 className="text-base font-semibold text-text-main">{sectionLabel}</h1>
        </div>
        <div className="px-4 md:px-8 py-6">
          {section === "overview" && <OverviewSection />}
          {section === "users" && <UsersSection />}
          {section === "sites" && <SitesSection />}
          {section === "tasks" && <TasksSection />}
          {section === "models" && <ModelsSection />}
          {section === "billing" && <BillingSection />}
        </div>
      </main>
    </div>
  );
}

/* ─── Overview ───────────────────────────────────────────────────────────── */
function OverviewSection() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => { api.get<Stats>("/api/admin/stats").then(({ data }) => setStats(data)); }, []);
  const cards = [
    { label: "Пользователи", value: stats?.users, icon: "👤" },
    { label: "Сайты", value: stats?.sites, icon: "🌐" },
    { label: "Задачи", value: stats?.tasks, icon: "📋" },
    { label: "Токенов израсходовано", value: stats?.tokens_used, icon: "⚡" },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-surface rounded-2xl border border-border shadow-card p-5">
          <div className="text-2xl mb-2">{c.icon}</div>
          <p className="text-2xl font-semibold text-text-main">{c.value ?? "—"}</p>
          <p className="text-xs text-text-muted mt-0.5">{c.label}</p>
        </div>
      ))}
    </div>
  );
}

/* ─── Users ──────────────────────────────────────────────────────────────── */
function UsersSection() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const load = () => api.get<AdminUser[]>("/api/admin/users").then(({ data }) => setUsers(data));
  useEffect(() => { load(); }, []);

  async function patch(id: string, body: any) {
    const { data } = await api.patch<AdminUser>(`/api/admin/users/${id}`, body);
    setUsers((p) => p.map((u) => (u.id === id ? data : u)));
  }

  return (
    <div className="bg-surface rounded-2xl border border-border shadow-card overflow-x-auto">
      <table className="w-full text-sm whitespace-nowrap">
        <thead>
          <tr className="text-left text-xs text-text-muted border-b border-border">
            <th className="px-4 py-3 font-medium">Email</th>
            <th className="px-4 py-3 font-medium">План</th>
            <th className="px-4 py-3 font-medium">Кредиты</th>
            <th className="px-4 py-3 font-medium">Админ</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-surface-2">
              <td className="px-4 py-3">
                <div className="text-text-main">{u.email}</div>
                {u.name && <div className="text-xs text-text-muted">{u.name}</div>}
              </td>
              <td className="px-4 py-3">
                <select
                  value={u.plan}
                  onChange={(e) => patch(u.id, { plan: e.target.value })}
                  className="border border-border rounded-lg px-2 py-1 text-xs bg-surface-2 focus:border-accent"
                >
                  {["starter", "pro", "agency"].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </td>
              <td className="px-4 py-3">
                <input
                  type="number"
                  defaultValue={u.token_credits}
                  onBlur={(e) => { const v = parseFloat(e.target.value); if (v !== u.token_credits) patch(u.id, { token_credits: v }); }}
                  className="w-24 border border-border rounded-lg px-2 py-1 text-xs bg-surface-2 focus:border-accent"
                />
              </td>
              <td className="px-4 py-3">
                <button
                  onClick={() => patch(u.id, { is_admin: !u.is_admin })}
                  className={`relative w-9 h-5 rounded-full transition-colors ${u.is_admin ? "bg-accent" : "bg-surface-3 border border-border"}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${u.is_admin ? "left-4" : "left-0.5"}`} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Sites ──────────────────────────────────────────────────────────────── */
function SitesSection() {
  const [sites, setSites] = useState<AdminSite[]>([]);
  useEffect(() => { api.get<AdminSite[]>("/api/admin/sites").then(({ data }) => setSites(data)); }, []);
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-card overflow-x-auto">
      <table className="w-full text-sm whitespace-nowrap">
        <thead>
          <tr className="text-left text-xs text-text-muted border-b border-border">
            <th className="px-4 py-3 font-medium">Сайт</th>
            <th className="px-4 py-3 font-medium">CMS</th>
            <th className="px-4 py-3 font-medium">Владелец</th>
            <th className="px-4 py-3 font-medium">Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sites.map((s) => (
            <tr key={s.id} className="hover:bg-surface-2">
              <td className="px-4 py-3">
                <div className="text-text-main">{s.name}</div>
                {s.url && <div className="text-xs text-text-muted">{s.url}</div>}
              </td>
              <td className="px-4 py-3 text-text-sub">{s.cms ? `${s.cms} ${s.cms_version || ""}` : "—"}</td>
              <td className="px-4 py-3 text-text-sub">{s.owner_email}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center gap-1.5 text-xs ${s.status === "active" ? "text-emerald-600" : "text-text-muted"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${s.status === "active" ? "bg-emerald-400" : "bg-gray-300"}`} />
                  {s.status}
                </span>
              </td>
            </tr>
          ))}
          {sites.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-text-muted">Нет сайтов</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Tasks ──────────────────────────────────────────────────────────────── */
function TasksSection() {
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [dialog, setDialog] = useState<TaskDialog | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => { api.get<AdminTask[]>("/api/admin/tasks").then(({ data }) => setTasks(data)); }, []);

  async function openDialog(taskId: string) {
    setLoadingId(taskId);
    try {
      const { data } = await api.get<TaskDialog>(`/api/admin/tasks/${taskId}/dialog`);
      setDialog(data);
    } finally { setLoadingId(null); }
  }

  async function downloadDialog(taskId: string) {
    const { data } = await api.get<string>(`/api/admin/tasks/${taskId}/dialog/export`, { responseType: "text" });
    const blob = new Blob([data], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dialog_${taskId.slice(0, 8)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="bg-surface rounded-2xl border border-border shadow-card overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr className="text-left text-xs text-text-muted border-b border-border">
              <th className="px-4 py-3 font-medium">Задача</th>
              <th className="px-4 py-3 font-medium">Сайт</th>
              <th className="px-4 py-3 font-medium">Владелец</th>
              <th className="px-4 py-3 font-medium">Кредиты</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {tasks.map((t) => (
              <tr key={t.id} className="hover:bg-surface-2">
                <td className="px-4 py-3 text-text-main max-w-xs truncate">{t.title || "—"}</td>
                <td className="px-4 py-3 text-text-sub">{t.site_name}</td>
                <td className="px-4 py-3 text-text-sub">{t.owner_email}</td>
                <td className="px-4 py-3 text-text-sub">{t.actual_credits ?? t.estimated_credits ?? "—"}</td>
                <td className="px-4 py-3"><span className={`text-xs font-medium ${STATUS_COLOR[t.status] || "text-text-muted"}`}>{t.status}</span></td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => openDialog(t.id)}
                    disabled={loadingId === t.id}
                    className="text-xs text-accent hover:underline disabled:opacity-40"
                  >
                    {loadingId === t.id ? "..." : "Диалог"}
                  </button>
                </td>
              </tr>
            ))}
            {tasks.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-text-muted">Нет задач</td></tr>}
          </tbody>
        </table>
      </div>

      {dialog && (
        <DialogModal
          dialog={dialog}
          onClose={() => setDialog(null)}
          onDownload={() => downloadDialog(dialog.task_id)}
        />
      )}
    </>
  );
}

/* ─── Dialog modal ───────────────────────────────────────────────────────── */
function DialogModal({ dialog, onClose, onDownload }: {
  dialog: TaskDialog; onClose: () => void; onDownload: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-2xl bg-surface h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <div className="min-w-0">
            <h2 className="font-semibold text-text-main truncate">{dialog.title || "Диалог задачи"}</h2>
            <p className="text-xs text-text-muted mt-0.5">{dialog.user_email} · {dialog.site_name} · {dialog.created_at ? new Date(dialog.created_at).toLocaleString("ru") : "—"}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-4">
            <button
              onClick={onDownload}
              className="flex items-center gap-1.5 text-xs border border-border rounded-xl px-3 py-1.5 text-text-sub hover:text-text-main hover:bg-surface-2 transition-colors"
            >
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <path d="M6 1V8M3 5.5L6 8.5L9 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M1 10.5H11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              Скачать .txt
            </button>
            <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-2 text-text-muted hover:text-text-main transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M1 1L11 11M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Thread */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {dialog.turns.map((turn, i) => {
            if (turn.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="bg-accent text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-sm">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{turn.text}</p>
                  </div>
                </div>
              );
            }

            if (turn.type === "clarify") {
              return (
                <div key={i} className="flex gap-3 items-start">
                  <AgentDot />
                  <div className="bg-surface-2 border border-border rounded-2xl rounded-tl-sm px-4 py-3 flex-1 min-w-0">
                    <p className="text-xs font-semibold text-accent mb-2">Уточняющие вопросы</p>
                    <ol className="space-y-1">
                      {turn.questions.map((q, qi) => (
                        <li key={qi} className="flex gap-2 text-sm text-text-main">
                          <span className="text-accent font-semibold flex-shrink-0">{qi + 1}.</span>
                          <span>{q}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              );
            }

            if (turn.type === "estimate") {
              return (
                <div key={i} className="flex gap-3 items-start">
                  <AgentDot />
                  <div className="bg-surface-2 border border-border rounded-2xl rounded-tl-sm px-4 py-3 flex-1 min-w-0">
                    <p className="text-xs font-semibold text-accent mb-2">
                      План · {turn.confidence} · {(turn.total_credits || 0).toFixed(0)} кред.
                    </p>
                    <ol className="space-y-1.5">
                      {turn.subtasks.map((st: any, si: number) => (
                        <li key={si} className="text-sm text-text-main">
                          <span className="font-medium">{si + 1}. {st.title}</span>
                          {st.description && <span className="text-text-muted"> — {st.description}</span>}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              );
            }

            if (turn.type === "logs") {
              const successes = turn.entries.filter(e => e.status === "success").length;
              const errors = turn.entries.filter(e => e.status === "error").length;
              return (
                <div key={i} className="flex gap-3 items-start">
                  <AgentDot />
                  <div className="flex-1 min-w-0 border border-slate-200 rounded-2xl rounded-tl-sm overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-2.5 bg-white border-b border-slate-200">
                      <span className={`w-2 h-2 rounded-full ${turn.status === "done" ? "bg-emerald-400" : "bg-red-400"}`}/>
                      <span className="text-xs font-medium text-slate-600">
                        {turn.status === "done" ? "Выполнено" : "Ошибка"} · {successes} ✓{errors > 0 ? ` · ${errors} ✗` : ""}
                      </span>
                    </div>
                    <div className="px-4 py-3 bg-white font-mono text-xs space-y-1 max-h-52 overflow-y-auto">
                      {turn.entries.map((e, ei) => (
                        <div key={ei} className={`flex items-start gap-2 ${
                          e.status === "success" ? "text-emerald-700" :
                          e.status === "error" ? "text-red-600" : "text-slate-500"
                        }`}>
                          <span className="flex-shrink-0 w-3 text-center">{e.status === "success" ? "✓" : e.status === "error" ? "✗" : "·"}</span>
                          <span className="break-all">{e.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              );
            }

            return null;
          })}

          {dialog.turns.length === 0 && (
            <p className="text-sm text-text-muted text-center py-8">Диалог пуст</p>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentDot() {
  return (
    <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center flex-shrink-0 mt-0.5">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
        <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
      </svg>
    </div>
  );
}

/* ─── Models / Layers ────────────────────────────────────────────────────── */
function ModelsSection() {
  const [layers, setLayers] = useState<Layer[]>([]);
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    api.get<Layer[]>("/api/admin/llm-layers").then(({ data }) => setLayers(data));
    api.get<{ models: string[] }>("/api/admin/llm-models").then(({ data }) => setModels(data.models));
  }, []);

  const grouped = layers.reduce<Record<string, Layer[]>>((acc, l) => {
    (acc[l.product] = acc[l.product] || []).push(l);
    return acc;
  }, {});

  function onSaved(updated: Layer) {
    setLayers((p) => p.map((l) => (l.layer_key === updated.layer_key ? updated : l)));
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([product, group]) => (
        <div key={product}>
          <h2 className="text-sm font-semibold text-text-main mb-3 flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-lg border ${PRODUCT_COLOR[product]}`}>{PRODUCT_LABEL[product] || product}</span>
          </h2>
          <div className="space-y-3">
            {group.map((layer) => (
              <LayerCard key={layer.layer_key} layer={layer} models={models} onSaved={onSaved} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function LayerCard({ layer, models, onSaved }: { layer: Layer; models: string[]; onSaved: (l: Layer) => void }) {
  const [model, setModel] = useState(layer.model);
  const [customModel, setCustomModel] = useState(!models.includes(layer.model));
  const [prompt, setPrompt] = useState(layer.system_prompt);
  const [maxTokens, setMaxTokens] = useState(layer.max_tokens);
  const [temperature, setTemperature] = useState(layer.temperature);
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setModel(layer.model); setPrompt(layer.system_prompt);
    setMaxTokens(layer.max_tokens); setTemperature(layer.temperature);
    setCustomModel(!models.includes(layer.model));
  }, [layer, models]);

  const dirty = model !== layer.model || prompt !== layer.system_prompt || maxTokens !== layer.max_tokens || temperature !== layer.temperature;

  async function save() {
    setSaving(true);
    try {
      const { data } = await api.patch<Layer>(`/api/admin/llm-layers/${layer.layer_key}`, {
        model, system_prompt: prompt, max_tokens: maxTokens, temperature,
      });
      onSaved(data);
    } finally { setSaving(false); }
  }

  async function reset() {
    if (!confirm("Сбросить слой к значениям по умолчанию?")) return;
    setSaving(true);
    try {
      const { data } = await api.post<Layer>(`/api/admin/llm-layers/${layer.layer_key}/reset`);
      onSaved(data);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-surface rounded-2xl border border-border shadow-card p-5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-text-main">{layer.name}</h3>
            {layer.is_default
              ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-3 text-text-muted">по умолчанию</span>
              : <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">изменён</span>}
          </div>
          {layer.description && <p className="text-xs text-text-muted mt-0.5">{layer.description}</p>}
          <code className="text-[10px] text-text-muted">{layer.layer_key}</code>
        </div>
      </div>

      {/* Model + params */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-text-sub mb-1.5">Модель</label>
          {customModel ? (
            <div className="flex gap-2">
              <input
                value={model} onChange={(e) => setModel(e.target.value)}
                className="flex-1 border border-border rounded-xl px-3 py-2 text-sm bg-surface-2 font-mono focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface"
                placeholder="claude-..."
              />
              <button onClick={() => setCustomModel(false)} className="text-xs text-text-muted hover:text-text-main px-2">пресеты</button>
            </div>
          ) : (
            <div className="flex gap-2">
              <select
                value={model} onChange={(e) => setModel(e.target.value)}
                className="flex-1 border border-border rounded-xl px-3 py-2 text-sm bg-surface-2 focus:border-accent"
              >
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <button onClick={() => setCustomModel(true)} className="text-xs text-text-muted hover:text-text-main px-2">своя</button>
            </div>
          )}
        </div>
        <div>
          <label className="block text-xs font-medium text-text-sub mb-1.5">Max tokens</label>
          <input
            type="number" value={maxTokens} onChange={(e) => setMaxTokens(parseInt(e.target.value) || 0)}
            className="w-full border border-border rounded-xl px-3 py-2 text-sm bg-surface-2 focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface"
          />
        </div>
      </div>

      {/* Prompt */}
      <button onClick={() => setExpanded((v) => !v)} className="text-xs text-accent hover:underline mb-2">
        {expanded ? "Скрыть промпт ▲" : "Показать / редактировать промпт ▼"}
      </button>
      {expanded && (
        <div className="mb-3 space-y-3">
          <textarea
            value={prompt} onChange={(e) => setPrompt(e.target.value)}
            className="w-full border border-border rounded-xl px-3 py-2.5 text-xs font-mono bg-surface-2 h-64 resize-y focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface"
          />
          <div className="w-40">
            <label className="block text-xs font-medium text-text-sub mb-1.5">Temperature</label>
            <input
              type="number" step="0.1" min="0" max="1" value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value) || 0)}
              className="w-full border border-border rounded-xl px-3 py-2 text-sm bg-surface-2 focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface"
            />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={save} disabled={saving || !dirty}
          className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-medium px-4 py-1.5 rounded-xl transition-colors"
        >
          {saving ? "Сохраняю..." : "Сохранить"}
        </button>
        {!layer.is_default && (
          <button onClick={reset} disabled={saving} className="text-sm text-text-sub hover:text-text-main px-3 py-1.5 rounded-xl hover:bg-surface-2 transition-colors">
            Сбросить к дефолту
          </button>
        )}
      </div>
    </div>
  );
}

/* ─── Billing (placeholder) ──────────────────────────────────────────────── */
function BillingSection() {
  return (
    <div className="bg-surface rounded-2xl border border-dashed border-border p-12 text-center max-w-md mx-auto">
      <div className="text-3xl mb-3">💳</div>
      <p className="text-text-sub font-medium mb-1">Биллинг</p>
      <p className="text-sm text-text-muted">Раздел оплат появится при подключении платёжной системы.</p>
    </div>
  );
}
