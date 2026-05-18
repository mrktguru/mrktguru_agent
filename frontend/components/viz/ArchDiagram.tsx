"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  Node,
} from "reactflow";
import "reactflow/dist/style.css";

interface Component {
  id: string;
  label: string;
  port?: number | string;
  kind?: string;
  connects_to?: string[];
}

function readComponents(spec: any): Component[] {
  const arch = (spec && spec.architecture) || {};
  const arr = arch.components;
  if (!Array.isArray(arr)) return [];
  return arr
    .map((c: any, i: number) => {
      if (typeof c === "string") {
        return { id: `c${i}`, label: c };
      }
      return {
        id: c?.id ?? c?.name ?? `c${i}`,
        label: c?.label ?? c?.name ?? `Компонент ${i + 1}`,
        port: c?.port,
        kind: c?.kind ?? c?.type,
        connects_to: Array.isArray(c?.connects_to) ? c.connects_to : [],
      };
    })
    .filter((c) => !!c.label);
}

const KIND_COLOR: Record<string, string> = {
  api: "#22d3ee",
  frontend: "#a855f7",
  db: "#f59e0b",
  cache: "#f97316",
  worker: "#10b981",
  nginx: "#94a3b8",
};

export function ArchDiagram({ spec }: { spec: any }) {
  const { nodes, edges } = useMemo(() => {
    const comps = readComponents(spec);
    const cols = 3;
    const nodes: Node[] = comps.map((c, i) => {
      const color = (c.kind && KIND_COLOR[c.kind]) || "#6366f1";
      return {
        id: c.id,
        data: {
          label: c.port ? `${c.label}\n:${c.port}` : c.label,
        },
        position: { x: 60 + (i % cols) * 200, y: 40 + Math.floor(i / cols) * 110 },
        style: {
          background: "#0f172a",
          color: "#e2e8f0",
          border: `1.5px solid ${color}`,
          borderRadius: 10,
          fontSize: 12,
          width: 170,
          whiteSpace: "pre-line",
          padding: 8,
        },
      };
    });
    const ids = new Set(comps.map((c) => c.id));
    const edges: Edge[] = [];
    for (const c of comps) {
      for (const t of c.connects_to ?? []) {
        if (!ids.has(t)) continue;
        edges.push({
          id: `${c.id}->${t}`,
          source: c.id,
          target: t,
          markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
          style: { stroke: "#94a3b8" },
        });
      }
    }
    return { nodes, edges };
  }, [spec]);

  if (nodes.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 p-4 text-xs text-gray-500">
        Схема архитектуры появится, когда агент опишет компоненты.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 p-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">Архитектура</div>
      <div style={{ height: 320 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e293b" gap={16} />
          <Controls showInteractive={false} className="!bg-gray-900 !text-gray-200" />
        </ReactFlow>
      </div>
    </div>
  );
}
