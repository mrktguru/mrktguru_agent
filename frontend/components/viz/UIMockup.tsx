"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface UIMockupProps {
  spec: any;
  projectId: string;
  projectName?: string;
  onDeploy?: () => void;
}

export function UIMockup({ spec, projectId, projectName, onDeploy }: UIMockupProps) {
  const [loading, setLoading] = useState(false);
  const [html, setHtml] = useState<string | null>(spec?.mockup?.html ?? null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post(`/api/projects/${projectId}/mockup`);
      setHtml(data.html);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Ошибка генерации");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-300">Предпросмотр MVP</span>
          {html && !loading && (
            <button
              onClick={generate}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              ↻ Обновить
            </button>
          )}
        </div>
        {onDeploy && (
          <button
            onClick={onDeploy}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95"
            style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
          >
            <span>🚀</span>
            Выглядит хорошо — задеплоить
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div
          className="flex-1 flex flex-col items-center justify-center gap-5 rounded-2xl"
          style={{ border: "1px solid rgba(99,102,241,0.2)", background: "#0d0f17" }}
        >
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
            <div
              className="absolute inset-2 rounded-full border-2 border-purple-500 border-b-transparent animate-spin"
              style={{ animationDirection: "reverse", animationDuration: "0.8s" }}
            />
          </div>
          <div className="text-center">
            <div className="text-sm font-medium text-gray-300">Генерирую UX/UI макет…</div>
            <div className="text-xs text-gray-500 mt-1">
              Claude изучает спецификацию и рисует ваш продукт
            </div>
          </div>
        </div>
      ) : html ? (
        <div
          className="flex-1 rounded-2xl overflow-hidden"
          style={{ border: "1px solid rgba(99,102,241,0.25)" }}
        >
          <iframe
            srcDoc={html}
            sandbox="allow-scripts"
            className="w-full h-full"
            title="MVP Preview"
          />
        </div>
      ) : (
        <div
          className="flex-1 flex flex-col items-center justify-center gap-6 rounded-2xl"
          style={{ border: "1px dashed rgba(99,102,241,0.3)", background: "#0d0f17" }}
        >
          <div className="flex flex-col items-center gap-2 text-center max-w-sm">
            <span className="text-5xl">🎨</span>
            <div className="text-base font-semibold text-gray-200 mt-2">
              Интерактивный макет продукта
            </div>
            <div className="text-sm text-gray-500">
              Claude изучит спецификацию и нарисует полноценный UX/UI прототип с
              рабочими кнопками и навигацией между экранами
            </div>
          </div>
          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2 max-w-sm text-center">
              {error}
            </div>
          )}
          <button
            onClick={generate}
            className="flex items-center gap-2.5 px-6 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95"
            style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
          >
            <span>✨</span>
            Сгенерировать предпросмотр
          </button>
          <div className="text-[11px] text-gray-600">~20–30 секунд</div>
        </div>
      )}
    </div>
  );
}

