"use client";

import { useMemo } from "react";

type Feature = {
  id: string;
  title: string;
  source?: "user" | "ml_pattern";
  ml_frequency?: number;
  column: "mvp" | "post_mvp" | "future";
};

const COLUMNS: { key: Feature["column"]; label: string }[] = [
  { key: "mvp", label: "MVP" },
  { key: "post_mvp", label: "После MVP" },
  { key: "future", label: "Идеи" },
];

function normalize(spec: any): Feature[] {
  const product = (spec && spec.product) || {};
  const features = product.features || {};
  const buckets: [string, Feature["column"]][] = [
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

export function FeatureBoard({ spec }: { spec: any }) {
  const features = useMemo(() => normalize(spec), [spec]);

  if (features.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 p-4 text-xs text-gray-500">
        Фичи появятся, когда агент сформирует продуктовую часть спецификации.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 p-3">
      <div className="mb-3 text-xs uppercase tracking-wide text-gray-500">Фичи</div>
      <div className="grid grid-cols-3 gap-2">
        {COLUMNS.map((col) => {
          const items = features.filter((f) => f.column === col.key);
          return (
            <div key={col.key} className="rounded-lg bg-gray-900/40 p-2">
              <div className="mb-2 text-[10px] uppercase tracking-wider text-gray-500">
                {col.label} · {items.length}
              </div>
              <div className="space-y-1.5">
                {items.length === 0 && (
                  <div className="text-xs text-gray-600">—</div>
                )}
                {items.map((f) => (
                  <div
                    key={f.id}
                    className="rounded-md border border-gray-800 bg-gray-900/60 p-2 text-xs"
                  >
                    <div className="text-gray-200">{f.title}</div>
                    {f.source === "ml_pattern" && (
                      <div className="mt-1 text-[10px] text-indigo-400">
                        💡 ML
                        {f.ml_frequency != null
                          ? ` · ${Math.round(f.ml_frequency * 100)}%`
                          : ""}
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
