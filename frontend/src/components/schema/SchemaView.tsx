import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import type { ActiveDbRef, SchemaGraphResponse } from '../../types';
import { dbRefLabel } from '../../lib/format';
import { fetchSchemaGraph } from '../../lib/api';
import { Badge, Spinner, buttonGhost, buttonPrimary, inputClass } from '../ui';
import SchemaGraph from './SchemaGraph';

interface SchemaViewProps {
  apiUrl: string;
  apiKey: string;
  dbRef: ActiveDbRef | null;
}

/** Node threshold past which the graph only renders on demand. */
const GRAPH_RENDER_LIMIT = 40;

const FkBadges: React.FC<{ table: string; column: { name: string; primary_key?: boolean; foreign_keys?: { references_table?: string }[] } }> = ({ column }) => (
  <>
    {column.primary_key ? (
      <span className="rounded-md bg-accent/10 px-1 font-display text-[9px] uppercase text-accent">pk</span>
    ) : null}
    {column.foreign_keys?.map((fk, i) => (
      <span
        key={i}
        className="rounded-md border border-border/50 px-1 font-display text-[9px] uppercase text-fg/50"
        title={fk.references_table ? `References ${fk.references_table}` : 'Foreign key'}
      >
        fk{fk.references_table ? `: ${fk.references_table}` : ''}
      </span>
    ))}
  </>
);

/** Schema explorer for the active connection: table list, detail, FK graph. */
const SchemaView: React.FC<SchemaViewProps> = ({ apiUrl, apiKey, dbRef }) => {
  const [graph, setGraph] = useState<SchemaGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [graphVisible, setGraphVisible] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Track which ref the current graph belongs to; refetch when it changes.
  const loadedForRef = useRef<string | null>(null);

  const refKey = dbRef ? dbRefLabel(dbRef) : null;

  const load = useCallback(async () => {
    if (!dbRef) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSchemaGraph({ apiUrl, apiKey, dbRef, signal: controller.signal });
      setGraph(data);
      setGraphVisible(false);
      setSelected(data.nodes[0]?.name ?? null);
      loadedForRef.current = refKey;
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to load the schema.');
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [apiUrl, apiKey, dbRef, refKey]);

  useEffect(() => {
    // Reset when the active reference changes, then load.
    if (loadedForRef.current !== refKey) {
      setGraph(null);
      setSelected(null);
      setError(null);
    }
    if (dbRef) void load();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, apiKey, dbRef]);

  if (!dbRef) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4 text-center">
        <p className="text-[13px] text-fg/50">Attach a database to explore its schema.</p>
      </div>
    );
  }

  const tables = (graph?.nodes ?? []).filter(t =>
    t.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const selectedNode = graph?.nodes.find(n => n.name === selected) ?? null;
  const needsOnDemand = !!graph && (graph.truncated === true || graph.nodes.length > GRAPH_RENDER_LIMIT);
  const showGraph = !!graph && (graphVisible || !needsOnDemand);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Header */}
      <div className="flex shrink-0 items-center gap-3 border-b border-border/30 px-6 py-3">
        <h1 className="font-display text-[15px] font-semibold text-fg">Schema</h1>
        {graph ? (
          <>
            <Badge>{graph.dialect}</Badge>
            <span className="font-display text-[11px] text-fg/40">
              {graph.table_count} {graph.table_count === 1 ? 'table' : 'tables'}
              {graph.truncated ? ' (truncated at 200)' : ''}
            </span>
          </>
        ) : null}
        <span className="font-display text-[11px] text-fg/30">{refKey}</span>
        <span className="flex-1" />
        <button type="button" onClick={() => void load()} disabled={loading} className={buttonGhost}>
          {loading ? <Spinner /> : <RefreshCw size={13} />}
          Refresh
        </button>
      </div>

      {loading && !graph ? (
        <div className="flex flex-1 items-center justify-center">
          <Spinner className="h-5 w-5 text-fg/40" />
        </div>
      ) : error ? (
        <div role="alert" className="mx-6 mt-4 rounded-card border border-destructive/50 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
          {error}
        </div>
      ) : graph ? (
        <div className="flex min-h-0 flex-1 gap-4 px-6 py-4">
          {/* Left: searchable table list */}
          <aside className="flex w-60 shrink-0 flex-col">
            <div className="relative">
              <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg/30" aria-hidden />
              <input
                type="search"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Filter tables..."
                aria-label="Filter tables"
                className={`${inputClass} pl-7`}
              />
            </div>
            <ul className="mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto" aria-label="Tables">
              {tables.map(t => (
                <li key={String(t.id)}>
                  <button
                    type="button"
                    onClick={() => setSelected(t.name)}
                    aria-pressed={selected === t.name}
                    className={`flex w-full items-center justify-between rounded-input px-2.5 py-1.5 text-left text-[13px] transition-tool focus-visible:outline-2 focus-visible:outline-accent ${
                      selected === t.name
                        ? 'bg-surface text-fg'
                        : 'text-fg/60 hover:bg-surface-hi/50 hover:text-fg'
                    }`}
                  >
                    <span className="truncate font-display text-[12px]" title={t.name}>
                      {t.name}
                    </span>
                    <span className="ml-2 shrink-0 font-display text-[10px] text-fg/30">
                      {t.columns.length}
                    </span>
                  </button>
                </li>
              ))}
              {tables.length === 0 ? (
                <li className="px-2 py-3 text-[12px] text-fg/40">No tables match.</li>
              ) : null}
            </ul>
          </aside>

          {/* Right: selected table detail + relationship graph */}
          <div className="min-w-0 flex-1 overflow-y-auto">
            {selectedNode ? (
              <section aria-label="Table detail" className="rounded-card border border-border/40 p-4">
                <h2 className="font-display text-[13px] font-semibold text-fg">{selectedNode.name}</h2>
                <p className="mt-0.5 text-[11px] text-fg/40">
                  {selectedNode.columns.length} {selectedNode.columns.length === 1 ? 'column' : 'columns'}
                </p>
                <div className="mt-3 overflow-hidden rounded-card border border-border/30">
                  <table className="w-full border-collapse text-[12px]">
                    <thead>
                      <tr className="border-b border-border/30 bg-surface/60">
                        <th scope="col" className="px-3 py-1.5 text-left font-display text-[10px] uppercase tracking-wide text-fg/50">Column</th>
                        <th scope="col" className="px-3 py-1.5 text-left font-display text-[10px] uppercase tracking-wide text-fg/50">Type</th>
                        <th scope="col" className="px-3 py-1.5 text-left font-display text-[10px] uppercase tracking-wide text-fg/50">Keys</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedNode.columns.map(col => (
                        <tr key={col.name} className="border-b border-border/20 last:border-b-0">
                          <td className="px-3 py-1.5 font-display text-[12px] text-fg/85">{col.name}</td>
                          <td className="px-3 py-1.5 text-fg/50">{col.type ?? ''}</td>
                          <td className="px-3 py-1.5">
                            <span className="flex gap-1">
                              <FkBadges table={selectedNode.name} column={col} />
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}

            <section aria-label="Relationship graph" className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-[12px] text-fg/60">Relationships</h2>
                <p className="font-display text-[10px] text-fg/30">Dashed edges are inferred joins</p>
              </div>
              {showGraph ? (
                <SchemaGraph graph={graph} selectedTable={selected} onSelectTable={setSelected} />
              ) : (
                <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border/40 py-8 text-center">
                  <p className="text-[13px] text-fg/50">
                    This schema has {graph.nodes.length} tables
                    {graph.truncated ? ' (the server caps it at 200)' : ''}. Rendering the graph is
                    skipped by default at this size.
                  </p>
                  <button
                    type="button"
                    onClick={() => setGraphVisible(true)}
                    className={buttonPrimary}
                  >
                    Render graph anyway
                  </button>
                </div>
              )}
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default SchemaView;
