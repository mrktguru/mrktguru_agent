"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Site = {
  id: string;
  name: string;
  url: string | null;
  status: string;
  cms: string | null;
  cms_version: string | null;
  web_server: string | null;
  audit_score: number | null;
  uptime_percent: number | null;
};

type User = {
  name: string | null;
  email: string;
  plan: string;
  token_credits: number;
};

const CMS_BADGE: Record<string, { label: string; color: string }> = {
  wordpress: { label: "WordPress", color: "bg-blue-50 text-blue-600 border-blue-100" },
  joomla:    { label: "Joomla",    color: "bg-orange-50 text-orange-600 border-orange-100" },
  bitrix:    { label: "Битрикс",   color: "bg-red-50 text-red-600 border-red-100" },
  laravel:   { label: "Laravel",   color: "bg-pink-50 text-pink-600 border-pink-100" },
  opencart:  { label: "OpenCart",  color: "bg-green-50 text-green-600 border-green-100" },
  custom:    { label: "Custom",    color: "bg-gray-100 text-gray-500 border-gray-200" },
};

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
    } catch {
      router.push("/login");
    }
  }

  const scoreColor = (s: number | null) =>
    s === null ? "text-text-muted" : s >= 80 ? "text-emerald-600" : s >= 60 ? "text-amber-500" : "text-red-500";

  const uptimeColor = (u: number | null) =>
    u === null ? "text-text-muted" : u >= 99 ? "text-emerald-600" : u >= 95 ? "text-amber-500" : "text-red-500";

  return (
    <div className="min-h-screen bg-surface-2">
      {/* Top nav */}
      <header className="bg-surface border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-sm text-text-main">SiteDoc</span>
        </div>

        <div className="flex items-center gap-4">
          {user && (
            <div className="flex items-center gap-3 text-sm">
              <div className="flex items-center gap-1.5 bg-accent/8 text-accent px-3 py-1 rounded-full">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M6 3.5V6.5L8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
                <span className="font-medium">{(user.token_credits ?? 0).toFixed(0)}</span>
                <span className="text-accent/60">кред.</span>
              </div>
              <span className="text-text-muted text-xs">{user.email}</span>
            </div>
          )}
          <button
            onClick={() => { localStorage.removeItem("token"); router.push("/"); }}
            className="text-xs text-text-muted hover:text-text-main transition-colors"
          >
            Выйти
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Page title + action */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-text-main">Мои сайты</h1>
            <p className="text-sm text-text-muted mt-0.5">{sites.length} подключено</p>
          </div>
          <button
            onClick={() => router.push("/site/connect")}
            className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 2V12M2 7H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Добавить сайт
          </button>
        </div>

        {/* Sites grid */}
        {sites.length === 0 ? (
          <div className="bg-surface rounded-2xl border border-dashed border-border p-12 text-center">
            <div className="w-12 h-12 rounded-2xl bg-surface-3 flex items-center justify-center mx-auto mb-4">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="3" width="16" height="14" rx="3" stroke="#9ca3af" strokeWidth="1.4"/>
                <path d="M2 7H18" stroke="#9ca3af" strokeWidth="1.4"/>
                <circle cx="5" cy="5" r="1" fill="#9ca3af"/>
                <circle cx="8" cy="5" r="1" fill="#9ca3af"/>
              </svg>
            </div>
            <p className="text-text-sub font-medium mb-1">Нет подключённых сайтов</p>
            <p className="text-sm text-text-muted mb-4">Добавьте первый сайт, чтобы начать</p>
            <button
              onClick={() => router.push("/site/connect")}
              className="text-sm text-accent hover:underline font-medium"
            >
              Подключить сайт →
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {sites.map((s) => {
              const cms = CMS_BADGE[s.cms || ""] || CMS_BADGE.custom;
              return (
                <a
                  key={s.id}
                  href={`/site/${s.id}`}
                  className="group bg-surface rounded-2xl border border-border hover:border-accent/30 hover:shadow-card-hover p-5 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      {/* Status + name */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          s.status === "active" ? "bg-emerald-400" :
                          s.status === "error" ? "bg-red-400" : "bg-amber-400"
                        }`} />
                        <span className="font-medium text-text-main truncate">{s.name}</span>
                      </div>
                      {s.url && <p className="text-xs text-text-muted truncate mb-3">{s.url}</p>}

                      {/* Badges */}
                      <div className="flex flex-wrap gap-1.5">
                        {s.cms && (
                          <span className={`text-xs px-2 py-0.5 rounded-lg border font-medium ${cms.color}`}>
                            {cms.label}{s.cms_version ? ` ${s.cms_version}` : ""}
                          </span>
                        )}
                        {s.web_server && (
                          <span className="text-xs px-2 py-0.5 rounded-lg border border-border bg-surface-2 text-text-sub">
                            {s.web_server}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="text-right flex-shrink-0 space-y-1">
                      {s.uptime_percent !== null && (
                        <p className={`text-xs font-medium ${uptimeColor(s.uptime_percent)}`}>
                          {s.uptime_percent.toFixed(1)}%
                        </p>
                      )}
                      {s.audit_score !== null && (
                        <p className={`text-xs ${scoreColor(s.audit_score)}`}>
                          {s.audit_score}/100
                        </p>
                      )}
                      <div className="text-xs text-text-muted group-hover:text-accent transition-colors mt-2">
                        Открыть →
                      </div>
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
