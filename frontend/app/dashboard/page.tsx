"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Project = {
  id: string;
  name: string;
  status: string;
  current_phase: number;
  domain: string | null;
};

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const router = useRouter();

  async function load() {
    try {
      const { data } = await api.get<Project[]>("/api/projects");
      setProjects(data);
    } catch {
      router.push("/login");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const { data } = await api.post<Project>("/api/projects", { name });
    setName("");
    router.push(`/projects/${data.id}`);
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Мои проекты</h1>
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

      <form onSubmit={create} className="mt-6 flex gap-2">
        <input
          className="flex-1 rounded-md border border-gray-700 bg-transparent px-3 py-2"
          placeholder="название нового проекта"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="rounded-md bg-accent px-4 py-2 text-white">Создать</button>
      </form>

      <div className="mt-8 space-y-2">
        {projects.length === 0 && (
          <div className="text-gray-500">Пока нет проектов — создайте первый.</div>
        )}
        {projects.map((p) => (
          <a
            key={p.id}
            href={`/projects/${p.id}`}
            className="block rounded-lg border border-gray-800 p-4 hover:border-accent"
          >
            <div className="flex items-center justify-between">
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-gray-500">
                фаза {p.current_phase} · {p.status}
              </div>
            </div>
            {p.domain && <div className="mt-1 text-xs text-gray-500">{p.domain}</div>}
          </a>
        ))}
      </div>
    </main>
  );
}
