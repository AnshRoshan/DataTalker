import type { Edge, Node } from '@xyflow/react';
import type { SchemaGraphResponse } from '../types';

const NODE_W = 190;
const NODE_H = 58;
const LAYER_GAP = 120;
const ROW_GAP = 80;

/**
 * Layered layout: x from the longest path over FK edges (source references
 * target), y stacked within each layer. Isolated tables fall into a grid
 * below the layered region so they never overlap the graph.
 */
export function computeLayout(graph: SchemaGraphResponse): {
  nodes: Node[];
  edges: Edge[];
} {
  const ids = graph.nodes.map(n => String(n.id));
  const idSet = new Set(ids);
  const edges = graph.edges.filter(
    e => idSet.has(String(e.source)) && idSet.has(String(e.target)),
  );

  const layer = new Map<string, number>();
  // Longest-path relaxation; bounded passes make cycles harmless.
  for (let pass = 0; pass < Math.min(ids.length, 64); pass++) {
    let changed = false;
    for (const e of edges) {
      const s = String(e.source);
      const t = String(e.target);
      const next = (layer.get(s) ?? 0) + 1;
      if (next > (layer.get(t) ?? 0) && next < ids.length) {
        layer.set(t, next);
        changed = true;
      }
    }
    if (!changed) break;
  }

  const connected = new Set<string>();
  for (const e of edges) {
    connected.add(String(e.source));
    connected.add(String(e.target));
  }

  const layered = ids.filter(id => connected.has(id));
  const isolated = ids.filter(id => !connected.has(id));

  const byLayer = new Map<number, string[]>();
  for (const id of layered) {
    const l = layer.get(id) ?? 0;
    const arr = byLayer.get(l) ?? [];
    arr.push(id);
    byLayer.set(l, arr);
  }

  const positionById = new Map<string, { x: number; y: number }>();
  let maxLayerHeight = 0;
  for (const [l, members] of byLayer) {
    members.forEach((id, i) => {
      positionById.set(id, { x: l * (NODE_W + LAYER_GAP), y: i * (NODE_H + ROW_GAP) });
    });
    maxLayerHeight = Math.max(maxLayerHeight, members.length * (NODE_H + ROW_GAP));
  }

  // Isolated tables: grid below the layered area.
  const perRow = Math.max(1, Math.floor(900 / (NODE_W + LAYER_GAP)));
  isolated.forEach((id, i) => {
    positionById.set(id, {
      x: (i % perRow) * (NODE_W + LAYER_GAP),
      y: maxLayerHeight + ROW_GAP * 2 + Math.floor(i / perRow) * (NODE_H + ROW_GAP),
    });
  });

  const nodeById = new Map(graph.nodes.map(n => [String(n.id), n]));
  const flowNodes: Node[] = ids.map(id => {
    const g = nodeById.get(id)!;
    return {
      id,
      type: 'tableNode',
      position: positionById.get(id) ?? { x: 0, y: 0 },
      data: { name: g.name, columnCount: g.columns?.length ?? 0 },
    };
  });

  const flowEdges: Edge[] = edges.map((e, i) => ({
    id: `e-${i}`,
    source: String(e.source),
    target: String(e.target),
    label: e.label || undefined,
    animated: false,
    style: {
      stroke: e.inferred ? '#47556966' : '#64748b',
      strokeWidth: 1,
      strokeDasharray: e.inferred ? '5 4' : undefined,
    },
    labelStyle: { fill: '#94a3b8', fontSize: 10, fontFamily: 'Fira Code, monospace' },
    labelBgStyle: { fill: '#272F42', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 2,
  }));

  return { nodes: flowNodes, edges: flowEdges };
}
