"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");
    if (token) {
      window.localStorage.setItem("token", token);
      router.replace("/dashboard");
    }
  }, [params, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await api.post("/api/auth/login", { email, password });
      window.localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Ошибка входа");
    }
  }

  return (
    <main className="mx-auto max-w-md px-6 py-24">
      <h1 className="text-2xl font-semibold">Войти</h1>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2"
          type="email"
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2"
          type="password"
          placeholder="пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <div className="text-sm text-red-400">{error}</div>}
        <button className="w-full rounded-md bg-accent px-3 py-2 font-medium text-white">
          Войти
        </button>
      </form>
      <div className="my-4 flex items-center gap-3 text-xs text-gray-500">
        <div className="h-px flex-1 bg-gray-800" />
        или
        <div className="h-px flex-1 bg-gray-800" />
      </div>
      <a
        href="/api/auth/google/login"
        className="block w-full rounded-md border border-gray-700 px-3 py-2 text-center font-medium hover:bg-gray-900"
      >
        Войти через Google
      </a>
    </main>
  );
}
