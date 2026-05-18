"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await api.post("/api/auth/register", { email, password, name });
      window.localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Ошибка регистрации");
    }
  }

  return (
    <main className="mx-auto max-w-md px-6 py-24">
      <h1 className="text-2xl font-semibold">Создать аккаунт</h1>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          className="w-full rounded-md border border-gray-700 bg-transparent px-3 py-2"
          placeholder="имя (опц.)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
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
          placeholder="пароль (мин. 8)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        {error && <div className="text-sm text-red-400">{error}</div>}
        <button className="w-full rounded-md bg-accent px-3 py-2 font-medium text-white">
          Зарегистрироваться
        </button>
      </form>
    </main>
  );
}
