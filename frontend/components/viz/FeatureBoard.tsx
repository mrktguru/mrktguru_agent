"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type Column = "mvp" | "post_mvp" | "future";

type Feature = {
  id: string;
  title: string;
  source?: "user" | "ml_pattern";
  ml_frequency?: number;
  column: Column;
};

const COLUMNS: { key: Column; label: string }[] = [
  { key: "mvp", label: "MVP" },
  { key: "post_mvp", label: "После MVP" },
  { key: "future", label: "Идеи" },
];

function normalize(spec: any): Feature[] {
  const product = (spec && spec.product) || {};
  const features = product.features || {};
  const buckets: [string, Column][] = [
    ["mvp", "mvp"],
    ["post_mvp", "post_mvp"],
    ["future", "future"],
    ["ideas", "future"],
  ];
  const out: Feature[] = [];
  for (const [bucket, column] of buckets) {
    const arr = features[bucket];
    if (!Array.isArray(arr)) continue;
    arr.forEach((f: any, i: number) => {
      const title = typeof f === "string" ? f : f?.title;
      if (!title) return;
      out.push({
        id: `${bucket}-${i}-${title}`,
        title,
        source: typeof f === "object" ? f?.source : "user",
        ml_frequency: typeof f === "object" ? f?.ml_frequency : undefined,
        column,
      });
    });
  }
  return out;
}

function toProductPatch(features: Feature[], baseSpec: any) {
  const baseProduct = (baseSpec && baseSpec.product) || {};
  const next: Record<Column, any[]> = { mvp: [], post_mvp: [], future: [] };
  for (const f of features) {
    next[f.column].push({
      title: f.title,
      source: f.source ?? "user",
      ml_frequency: f.ml_frequency,
    });
  }
  return {
    ...baseProduct,
    features: { ...(baseProduct.features || {}), ...next },
  };
}

interface Props {
  spec: any;
  projectId: string;
  onSpecChanged?: (spec: any) => void;
}

export function FeatureBoard({ spec, projectId, onSpecChanged }: Props) {
  const initial = useMemo(() => normalize(spec), [spec]);
  const [features, setFeatures] = useState<Feature[]>(initial);
  const [dragging, setDragging] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setFeatures(normalize(spec));
  }, [spec]);

  async function persist(next: Feature[]) {
    setSaving(true);
    try {
      const product = toProductPatch(next, spec);
      const { data } = await api.patch(`/api/projects/${projectId}/spec`, { product });
      onSpecChanged?.(data.spec);
    } catch {
      setFeatures(normalize(spec));
    } finally {
      setSaving(false);
    }
  }

  function move(id: string, target: Column) {
    setFeatures((prev) => {
      const next = prev.map((f) => (f.id === id ? { ...f, column: target } : f));
      persist(next);
      return next;
    });
  }

  if (features.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 p-4 text-xs text-gray-500">
        Фичи появятся, когда агент сформирует продуктовую часть спецификации.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 p-3">
      <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-wide text-gray-500">
        <span>Фичи</span>
        {saving && <span className="normal-case text-indigo-400">сохраняю…</span>}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {COLUMNS.map((col) => {
          const items = features.filter((f) => f.column === col.key);
          return (
            <div
              key={col.key}
              onDragOver={(e) => {
                if (dragging) e.preventDefault();
              }}
              onDrop={(e) => {
                e.preventDefault();
                if (dragging) {
                  move(dragging, col.key);
                  setDragging(null);
                }
              }}
              className="rounded-lg bg-gray-900/40 p-2"
            >
              <div className="mb-2 text-[10px] uppercase tracking-wider text-gray-500">
                {col.label} · {items.length}
              </div>
              <div className="space-y-1.5">
                {items.length === 0 && <div className="text-xs text-gray-600">— перетащите —</div>}
                {items.map((f) => (
                  <div
                    key={f.id}
                    draggable
                    onDragStart={() => setDragging(f.id)}
                    onDragEnd={() => setDragging(null)}
                    className="cursor-grab rounded-md border border-gray-800 bg-gray-900/60 p-2 text-xs active:cursor-grabbing"
                  >
                    <div className="text-gray-200">{f.title}</div>
                    {f.source === "ml_pattern" && (
                      <div className="mt-1 text-[10px] text-indigo-400">
                        💡 ML
                        {f.ml_frequency != null ? ` · ${Math.round(f.ml_frequency * 100)}%` : ""}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
