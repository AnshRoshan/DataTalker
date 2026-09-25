import React, { useRef, useState } from 'react';
import { CheckCircle2, CircleAlert, Database, Plus, RefreshCw, Trash2, Upload } from 'lucide-react';
import type { ActiveDbRef, Connection, NewConnectionInput } from '../../types';
import { relativeTime } from '../../lib/format';
import { Badge, Field, StatusDot, Spinner, buttonGhost, buttonPrimary, inputClass } from '../ui';

interface ConnectionsViewProps {
  connections: Connection[];
  isLoading: boolean;
  loadError: string | null;
  activeRef: ActiveDbRef | null;
  onReload: () => void;
  onSetActive: (connection: Connection) => void;
  onCreate: (input: NewConnectionInput) => Promise<Connection>;
  onCheck: (id: number) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onQuickAttach: (ref: ActiveDbRef) => void;
}

function statusTone(conn: Connection): 'ok' | 'error' | 'unknown' {
  if (!conn.last_status) return 'unknown';
  return conn.last_status.ok ? 'ok' : 'error';
}

/** Card in the saved-connections grid. */
const ConnectionCard: React.FC<{
  conn: Connection;
  isActive: boolean;
  onSetActive: () => void;
  onCheck: () => Promise<void>;
  onDelete: () => Promise<void>;
}> = ({ conn, isActive, onSetActive, onCheck, onDelete }) => {
  const [checking, setChecking] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const tone = statusTone(conn);
  const status = conn.last_status;

  const handleCheck = async () => {
    setChecking(true);
    try {
      await onCheck();
    } finally {
      setChecking(false);
    }
  };

  const handleDelete = async () => {
    if (!confirming) {
      setConfirming(true);
      window.setTimeout(() => setConfirming(false), 4000);
      return;
    }
    try {
      await onDelete();
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div
      className={`flex flex-col rounded-card border bg-surface/40 p-3 transition-tool ${
        isActive ? 'border-accent/60' : 'border-border/40 hover:border-border/70'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <StatusDot tone={tone} />
          <h3 className="truncate text-[13px] font-medium text-fg" title={conn.name}>
            {conn.name}
          </h3>
        </div>
        {conn.dialect ? <Badge>{conn.dialect}</Badge> : null}
      </div>

      <p
        className="mt-1.5 truncate font-display text-[11px] text-fg/40"
        title={conn.connection_string_masked}
      >
        {conn.connection_string_masked}
      </p>

      <p className="mt-1 text-[12px] text-fg/50">
        {status && status.ok
          ? `${status.table_count ?? '?'} tables · checked ${relativeTime(conn.last_checked_at)}`
          : status && !status.ok
            ? `Check failed, ${relativeTime(conn.last_checked_at)}`
            : 'Never checked'}
      </p>

      {status && !status.ok && status.error ? (
        <p className="mt-1 line-clamp-2 text-[11px] text-destructive/90" title={status.error}>
          {status.error}
        </p>
      ) : null}

      <div className="mt-3 flex items-center gap-1.5 border-t border-border/20 pt-2.5">
        <button
          type="button"
          onClick={onSetActive}
          disabled={isActive}
          className={
            isActive
              ? 'inline-flex items-center gap-1.5 rounded-button px-2 py-1 text-[12px] text-accent'
              : `${buttonGhost} px-2! py-1! text-[12px]!`
          }
        >
          {isActive ? <CheckCircle2 size={13} className="text-accent" /> : null}
          {isActive ? 'Active' : 'Set active'}
        </button>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => void handleCheck()}
          disabled={checking}
          aria-label={`Re-check ${conn.name}`}
          title="Re-check connection"
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-fg/40 transition-tool hover:bg-surface-hi hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
        >
          {checking ? <Spinner className="h-3 w-3" /> : <RefreshCw size={13} />}
        </button>
        <button
          type="button"
          onClick={() => void handleDelete()}
          aria-label={confirming ? `Confirm delete ${conn.name}` : `Delete ${conn.name}`}
          title={confirming ? 'Click again to confirm' : 'Delete connection'}
          className={`inline-flex h-6 items-center justify-center gap-1 rounded-md px-1.5 text-[11px] transition-tool focus-visible:outline-2 focus-visible:outline-accent ${
            confirming
              ? 'bg-destructive/15 text-destructive'
              : 'text-fg/40 hover:bg-surface-hi hover:text-destructive'
          }`}
        >
          <Trash2 size={13} />
          {confirming ? 'Confirm' : ''}
        </button>
      </div>
    </div>
  );
};

const PLACEHOLDER_EXAMPLES = [
  'sqlite:///C:/data/app.db',
  'postgresql://user:pass@host:5432/dbname',
  'mysql://user:pass@host:3306/dbname',
];

const ConnectionsView: React.FC<ConnectionsViewProps> = ({
  connections,
  isLoading,
  loadError,
  activeRef,
  onReload,
  onSetActive,
  onCreate,
  onCheck,
  onDelete,
  onQuickAttach,
}) => {
  // Add-connection form state
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState('');
  const [connectionString, setConnectionString] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [preflight, setPreflight] = useState<Connection | null>(null);

  // Quick-attach state
  const [quickString, setQuickString] = useState('');
  const [quickPath, setQuickPath] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetForm = () => {
    setName('');
    setConnectionString('');
    setNotes('');
    setSubmitError(null);
    setPreflight(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setPreflight(null);
    setSubmitting(true);
    try {
      const created = await onCreate({ name: name.trim(), connection_string: connectionString.trim(), notes: notes.trim() || undefined });
      setPreflight(created);
      setName('');
      setConnectionString('');
      setNotes('');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save the connection.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onQuickAttach({ kind: 'file', file, name: file.name });
    e.target.value = '';
  };

  const quickStringIsUrl = /^https?:\/\//i.test(quickString.trim());

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-[15px] font-semibold text-fg">Connections</h1>
            <p className="mt-0.5 text-[12px] text-fg/50">
              Saved databases you can chat with. The active one is used on every question.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onReload} className={buttonGhost} disabled={isLoading}>
              {isLoading ? <Spinner /> : <RefreshCw size={13} />}
              Refresh
            </button>
            <button type="button" onClick={() => setShowAdd(s => !s)} className={buttonPrimary}>
              <Plus size={14} />
              Add connection
            </button>
          </div>
        </div>

        {loadError ? (
          <p role="alert" className="mt-4 rounded-card border border-destructive/50 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
            {loadError}
          </p>
        ) : null}

        {/* Saved connections grid */}
        <section aria-label="Saved connections" className="mt-5">
          {connections.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border/40 py-10 text-center">
              <Database size={20} className="text-fg/30" aria-hidden />
              <p className="text-[13px] text-fg/50">No saved connections yet.</p>
              <p className="text-[12px] text-fg/35">
                Add one above, or quick-attach a file below for a one-off session.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {connections.map(conn => (
                <ConnectionCard
                  key={conn.id}
                  conn={conn}
                  isActive={activeRef?.kind === 'connection' && activeRef.id === conn.id}
                  onSetActive={() => onSetActive(conn)}
                  onCheck={() => onCheck(conn.id)}
                  onDelete={() => onDelete(conn.id)}
                />
              ))}
            </div>
          )}
        </section>

        {/* Add-connection form */}
        {showAdd ? (
          <section aria-label="Add connection" className="mt-6 rounded-card border border-border/40 bg-surface/20 p-4">
            <h2 className="font-display text-[13px] font-semibold text-fg">Add connection</h2>
            <p className="mt-0.5 text-[12px] text-fg/50">
              The server runs a preflight check when you save. It must succeed for the connection
              to be stored.
            </p>
            <form onSubmit={e => void handleSubmit(e)} className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Name" htmlFor="conn-name">
                <input
                  id="conn-name"
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="Production warehouse"
                />
              </Field>
              <div />
              <div className="md:col-span-2">
                <Field label="Connection string" htmlFor="conn-string">
                  <textarea
                    id="conn-string"
                    value={connectionString}
                    onChange={e => setConnectionString(e.target.value)}
                    required
                    rows={3}
                    spellCheck={false}
                    className={`${inputClass} font-display text-[12px]`}
                    placeholder={PLACEHOLDER_EXAMPLES.join('\n')}
                  />
                </Field>
              </div>
              <div className="md:col-span-2">
                <Field label="Notes (optional)" htmlFor="conn-notes">
                  <input
                    id="conn-notes"
                    type="text"
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    className={inputClass}
                    placeholder="What lives in this database, who owns it..."
                  />
                </Field>
              </div>
              <div className="flex items-center gap-3 md:col-span-2">
                <button type="submit" className={buttonPrimary} disabled={submitting}>
                  {submitting ? <Spinner /> : null}
                  Save and test
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAdd(false);
                    resetForm();
                  }}
                  className={buttonGhost}
                >
                  Cancel
                </button>
              </div>
            </form>

            {submitError ? (
              <p role="alert" className="mt-3 flex items-start gap-1.5 rounded-card border border-destructive/50 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
                <CircleAlert size={14} className="mt-0.5 shrink-0" aria-hidden />
                {submitError}
              </p>
            ) : null}

            {preflight ? (
              <div className="mt-3 rounded-card border border-accent/50 bg-accent/5 px-3 py-2.5">
                <p className="flex items-center gap-1.5 text-[13px] font-medium text-accent">
                  <CheckCircle2 size={14} aria-hidden />
                  Saved. Preflight passed for {preflight.name}.
                </p>
                {preflight.last_status && preflight.last_status.ok ? (
                  <p className="mt-1 font-display text-[11px] text-fg/50">
                    {[
                      preflight.last_status.dialect,
                      preflight.last_status.server_version,
                      preflight.last_status.table_count != null
                        ? `${preflight.last_status.table_count} tables`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                ) : null}
                {preflight.last_status && preflight.last_status.ok && preflight.last_status.warnings?.length ? (
                  <ul className="mt-1 list-disc pl-4 text-[11px] text-fg/50">
                    {preflight.last_status.warnings.map(w => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        {/* Quick attach: one-off use without saving */}
        <section aria-label="Quick attach" className="mt-6 rounded-card border border-border/40 p-4">
          <h2 className="font-display text-[13px] font-semibold text-fg">Quick attach</h2>
          <p className="mt-0.5 text-[12px] text-fg/50">
            Use a database for this session without saving it. It becomes the active reference for
            chat and the schema explorer.
          </p>
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <Field label="Upload .db file" htmlFor="quick-file">
                <input
                  ref={fileInputRef}
                  id="quick-file"
                  type="file"
                  accept=".db,.sqlite,.sqlite3"
                  onChange={handleFilePick}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className={`${buttonGhost} w-full justify-start`}
                >
                  <Upload size={13} />
                  {activeRef?.kind === 'file' ? activeRef.name : 'Choose file'}
                </button>
              </Field>
            </div>
            <div>
              <Field label="Server path (advanced)" htmlFor="quick-path">
                <div className="flex gap-1.5">
                  <input
                    id="quick-path"
                    type="text"
                    value={quickPath}
                    onChange={e => setQuickPath(e.target.value)}
                    className={`${inputClass} font-display text-[12px]`}
                    placeholder="/abs/path/on/server.db"
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    className={`${buttonGhost} shrink-0 px-2!`}
                    disabled={!quickPath.trim()}
                    onClick={() => onQuickAttach({ kind: 'path', path: quickPath.trim() })}
                  >
                    Attach
                  </button>
                </div>
              </Field>
            </div>
            <div>
              <Field label="Connection string or file URL" htmlFor="quick-string">
                <div className="flex gap-1.5">
                  <input
                    id="quick-string"
                    type="text"
                    value={quickString}
                    onChange={e => setQuickString(e.target.value)}
                    className={`${inputClass} font-display text-[12px]`}
                    placeholder={
                      quickStringIsUrl ? 'https://host/db.sqlite' : 'postgres://user:pass@host/db'
                    }
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    className={`${buttonGhost} shrink-0 px-2!`}
                    disabled={!quickString.trim()}
                    onClick={() =>
                      onQuickAttach({ kind: 'string', connectionString: quickString.trim() })
                    }
                  >
                    Attach
                  </button>
                </div>
              </Field>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default ConnectionsView;
