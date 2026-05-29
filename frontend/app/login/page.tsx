"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");
    if (token) {
      localStorage.setItem("token", token);
      redirectAfterLogin();
    }
  }, [params]);

  async function redirectAfterLogin() {
    try {
      const { data } = await api.get<any[]>("/api/sites");
      router.replace(data.length === 0 ? "/projects/new" : "/dashboard");
    } catch {
      router.replace("/projects/new");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post("/api/auth/login", { email, password });
      localStorage.setItem("token", data.access_token);
      await redirectAfterLogin();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Неверный email или пароль");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 bg-surface-2">
      <div className="w-full max-w-sm">
        <a href="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-xl bg-accent flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-text-main">SiteDoc</span>
        </a>

        <div className="bg-surface rounded-2xl shadow-card border border-border p-6">
          <h1 className="text-xl font-semibold text-text-main mb-5">Войти</h1>

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-text-sub mb-1.5">Email</label>
              <input
                className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
                type="email" placeholder="you@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)} required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-sub mb-1.5">Пароль</label>
              <input
                className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 focus:bg-surface transition-colors"
                type="password" placeholder="••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)} required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/><path d="M7 4.5V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full rounded-xl bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors disabled:opacity-60">
              {loading ? "Вхожу..." : "Войти"}
            </button>
          </form>

          <div className="my-4 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" /><span className="text-xs text-text-muted">или</span><div className="h-px flex-1 bg-border" />
          </div>

          <a href="/api/auth/google/login"
            className="flex items-center justify-center gap-2 w-full rounded-xl border border-border hover:bg-surface-3 px-3.5 py-2.5 text-sm font-medium text-text-main transition-colors">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M15.68 8.18c0-.57-.05-1.11-.14-1.64H8v3.1h4.31a3.68 3.68 0 01-1.6 2.42v2h2.59c1.52-1.4 2.38-3.46 2.38-5.88z" fill="#4285F4"/>
              <path d="M8 16c2.16 0 3.97-.72 5.3-1.94l-2.59-2a4.77 4.77 0 01-7.1-2.5H.98v2.07A8 8 0 008 16z" fill="#34A853"/>
              <path d="M3.61 9.56A4.82 4.82 0 013.36 8c0-.54.1-1.07.25-1.56V4.37H.98A8.02 8.02 0 000 8c0 1.29.31 2.51.98 3.63l2.63-2.07z" fill="#FBBC05"/>
              <path d="M8 3.18c1.22 0 2.31.42 3.17 1.24l2.38-2.38A7.95 7.95 0 008 0 8 8 0 00.98 4.37l2.63 2.07A4.77 4.77 0 018 3.18z" fill="#EA4335"/>
            </svg>
            Войти через Google
          </a>
        </div>

        <p className="mt-4 text-center text-sm text-text-muted">
          Нет аккаунта?{" "}
          <a href="/register" className="text-accent hover:underline font-medium">Создать</a>
        </p>
      </div>
    </main>
  );
}
