import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BookmarkPlus, Play, X } from 'lucide-react';
import type { ActiveDbRef, SqlRunResponse } from '../../types';
import { getErrorMessage, putSavedQuery, runSql } from '../../lib/api';
import ChartView from '../ChartView';
import { hasPlottableColumn } from '../../lib/chart';
import ResultsTable from '../ResultsTable';
import { Field, Spinner, buttonGhost, buttonPrimary, inputClass, panel } from '../ui';

interface SqlLabViewProps {
  apiUrl: string;
  apiKey: string;
  dbRef: ActiveDbRef | null;
  /** A statement pushed in from the library. */
  initialSql?: string | null;
  onGoToConnections: () => void;
}

/** SQL Lab: write the statement yourself, same guard, no model in the loop. */
const SqlLabView: React.FC<SqlLabViewProps> = ({ apiUrl, apiKey, dbRef, initialSql, onGoToConnections }) => {
  const [sql, setSql] = useState(initialSql?.trim() ? initialSql : 'SELECT 1');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SqlRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('');
  const [saveOpen, setSaveOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  // A statement opened from the library replaces whatever was in the editor.
  useEffect(() => {
    if (initialSql?.trim()) {
      setSql(initialSql);
      setResult(null);
      setError(null);
    }
  }, [initialSql]);

  const execute = useCallback(async () => {
    const statement = sql.trim();
    if (!statement || running) return;
    if (!dbRef) {
      setError('Attach a database first — the console needs somewhere to run.');
      return;
    }
    setRunning(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const data = await runSql({ apiUrl, apiKey, sql: statement, dbRef, signal: controller.signal });
      setResult(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(getErrorMessage(err));
    } finally {
      abortRef.current = null;
      setRunning(false);
    }
  }, [apiUrl, apiKey, dbRef, running, sql]);

  const save = useCallback(async () => {
    if (!result?.sql || !saveName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await putSavedQuery(apiUrl, apiKey, {
        name: saveName.trim(),
        sql: result.sql,
        source: dbRef?.kind === 'connection' ? dbRef.name : null,
      });
      setSaveOpen(false);
      setSaveName('');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [apiUrl, apiKey, dbRef, result, saveName]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <div className={`${panel} overflow-hidden`}>
          <div
            className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2"
            style={{ background: 'var(--color-surface)' }}
          >
            <span className="label">statement</span>
            <span className="tag ml-auto normal-case tracking-normal">
              {dbRef ? 'read-only guard applies' : 'no source attached'}
            </span>
            <button
              type="button"
              onClick={() => void execute()}
              disabled={running || !sql.trim()}
              className={buttonPrimary}
            >
              {running ? <Spinner /> : <Play className="size-3.5" />}
              Run
            </button>
            <button
              type="button"
              onClick={() => setSaveOpen(v => !v)}
              disabled={!result?.sql}
              className={buttonGhost}
              title="Save this statement to the library"
            >
              <BookmarkPlus className="size-3.5" />
              Save
            </button>
          </div>

          <textarea
            value={sql}
            onChange={e => setSql(e.target.value)}
            onKeyDown={e => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                void execute();
              }
            }}
            spellCheck={false}
            aria-label="SQL statement"
            className="block max-h-[420px] min-h-[140px] w-full resize-y bg-transparent px-4 py-3 font-code text-[12.5px] leading-[1.75] text-fg outline-none"
            placeholder="SELECT * FROM patients LIMIT 10"
          />

          {result ? (
            <div
              className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2 font-code text-[11px]"
              style={{ background: 'var(--color-surface)' }}
            >
              {result.sql_executed ? (
                <>
                  <span style={{ color: 'var(--color-success)' }}>
                    ok · {result.row_count} {result.row_count === 1 ? 'row' : 'rows'} · {result.latency_ms}ms
                  </span>
                  {result.results_truncated ? (
                    <span style={{ color: 'var(--color-warn)' }}>capped at {result.row_cap}</span>
                  ) : null}
                </>
              ) : (
                <span style={{ color: 'var(--color-destructive)' }}>
                  {result.validator_rejected ? 'blocked' : 'failed'} · {result.reason}
                </span>
              )}
              <span className="ml-auto" style={{ color: 'var(--color-faint)' }}>
                ⌘/Ctrl + Enter
              </span>
            </div>
          ) : null}
        </div>

        {saveOpen ? (
          <div className={`${panel} p-4`}>
            <Field label="Name" htmlFor="sql-save-name">
              <div className="flex gap-2">
                <input
                  id="sql-save-name"
                  className={inputClass}
                  value={saveName}
                  onChange={e => setSaveName(e.target.value)}
                  placeholder="Weekly appointment count"
                />
                <button type="button" onClick={() => void save()} disabled={saving || !saveName.trim()} className={buttonPrimary}>
                  {saving ? <Spinner /> : null}
                  Save query
                </button>
                <button type="button" onClick={() => setSaveOpen(false)} className={`${buttonGhost} shrink-0`} aria-label="Cancel">
                  <X className="size-3.5" />
                </button>
              </div>
            </Field>
          </div>
        ) : null}

        {error ? (
          <p className="text-[12.5px]" style={{ color: 'var(--color-destructive)' }}>
            {error}
          </p>
        ) : null}

        {result?.results?.length ? (
          <>
            {hasPlottableColumn(result.results) ? (
              <div className={`${panel} p-4`}>
                <ChartView rows={result.results} />
              </div>
            ) : null}
            <div className={`${panel} overflow-hidden`}>
              <div className="border-b border-border px-4 py-2">
                <span className="label">results</span>
              </div>
              <ResultsTable results={result.results} />
            </div>
          </>
        ) : result?.sql_executed ? (
          <p className="text-[12.5px]" style={{ color: 'var(--color-faint)' }}>
            The statement ran and returned no rows.
          </p>
        ) : null}

        {!dbRef ? (
          <button type="button" onClick={onGoToConnections} className={buttonGhost}>
            Attach a database
          </button>
        ) : null}
      </div>
    </div>
  );
};

export default SqlLabView;
