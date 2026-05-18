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


interface FlowStep {
  action?: string;
  label?: string;
  step?: string;
}

function stepLabel(s: any, i: number): string {
  if (typeof s === "string") return s;
  return s?.action ?? s?.label ?? s?.step ?? `Шаг ${i + 1}`;
}

type ScreenType = "catalog" | "form" | "result" | "info" | "default";

function inferType(label: string): ScreenType {
  const l = label.toLowerCase();
  if (/список|каталог|главн|home|main|выбирает|переходит на главн/.test(l)) return "catalog";
  if (/ввод|форма|заполня|вводит|форм|поля|input|выбирает тип/.test(l)) return "form";
  if (/результат|готов|скачива|получает|download|complete|скачать|генер|показывает/.test(l)) return "result";
  if (/информ|about|faq|seo|блог|статья|читает/.test(l)) return "info";
  return "default";
}

function appColor(type: string[]): { bg: string; accent: string; button: string } {
  const t = type?.join("") ?? "";
  if (t.includes("telegram")) return { bg: "#0088cc", accent: "#33aaff", button: "#0088cc" };
  if (t.includes("ecommerce") || t.includes("shop")) return { bg: "#f97316", accent: "#fb923c", button: "#f97316" };
  return { bg: "#6366f1", accent: "#818cf8", button: "#6366f1" };
}

// -- Screen renderers --

function CatalogScreen({ features, appName, color }: { features: Feature[]; appName: string; color: any }) {
  const items = features.length > 0 ? features : [
    { title: "Пункт 1", description: "Описание первого пункта" },
    { title: "Пункт 2", description: "Описание второго пункта" },
    { title: "Пункт 3", description: "Описание третьего пункта" },
  ];
  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-2 gap-3 flex-1 overflow-auto pr-1">
        {items.map((f, i) => (
          <div
            key={i}
            className="rounded-xl p-3 cursor-pointer transition-all hover:scale-[1.02] active:scale-95 select-none"
            style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)" }}
          >
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2 text-lg"
              style={{ background: color.bg + "22" }}>
              {["📦", "⚡", "🔧", "🎯", "📊", "🌟"][i % 6]}
            </div>
            <div className="text-xs font-semibold text-gray-200 leading-tight">{f.title}</div>
            {f.description && (
              <div className="text-[10px] text-gray-500 mt-1 leading-tight line-clamp-2">{f.description}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function FormScreen({ features, color }: { features: Feature[]; color: any }) {
  const [vals, setVals] = useState<Record<number, string>>({});
  const fields = features.length > 0
    ? features.map((f) => f.title)
    : ["Поле 1", "Поле 2", "Поле 3"];
  return (
    <div className="flex flex-col gap-3">
      {fields.slice(0, 4).map((label, i) => (
        <div key={i} className="flex flex-col gap-1">
          <label className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">{label}</label>
          <input
            value={vals[i] ?? ""}
            onChange={(e) => setVals((v) => ({ ...v, [i]: e.target.value }))}
            placeholder={`Введите ${label.toLowerCase()}…`}
            className="w-full rounded-lg px-3 py-2 text-xs text-gray-200 outline-none"
            style={{ background: "#1e2030", border: "1px solid rgba(99,102,241,0.3)" }}
          />
        </div>
      ))}
      <button
        className="mt-2 w-full rounded-lg py-2.5 text-xs font-semibold text-white transition-opacity hover:opacity-90"
        style={{ background: color.bg }}
      >
        Сгенерировать →
      </button>
    </div>
  );
}

function ResultScreen({ appName, color }: { appName: string; color: any }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="w-full rounded-xl p-4 flex flex-col items-center gap-3"
        style={{ background: "#1e2030", border: "1px solid rgba(99,102,241,0.3)" }}>
        {/* fake barcode / QR placeholder */}
        <div className="rounded-lg overflow-hidden" style={{ width: 140, height: 80, background: "#fff" }}>
          <div className="w-full h-full flex items-center justify-center">
            <svg viewBox="0 0 140 80" width="140" height="80">
              {[...Array(14)].map((_, i) => (
                <rect key={i} x={10 + i * 9} y={10} width={[5, 3, 7, 2, 6, 4, 5, 3, 7, 2, 6, 4, 5, 3][i]} height={50} fill="#111" />
              ))}
              <text x="70" y="72" textAnchor="middle" fontSize="7" fill="#111">8901234567890</text>
            </svg>
          </div>
        </div>
        <div className="text-xs font-semibold text-green-400 flex items-center gap-1.5">
          <span>✓</span> Готово!
        </div>
      </div>
      <div className="w-full flex gap-2">
        <button
          className="flex-1 py-2 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90"
          style={{ background: color.bg }}
        >
          PNG
        </button>
        <button
          className="flex-1 py-2 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90"
          style={{ background: color.bg }}
        >
          SVG
        </button>
        <button
          className="flex-1 py-2 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90"
          style={{ background: color.bg }}
        >
          PDF
        </button>
      </div>
      <button
        onClick={() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="w-full py-2 rounded-lg text-xs font-medium transition-all"
        style={{ background: copied ? "#22c55e22" : "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: copied ? "#4ade80" : "#94a3b8" }}
      >
        {copied ? "Скопировано!" : "Копировать ссылку"}
      </button>
    </div>
  );
}

function InfoScreen({ features, color }: { features: Feature[]; color: any }) {
  const items = features.length > 0 ? features : [
    { title: "О сервисе", description: "Подробная информация о возможностях платформы." },
    { title: "Как использовать", description: "Пошаговые инструкции для начала работы." },
  ];
  return (
    <div className="flex flex-col gap-3">
      {items.slice(0, 3).map((f, i) => (
        <div key={i} className="rounded-xl p-3" style={{ background: "#1e2030", border: "1px solid rgba(99,102,241,0.2)" }}>
          <div className="text-xs font-semibold text-gray-200 mb-1">{f.title}</div>
          <div className="text-[11px] text-gray-400 leading-relaxed">{f.description ?? "—"}</div>
        </div>
      ))}
    </div>
  );
}

function DefaultScreen({ features, color }: { features: Feature[]; color: any }) {
  const items = features.length > 0 ? features : [
    { title: "Начать работу", description: "" },
    { title: "Обзор возможностей", description: "" },
  ];
  return (
    <div className="flex flex-col gap-3">
      {items.slice(0, 4).map((f, i) => (
        <button
          key={i}
          className="w-full text-left rounded-xl p-3 transition-all hover:scale-[1.01] active:scale-95"
          style={{ background: i === 0 ? color.bg : "#1e2030", border: "1px solid rgba(99,102,241,0.3)" }}
        >
          <div className="text-xs font-semibold" style={{ color: i === 0 ? "#fff" : "#e2e8f0" }}>{f.title}</div>
          {f.description && <div className="text-[10px] mt-0.5 opacity-70">{f.description}</div>}
        </button>
      ))}
    </div>
  );
}

interface UIMockupProps {
  spec: any;
  projectName?: string;
  onDeploy?: () => void;
}

export function UIMockup({ spec, projectName, onDeploy }: UIMockupProps) {
  const [screen, setScreen] = useState(0);

  const userFlow: any[] = Array.isArray(spec?.workflow?.user_flow) ? spec.workflow.user_flow : [];
  const mvp: Feature[] = (spec?.product?.features?.mvp ?? []).map((f: any) =>
    typeof f === "string" ? { title: f } : { title: f.title, description: f.description }
  );
  const appName = spec?.meta?.name ?? projectName ?? "Приложение";
  const types: string[] = spec?.idea?.type ?? [];
  const color = appColor(types);

  const steps = userFlow.length > 0
    ? userFlow.map((s, i) => ({ label: stepLabel(s, i), type: inferType(stepLabel(s, i)) }))
    : [
        { label: "Главная страница", type: "catalog" as ScreenType },
        { label: "Ввод данных", type: "form" as ScreenType },
        { label: "Результат", type: "result" as ScreenType },
      ];

  const total = steps.length;
  const current = steps[Math.min(screen, total - 1)];
  // distribute features across screens
  const perScreen = Math.max(1, Math.ceil(mvp.length / total));
  const screenFeatures = mvp.slice(screen * perScreen, (screen + 1) * perScreen);

  function renderScreen() {
    switch (current.type) {
      case "catalog":
        return <CatalogScreen features={screenFeatures.length ? screenFeatures : mvp.slice(0, 6)} appName={appName} color={color} />;
      case "form":
        return <FormScreen features={screenFeatures} color={color} />;
      case "result":
        return <ResultScreen appName={appName} color={color} />;
      case "info":
        return <InfoScreen features={screenFeatures} color={color} />;
      default:
        return <DefaultScreen features={screenFeatures} color={color} />;
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar with deploy button */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div className="text-sm font-semibold text-gray-300">
          Предпросмотр MVP
          <span className="ml-2 text-xs font-normal text-gray-500">
            {steps.length} экранов
          </span>
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

      {/* Browser + screen area */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Screen list sidebar */}
        <div className="flex flex-col gap-1.5 w-48 shrink-0 overflow-y-auto">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1 px-1">Экраны</div>
          {steps.map((s, i) => (
            <button
              key={i}
              onClick={() => setScreen(i)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-all hover:bg-gray-800"
              style={{
                background: i === screen ? "rgba(99,102,241,0.18)" : "transparent",
                border: i === screen ? "1px solid rgba(99,102,241,0.4)" : "1px solid transparent",
                color: i === screen ? "#c7d2fe" : "#94a3b8",
              }}
            >
              <span className="shrink-0 w-5 h-5 rounded flex items-center justify-center text-[10px]"
                style={{ background: i === screen ? color.bg : "#1e293b" }}>
                {i + 1}
              </span>
              <span className="leading-tight line-clamp-2">{s.label}</span>
            </button>
          ))}
        </div>

        {/* Browser frame */}
        <div className="flex-1 min-w-0 flex flex-col rounded-2xl overflow-hidden"
          style={{ border: "1px solid rgba(99,102,241,0.25)", background: "#0d0f17" }}>
          {/* Browser chrome */}
          <div className="flex items-center gap-2 px-3 py-2 shrink-0"
            style={{ background: "#171b2d", borderBottom: "1px solid rgba(99,102,241,0.15)" }}>
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500 opacity-70" />
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-500 opacity-70" />
              <div className="w-2.5 h-2.5 rounded-full bg-green-500 opacity-70" />
            </div>
            <div className="flex-1 mx-2 rounded px-3 py-1 text-[10px] text-gray-400"
              style={{ background: "#0d0f17", border: "1px solid rgba(99,102,241,0.2)" }}>
              https://{appName.toLowerCase().replace(/\s+/g, "-")}.ru
            </div>
          </div>

          {/* App chrome */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* App header */}
            <div className="flex items-center justify-between px-4 py-3 shrink-0"
              style={{ background: color.bg + "dd", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-white bg-opacity-20 flex items-center justify-center text-xs">
                  {appName[0]?.toUpperCase() ?? "A"}
                </div>
                <span className="text-sm font-semibold text-white">{appName}</span>
              </div>
              <div className="flex gap-3">
                {mvp.slice(0, 3).map((f, i) => (
                  <span key={i} className="text-xs text-white opacity-80 cursor-pointer hover:opacity-100">
                    {f.title.split(" ").slice(0, 2).join(" ")}
                  </span>
                ))}
              </div>
            </div>

            {/* Screen content */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="text-sm font-semibold text-gray-200 mb-3">{current.label}</div>
              {renderScreen()}
            </div>

            {/* Pagination nav */}
            <div className="flex items-center justify-between px-4 py-2.5 shrink-0"
              style={{ borderTop: "1px solid rgba(99,102,241,0.15)", background: "#171b2d" }}>
              <button
                onClick={() => setScreen((s) => Math.max(0, s - 1))}
                disabled={screen === 0}
                className="text-xs px-3 py-1.5 rounded-lg transition-all disabled:opacity-30"
                style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}
              >
                ← Назад
              </button>
              <span className="text-[10px] text-gray-500">{screen + 1} / {total}</span>
              <button
                onClick={() => setScreen((s) => Math.min(total - 1, s + 1))}
                disabled={screen === total - 1}
                className="text-xs px-3 py-1.5 rounded-lg transition-all disabled:opacity-30"
                style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc" }}
              >
                Далее →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
