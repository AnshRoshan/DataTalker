import React, { useCallback, useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Node,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { SchemaGraphResponse } from '../../types';
import { computeLayout } from '../../lib/graphLayout';

const NODE_W = 190;

type TableNodeData = { name: string; columnCount: number };

const TableNode: React.FC<NodeProps> = ({ data, selected }) => {
  const d = data as unknown as TableNodeData;
  return (
    <div
      className={`rounded-card border bg-primary px-3 py-2 shadow-tinted-sm transition-tool ${
        selected ? 'border-accent' : 'border-border/60'
      }`}
      style={{ width: NODE_W }}
    >
      <p className="truncate font-display text-[12px] font-medium text-fg" title={d.name}>
        {d.name}
      </p>
      <p className="font-display text-[10px] text-fg/40">
        {d.columnCount} {d.columnCount === 1 ? 'column' : 'columns'}
      </p>
    </div>
  );
};

const nodeTypes: NodeTypes = { tableNode: TableNode };

interface SchemaGraphProps {
  graph: SchemaGraphResponse;
  selectedTable: string | null;
  onSelectTable: (name: string) => void;
}

/** Interactive FK graph over the /schema/graph/ response. */
const SchemaGraph: React.FC<SchemaGraphProps> = ({ graph, selectedTable, onSelectTable }) => {
  const layout = useMemo(() => computeLayout(graph), [graph]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const g = graph.nodes.find(n => String(n.id) === node.id);
      if (g) onSelectTable(g.name);
    },
    [graph.nodes, onSelectTable],
  );

  // Keep the selected table highlighted in the graph.
  const nodes = useMemo(
    () =>
      layout.nodes.map(n => {
        const g = graph.nodes.find(gn => String(gn.id) === n.id);
        return { ...n, selected: g?.name === selectedTable };
      }),
    [layout.nodes, graph.nodes, selectedTable],
  );

  return (
    <div className="h-[420px] overflow-hidden rounded-card border border-border/40 bg-bg" data-testid="schema-graph">
      <ReactFlow
        nodes={nodes}
        edges={layout.edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={1.75}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#272F42" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export default SchemaGraph;
