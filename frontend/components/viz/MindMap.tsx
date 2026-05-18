"use client";

import { useMemo } from "react";

type Node = {
  id: string;
  label: string;
  type: "problem" | "user" | "solution" | "pain" | "field";
  filled: boolean;
};

interface Props {
  spec: any;
}

const TYPE_COLOR: Record<Node["type"], string> = {
  problem: "#f97316",
  user: "#22d3ee",
  solution: "#a855f7",
  pain: "#f43f5e",
  field: "#64748b",
};

function buildNodes(spec: any): { center: string; nodes: Node[] } {
  const idea = (spec && spec.idea) || {};
  const center = idea.name || idea.title || "Идея";
  const candidates: [string, string, Node["type"]][] = [
    ["problem", "Проблема", "problem"],
    ["user", "Кто пользователь", "user"],
    ["solution", "Решение", "solution"],
    ["pain", "Боль", "pain"],
    ["audience", "Аудитория", "user"],
    ["value", "Ценность", "solution"],
    ["type", "Тип проекта", "field"],
  ];
  const nodes: Node[] = candidates.map(([key, label, type]) => {
    const val = idea[key];
    const filled = !!(typeof val === "string" ? val.trim() : val && (Array.isArray(val) ? val.length : true));
    return {
      id: key,
      label: filled ? `${label}: ${typeof val === "string" ? val : Array.isArray(val) ? val.join(", ") : "✓"}` : label,
      type,
      filled,
    };
  });
  return { center, nodes };
}

export function MindMap({ spec }: Props) {
  const { center, nodes } = useMemo(() => buildNodes(spec), [spec]);
  const radius = 140;
  const cx = 220;
  const cy = 170;

  return (
    <div className="rounded-xl border border-gray-800 p-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">Карта идеи</div>
      <svg viewBox="0 0 440 340" className="w-full" xmlns="http://www.w3.org/2000/svg">
        {nodes.map((n, i) => {
          const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
          const x = cx + Math.cos(angle) * radius;
          const y = cy + Math.sin(angle) * radius;
          const color = TYPE_COLOR[n.type];
          return (
            <g key={n.id}>
              <line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke={n.filled ? color : "#334155"}
                strokeOpacity={n.filled ? 0.5 : 0.25}
                strokeDasharray={n.filled ? undefined : "4 4"}
              />
              <g>
                <circle
                  cx={x}
                  cy={y}
                  r={n.filled ? 8 : 7}
                  fill={n.filled ? color : "#0f172a"}
                  stroke={color}
                  strokeWidth={2}
                  opacity={n.filled ? 1 : 0.6}
                >
                  {!n.filled && (
                    <animate
                      attributeName="r"
                      values="6;9;6"
                      dur="1.8s"
                      repeatCount="indefinite"
                    />
                  )}
                </circle>
                <text
                  x={x}
                  y={y + 22}
                  fontSize="11"
                  textAnchor="middle"
                  fill={n.filled ? "#e2e8f0" : "#64748b"}
                  style={{ maxWidth: 120 }}
                >
                  {n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label}
                </text>
              </g>
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r={36} fill="#1e293b" stroke="#6366f1" strokeWidth={2} />
        <text x={cx} y={cy + 4} fontSize="12" textAnchor="middle" fill="#f1f5f9">
          {center.length > 18 ? center.slice(0, 17) + "…" : center}
        </text>
      </svg>
    </div>
  );
}
