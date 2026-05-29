"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post("/api/auth/register", { email, password, name });
      window.localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Ошибка регистрации");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <a href="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-xl bg-accent flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-semibold text-text-main">SiteDoc</span>
        </a>

        <div className="bg-surface rounded-2xl shadow-card border border-border p-6">
          <h1 className="text-xl font-semibold text-text-main mb-5">Создать аккаунт</h1>

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-text-sub mb-1.5">Имя</label>
              <input
                className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 transition-colors"
                placeholder="Как вас зовут?"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-sub mb-1.5">Email</label>
              <input
                className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 transition-colors"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-sub mb-1.5">Пароль</label>
              <input
                className="w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text-main placeholder:text-text-muted focus:border-accent focus:ring-2 focus:ring-accent/10 transition-colors"
                type="password"
                placeholder="Минимум 8 символов"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M7 4.5V7.5M7 9.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors disabled:opacity-60 mt-1"
            >
              {loading ? "Создаю..." : "Зарегистрироваться"}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-sm text-text-muted">
          Уже есть аккаунт?{" "}
          <a href="/login" className="text-accent hover:underline font-medium">Войти</a>
        </p>
      </div>
    </main>
  );
}
