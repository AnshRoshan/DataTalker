import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type { Stats } from '../../types';
import { fetchStats, getErrorMessage } from '../../lib/api';
import { Spinner, buttonGhost, panel } from '../ui';

/** Pulse: what has been asked, what the guard stopped, and how long it took.
 * Every figure is aggregated from the audit log server-side (core/stats.py), so this
 * view cannot disagree with the log itself. */
const InsightsView: React.FC<{ apiUrl: string; apiKey: string }> = ({ apiUrl, apiKey }) => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStats(await fetchStats(apiUrl, apiKey));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [apiUrl, apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const cards = stats
    ? [
        { label: 'questions asked', value: stats.questions },
        { label: 'statements blocked', value: stats.blocked, tone: 'danger' as const },
        { label: 'avg latency', value: stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '—' },
        { label: 'p95 latency', value: stats.p95_latency_ms != null ? `${stats.p95_latency_ms}ms` : '—' },
        { label: 'rows returned', value: stats.rows_returned },
        { label: 'row-cap hits', value: stats.truncated, tone: 'warn' as const },
      ]
    : [];

  const peak = Math.max(...(stats?.activity.map(d => d.questions) ?? [1]), 1);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto w-full max-w-5xl space-y-5">
        <div className="flex items-center gap-2">
          <span className="label">usage · safety · performance</span>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className={`${buttonGhost} ml-auto h-7 px-2 text-[11px]`}
          >
            {loading ? <Spinner /> : <RefreshCw className="size-3" />}
            Refresh
          </button>
        </div>

        {error ? (
          <p className="text-[12.5px]" style={{ color: 'var(--color-destructive)' }}>
            {error}
          </p>
        ) : null}

        {stats && !stats.audit_enabled ? (
          <p className="text-[12.5px]" style={{ color: 'var(--color-warn)' }}>
            Auditing is disabled (DATATALKER_AUDIT_LOG_PATH is empty), so these figures stay empty.
          </p>
        ) : null}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {cards.map(c => (
            <div key={c.label} className={`${panel} px-4 py-3`}>
              <p
                className="font-display text-[26px] leading-none tabular"
                style={{
                  color:
                    c.tone === 'danger' && Number(c.value) > 0
                      ? 'var(--color-destructive)'
                      : c.tone === 'warn' && Number(c.value) > 0
                        ? 'var(--color-warn)'
                        : undefined,
                }}
              >
                {c.value}
              </p>
              <p className="mt-1.5 font-code text-[10px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-faint)' }}>
                {c.label}
              </p>
            </div>
          ))}
        </div>

        <div className={`${panel} p-4`}>
          <div className="mb-3 flex items-center justify-between">
            <span className="label">{stats?.window_days ?? 14}-day activity</span>
            <span className="font-code text-[10px]" style={{ color: 'var(--color-faint)' }}>
              {stats?.questions_in_window ?? 0} in window
            </span>
          </div>
          <div className="flex h-32 items-end gap-1.5">
            {(stats?.activity ?? []).map(day => (
              <div key={day.date} className="flex flex-1 flex-col items-center justify-end gap-1" style={{ height: '100%' }}>
                <div
                  className="w-full rounded-t-[3px]"
                  style={{
                    height: `${(day.questions / peak) * 100}%`,
                    minHeight: day.questions ? 2 : 0,
                    background: day.blocked ? 'var(--color-warn)' : 'var(--color-accent)',
                  }}
                  title={`${day.date}: ${day.questions} question(s), ${day.blocked} blocked`}
                />
                <span className="font-code text-[8.5px]" style={{ color: 'var(--color-faint)' }}>
                  {day.date.slice(8)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className={`${panel} p-4`}>
            <span className="label">by dialect</span>
            <ul className="mt-2 space-y-1.5">
              {Object.entries(stats?.dialects ?? {}).length === 0 ? (
                <li className="text-[12.5px]" style={{ color: 'var(--color-faint)' }}>
                  No queries recorded yet.
                </li>
              ) : (
                Object.entries(stats?.dialects ?? {}).map(([dialect, count]) => (
                  <li key={dialect} className="flex items-center justify-between text-[12.5px]">
                    <span className="font-code text-[11.5px] uppercase">{dialect}</span>
                    <span className="tabular" style={{ color: 'var(--color-muted)' }}>
                      {count}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className={`${panel} p-4`}>
            <span className="label">instance activity</span>
            <ul className="mt-2 space-y-1.5 text-[12.5px]">
              <li className="flex items-center justify-between">
                <span style={{ color: 'var(--color-muted)' }}>schema reflections</span>
                <span className="tabular">{stats?.schema_reads ?? 0}</span>
              </li>
              <li className="flex items-center justify-between">
                <span style={{ color: 'var(--color-muted)' }}>sign-ins</span>
                <span className="tabular">{stats?.sign_ins ?? 0}</span>
              </li>
              <li className="flex items-center justify-between">
                <span style={{ color: 'var(--color-muted)' }}>slowest statement</span>
                <span className="tabular">{stats?.slowest_ms != null ? `${stats.slowest_ms}ms` : '—'}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InsightsView;
