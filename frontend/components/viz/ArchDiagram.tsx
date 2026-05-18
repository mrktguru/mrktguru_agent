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

function inferKind(label: string): string {
  const l = label.toLowerCase();
  if (/nginx|reverse.proxy|cdn|proxy/.test(l)) return "nginx";
  if (/front|next|react|vue|ui|страниц|лендинг|landing|browser/.test(l)) return "frontend";
  if (/api|back|fastapi|django|flask|express|server|бэк/.test(l)) return "api";
  if (/postgres|mysql|mongo|sqlite|база|db|database/.test(l)) return "db";
  if (/redis|cache|memcache|кэш/.test(l)) return "cache";
  if (/worker|celery|queue|beat|воркер/.test(l)) return "worker";
  if (/admin|панель|управл/.test(l)) return "api";
  if (/seo|блог|blog|контент/.test(l)) return "frontend";
  return "api";
}

function autoConnections(comps: Component[]): Component[] {
  const kinds = comps.map((c) => c.kind ?? "api");
  return comps.map((c, i) => {
    if ((c.connects_to ?? []).length > 0) return c;
    const targets: string[] = [];
    const k = c.kind ?? "api";
    if (k === "nginx") {
      comps.forEach((t) => { if (t.kind === "frontend" || t.kind === "api") targets.push(t.id); });
    } else if (k === "frontend") {
      comps.forEach((t) => { if (t.kind === "api") targets.push(t.id); });
    } else if (k === "api") {
      comps.forEach((t) => { if (t.kind === "db" || t.kind === "cache") targets.push(t.id); });
    } else if (k === "worker") {
      comps.forEach((t) => { if (t.kind === "db" || t.kind === "cache") targets.push(t.id); });
    }
    return { ...c, connects_to: targets.filter((id) => id !== c.id) };
  });
}

function readComponents(spec: any): Component[] {
  // Try spec.architecture.components first, then spec.workflow.components
  const arr =
    (spec?.architecture?.components ??
      spec?.workflow?.components ??
      []) as any[];

  if (!Array.isArray(arr) || arr.length === 0) return [];

  const mapped: Component[] = arr.map((c: any, i: number) => {
    if (typeof c === "string") {
      return {
        id: `c${i}`,
        label: c,
        kind: inferKind(c),
        connects_to: [],
      };
    }
    return {
      id: c?.id ?? c?.name ?? `c${i}`,
      label: c?.label ?? c?.name ?? `Компонент ${i + 1}`,
      port: c?.port,
      kind: c?.kind ?? c?.type ?? inferKind(c?.label ?? c?.name ?? ""),
      connects_to: Array.isArray(c?.connects_to) ? c.connects_to : [],
    };
  });

  // Also parse stack into components if we got nothing useful
  const final = mapped.filter((c) => !!c.label);
  return autoConnections(final);
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
