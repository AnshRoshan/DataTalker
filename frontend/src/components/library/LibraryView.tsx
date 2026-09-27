import React, { useCallback, useEffect, useState } from 'react';
import { Copy, Play, RefreshCw, Trash2 } from 'lucide-react';
import type { HistoryEntry, SavedQuery } from '../../types';
import { deleteSavedQuery, fetchHistory, fetchSavedQueries, getErrorMessage } from '../../lib/api';
import { relativeTime } from '../../lib/format';
import { Spinner, buttonGhost, panel } from '../ui';

interface LibraryViewProps {
  apiUrl: string;
  apiKey: string;
  /** Copy a statement into the SQL Lab (the parent owns the editor state). */
  onRun: (query: SavedQuery) => void;
}

/** Library: saved statements plus the audit trail of what has actually been asked. */
const LibraryView: React.FC<LibraryViewProps> = ({ apiUrl, apiKey, onRun }) => {
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [saved, trail] = await Promise.all([
        fetchSavedQueries(apiUrl, apiKey),
        fetchHistory(apiUrl, apiKey, 50),
      ]);
      setQueries(saved);
      setHistory(trail);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [apiUrl, apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = useCallback(
    async (id: string) => {
      try {
        await deleteSavedQuery(apiUrl, apiKey, id);
        setQueries(prev => prev.filter(q => q.id !== id));
      } catch (err) {
        setError(getErrorMessage(err));
      }
    },
    [apiUrl, apiKey],
  );

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <section>
          <div className="mb-3 flex items-center gap-2">
            <span className="label">saved queries</span>
            <span className="font-code text-[10px]" style={{ color: 'var(--color-faint)' }}>
              {queries.length}
            </span>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className={`${buttonGhost} ml-auto h-7 px-2 text-[11px]`}
            >
              {loading ? <Spinner /> : <RefreshCw className="size-3" />}
              Reload
            </button>
          </div>

          {error ? (
            <p className="mb-3 text-[12.5px]" style={{ color: 'var(--color-destructive)' }}>
              {error}
            </p>
          ) : null}

          {queries.length === 0 && !loading ? (
            <p className="text-[12.5px]" style={{ color: 'var(--color-faint)' }}>
              Nothing saved yet. Run a statement in the SQL lab and press Save.
            </p>
          ) : (
            <div className={`${panel} divide-hair overflow-hidden`}>
              {queries.map(q => (
                <div key={q.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setOpen(open === q.id ? null : q.id)}
                      className="min-w-0 flex-1 truncate text-left text-[13px] font-semibold"
                    >
                      {q.name}
                    </button>
                    {q.dialect ? <span className="tag">{q.dialect}</span> : null}
                    {q.source ? (
                      <span className="tag normal-case tracking-normal" style={{ color: 'var(--color-muted)' }}>
                        {q.source}
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onRun(q)}
                      className={buttonGhost}
                      title="Open in the SQL lab"
                      aria-label={`Run ${q.name}`}
                    >
                      <Play className="size-3.5" />
                      Run
                    </button>
                    <button
                      type="button"
                      onClick={() => void navigator.clipboard?.writeText(q.sql)}
                      className={`${buttonGhost} px-2`}
                      aria-label="Copy statement"
                      title="Copy statement"
                    >
                      <Copy className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void remove(q.id)}
                      className="btn btn-danger h-[34px] px-2"
                      aria-label={`Delete ${q.name}`}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                  <p className="mt-1 font-code text-[10.5px]" style={{ color: 'var(--color-faint)' }}>
                    {q.run_count ? `${q.run_count} run${q.run_count === 1 ? '' : 's'} · last ${relativeTime(q.last_run_at)} · ` : ''}
                    saved {relativeTime(q.updated_at ?? q.created_at)}
                  </p>
                  {open === q.id ? (
                    <pre
                      className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg p-3 font-code text-[11.5px] leading-[1.7]"
                      style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}
                    >
                      {q.sql}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2">
            <span className="label">activity log</span>
            <span className="font-code text-[10px]" style={{ color: 'var(--color-faint)' }}>
              last {history.length} questions
            </span>
          </div>
          {history.length === 0 ? (
            <p className="text-[12.5px]" style={{ color: 'var(--color-faint)' }}>
              Nothing recorded yet.
            </p>
          ) : (
            <div className={`${panel} overflow-x-auto`}>
              <table className="w-full text-left text-[12px]">
                <thead>
                  <tr style={{ background: 'var(--color-surface)' }}>
                    {['when', 'question', 'verdict', 'rows', 'latency'].map(h => (
                      <th key={h} className="px-3 py-2 font-code text-[10px] font-normal uppercase tracking-[0.12em]" style={{ color: 'var(--color-faint)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={`${h.timestamp}-${i}`} style={{ borderTop: '1px solid var(--color-border)' }}>
                      <td className="whitespace-nowrap px-3 py-2 font-code text-[11px]" style={{ color: 'var(--color-faint)' }}>
                        {relativeTime(h.timestamp)}
                      </td>
                      <td className="max-w-[320px] truncate px-3 py-2" title={h.question}>
                        {h.question || '—'}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="font-code text-[10.5px] uppercase"
                          style={{
                            color: h.validator_rejected
                              ? 'var(--color-destructive)'
                              : h.executed
                                ? 'var(--color-success)'
                                : 'var(--color-warn)',
                          }}
                        >
                          {h.validator_rejected ? 'blocked' : h.executed ? 'ran' : 'no sql'}
                        </span>
                      </td>
                      <td className="px-3 py-2 tabular" style={{ color: 'var(--color-muted)' }}>
                        {h.row_count}
                        {h.truncated ? '+' : ''}
                      </td>
                      <td className="px-3 py-2 tabular" style={{ color: 'var(--color-muted)' }}>
                        {h.latency_ms != null ? `${h.latency_ms}ms` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default LibraryView;
