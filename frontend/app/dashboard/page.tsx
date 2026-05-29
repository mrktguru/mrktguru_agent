"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Site = {
  id: string; name: string; url: string | null; status: string;
  cms: string | null; cms_version: string | null; audit_score: number | null;
  uptime_percent: number | null; created_at: string;
};

type User = { name: string | null; email: string; plan: string; token_credits: number };

const CMS_BADGE: Record<string, string> = {
  wordpress: "bg-blue-50 text-blue-600 border-blue-100",
  joomla: "bg-orange-50 text-orange-600 border-orange-100",
  bitrix: "bg-red-50 text-red-600 border-red-100",
  laravel: "bg-pink-50 text-pink-600 border-pink-100",
  opencart: "bg-green-50 text-green-600 border-green-100",
  custom: "bg-gray-100 text-gray-500 border-gray-200",
};

const NAV_ITEMS = [
  { icon: "◻", label: "Проекты", href: "/dashboard", active: true },
  { icon: "⚙", label: "Настройки", href: "#", active: false },
];

export default function DashboardPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const [sitesRes, userRes] = await Promise.all([
        api.get<Site[]>("/api/sites"),
        api.get<User>("/api/auth/me"),
      ]);
      setSites(sitesRes.data);
      setUser(userRes.data);
    } catch { router.push("/login"); }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-2">
      {/* ── Left sidebar ── */}
      <aside className="w-60 bg-surface border-r border-border flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 border-b border-border flex items-center gap-2.5 h-[57px] flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-sm text-text-main">SiteDoc</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 space-y-0.5">
          {/* Section label */}
          <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-2 mb-2">Меню</p>

          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-colors ${
                item.active
                  ? "bg-accent/8 text-accent font-medium"
                  : "text-text-sub hover:bg-surface-2 hover:text-text-main"
              }`}
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" className="flex-shrink-0">
                {item.label === "Проекты" ? (
                  <>
                    <rect x="1.5" y="1.5" width="5" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                    <rect x="8.5" y="1.5" width="5" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                    <rect x="1.5" y="8.5" width="5" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                    <rect x="8.5" y="8.5" width="5" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                  </>
                ) : (
                  <>
                    <circle cx="7.5" cy="7.5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M7.5 1v2M7.5 12v2M1 7.5h2M12 7.5h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  </>
                )}
              </svg>
              {item.label}
            </a>
          ))}

          {/* Projects list */}
          <div className="mt-3 pt-3 border-t border-border space-y-0.5">
            <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-2 mb-2">Проекты</p>

            {sites.map((s) => (
              <a
                key={s.id}
                href={`/site/${s.id}`}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-text-sub hover:bg-surface-2 hover:text-text-main transition-colors group"
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.status === "active" ? "bg-emerald-400" : "bg-gray-300"}`} />
                <span className="truncate">{s.name}</span>
              </a>
            ))}

            <button
              onClick={() => router.push("/projects/new")}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-sm text-text-muted hover:text-accent hover:bg-accent/5 transition-colors"
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M6.5 1.5V11.5M1.5 6.5H11.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Добавить проект
            </button>
          </div>
        </nav>

        {/* User */}
        {user && (
          <div className="border-t border-border px-4 py-3 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-xs font-medium text-text-main truncate">{user.name || user.email}</p>
              <p className="text-xs text-text-muted">{(user.token_credits ?? 0).toFixed(0)} кредитов</p>
            </div>
            <button
              onClick={() => { localStorage.removeItem("token"); router.push("/"); }}
              className="text-text-muted hover:text-text-main transition-colors flex-shrink-0"
              title="Выйти"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9.5 7H2M5 4L2 7L5 10M8 2H11.5C12.05 2 12.5 2.45 12.5 3V11C12.5 11.55 12.05 12 11.5 12H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        )}
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-surface border-b border-border px-8 flex items-center h-[57px] z-10">
          <h1 className="text-base font-semibold text-text-main">Проекты</h1>
        </div>

        <div className="px-8 py-6">
          {sites.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center text-center min-h-80 max-w-sm mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-surface border border-border shadow-card flex items-center justify-center mb-5">
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                  <rect x="2" y="4" width="24" height="20" rx="4" stroke="#d1d5db" strokeWidth="1.5"/>
                  <path d="M2 10H26" stroke="#d1d5db" strokeWidth="1.5"/>
                  <circle cx="6" cy="7" r="1.5" fill="#d1d5db"/>
                  <circle cx="10" cy="7" r="1.5" fill="#d1d5db"/>
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-text-main mb-2">Пока нет проектов</h2>
              <p className="text-sm text-text-muted mb-6">Создайте первый проект — подключите сайт и начните редактировать с помощью ИИ</p>
              <button
                onClick={() => router.push("/projects/new")}
                className="bg-accent hover:bg-accent-hover text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors"
              >
                Создать первый проект
              </button>
            </div>
          ) : (
            /* Projects grid */
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {sites.map((s) => {
                const cmsKey = s.cms || "custom";
                const cmsBadge = CMS_BADGE[cmsKey] || CMS_BADGE.custom;
                return (
                  <a
                    key={s.id}
                    href={`/site/${s.id}`}
                    className="group bg-surface rounded-2xl border border-border hover:border-accent/25 hover:shadow-card-hover p-5 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${s.status === "active" ? "bg-emerald-400" : s.status === "error" ? "bg-red-400" : "bg-amber-400"}`} />
                        <span className="font-medium text-sm text-text-main">{s.name}</span>
                      </div>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-text-muted group-hover:text-accent transition-colors flex-shrink-0">
                        <path d="M5 11L9 7L5 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>

                    {s.url && <p className="text-xs text-text-muted truncate mb-3">{s.url}</p>}

                    <div className="flex flex-wrap gap-1.5">
                      {s.cms && (
                        <span className={`text-xs px-2 py-0.5 rounded-lg border font-medium ${cmsBadge}`}>
                          {s.cms}{s.cms_version ? ` ${s.cms_version}` : ""}
                        </span>
                      )}
                      {s.audit_score !== null && (
                        <span className={`text-xs px-2 py-0.5 rounded-lg border ${
                          s.audit_score >= 80 ? "bg-emerald-50 text-emerald-600 border-emerald-100" :
                          s.audit_score >= 60 ? "bg-amber-50 text-amber-600 border-amber-100" :
                          "bg-red-50 text-red-600 border-red-100"
                        }`}>
                          {s.audit_score}/100
                        </span>
                      )}
                      {s.uptime_percent !== null && (
                        <span className="text-xs px-2 py-0.5 rounded-lg border border-border bg-surface-2 text-text-sub">
                          {s.uptime_percent.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </a>
                );
              })}

              {/* Add project card */}
              <button
                onClick={() => router.push("/projects/new")}
                className="flex flex-col items-center justify-center bg-surface rounded-2xl border border-dashed border-border hover:border-accent/40 hover:bg-accent/2 p-5 transition-all min-h-32 text-text-muted hover:text-accent"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="mb-2">
                  <path d="M10 3V17M3 10H17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                <span className="text-sm font-medium">Добавить проект</span>
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
