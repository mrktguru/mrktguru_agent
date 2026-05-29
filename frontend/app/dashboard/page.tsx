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

const CMS_COLORS: Record<string, string> = {
  wordpress: "bg-blue-900 text-blue-200",
  joomla: "bg-orange-900 text-orange-200",
  bitrix: "bg-red-900 text-red-200",
  laravel: "bg-pink-900 text-pink-200",
  opencart: "bg-green-900 text-green-200",
  custom: "bg-gray-700 text-gray-200",
};

export default function DashboardPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    load();
  }, []);

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

  const uptimeColor = (u: number | null) => {
    if (u === null) return "text-gray-500";
    if (u >= 99) return "text-green-400";
    if (u >= 95) return "text-yellow-400";
    return "text-red-400";
  };

  const scoreColor = (s: number | null) => {
    if (s === null) return "text-gray-500";
    if (s >= 80) return "text-green-400";
    if (s >= 60) return "text-yellow-400";
    return "text-red-400";
  };

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-semibold">Мои сайты</h1>
        <div className="flex items-center gap-4">
          {user && (
            <div className="text-sm text-gray-400">
              <span className="text-white font-medium">{user.token_credits.toFixed(0)}</span>
              {" "}кредитов · {user.plan}
            </div>
          )}
          <button
            className="text-sm text-gray-400 hover:text-white"
            onClick={() => {
              window.localStorage.removeItem("token");
              router.push("/");
            }}
          >
            Выйти
          </button>
        </div>
      </div>

      {/* Add site button */}
      <div className="mt-6">
        <button
          onClick={() => router.push("/site/connect")}
          className="rounded-md border border-dashed border-gray-600 px-4 py-2 text-sm text-gray-400 hover:border-accent hover:text-white transition-colors"
        >
          + Добавить сайт
        </button>
      </div>

      {/* Sites list */}
      <div className="mt-6 space-y-3">
        {sites.length === 0 && (
          <div className="text-gray-500 mt-8 text-center">
            Нет подключённых сайтов — добавьте первый.
          </div>
        )}
        {sites.map((s) => (
          <a
            key={s.id}
            href={`/site/${s.id}`}
            className="block rounded-lg border border-gray-800 p-4 hover:border-accent transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Status dot + name */}
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    s.status === "active" ? "bg-green-400" :
                    s.status === "error" ? "bg-red-400" : "bg-yellow-400"
                  }`} />
                  <span className="font-medium truncate">{s.name}</span>
                </div>
                {/* URL */}
                {s.url && (
                  <div className="mt-1 text-xs text-gray-500 truncate">{s.url}</div>
                )}
                {/* Badges */}
                <div className="mt-2 flex flex-wrap gap-1">
                  {s.cms && (
                    <span className={`text-xs px-2 py-0.5 rounded ${CMS_COLORS[s.cms] || CMS_COLORS.custom}`}>
                      {s.cms}{s.cms_version ? ` ${s.cms_version}` : ""}
                    </span>
                  )}
                  {s.web_server && (
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">
                      {s.web_server}
                    </span>
                  )}
                </div>
              </div>
              {/* Stats */}
              <div className="text-right text-sm flex-shrink-0">
                {s.uptime_percent !== null && (
                  <div className={uptimeColor(s.uptime_percent)}>
                    {s.uptime_percent.toFixed(1)}% uptime
                  </div>
                )}
                {s.audit_score !== null && (
                  <div className={`text-xs mt-1 ${scoreColor(s.audit_score)}`}>
                    Аудит {s.audit_score}/100
                  </div>
                )}
                <div className="text-xs text-gray-600 mt-1">Открыть →</div>
              </div>
            </div>
          </a>
        ))}
      </div>
    </main>
  );
}
