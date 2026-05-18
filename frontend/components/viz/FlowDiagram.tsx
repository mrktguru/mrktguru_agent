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

interface Step {
  id: string;
  label: string;
  next?: string[];
}

function readSteps(spec: any, key: "user_flow" | "admin_flow"): Step[] {
  const workflow = (spec && spec.workflow) || {};
  const arr = workflow[key];
  if (!Array.isArray(arr)) return [];
  return arr
    .map((s: any, i: number) => {
      if (typeof s === "string") {
        const id = `${key}-${i}`;
        return { id, label: s, next: i + 1 < arr.length ? [`${key}-${i + 1}`] : [] };
      }
      const id = s?.id ?? `${key}-${i}`;
      const label = s?.label ?? s?.title ?? `Шаг ${i + 1}`;
      const next = Array.isArray(s?.next) ? s.next : i + 1 < arr.length ? [`${key}-${i + 1}`] : [];
      return { id, label, next };
    })
    .filter((s) => !!s.label);
}

interface Props {
  spec: any;
  flow?: "user_flow" | "admin_flow";
  title?: string;
}

export function FlowDiagram({ spec, flow = "user_flow", title = "Пользовательский флоу" }: Props) {
  const { nodes, edges } = useMemo(() => {
    const steps = readSteps(spec, flow);
    const nodes: Node[] = steps.map((s, i) => ({
      id: s.id,
      data: { label: s.label },
      position: { x: 60 + (i % 3) * 200, y: 40 + Math.floor(i / 3) * 110 },
      style: {
        background: "#0f172a",
        color: "#e2e8f0",
        border: "1px solid #6366f1",
        borderRadius: 8,
        fontSize: 12,
        width: 170,
        padding: 8,
      },
    }));
    const edges: Edge[] = [];
    for (const s of steps) {
      for (const target of s.next ?? []) {
        edges.push({
          id: `${s.id}->${target}`,
          source: s.id,
          target,
          markerEnd: { type: MarkerType.ArrowClosed, color: "#6366f1" },
          style: { stroke: "#6366f1" },
        });
      }
    }
    return { nodes, edges };
  }, [spec, flow]);

  if (nodes.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 p-4 text-xs text-gray-500">
        {title} появится, как только агент опишет шаги.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 p-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">{title}</div>
      <div style={{ height: 280 }}>
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
