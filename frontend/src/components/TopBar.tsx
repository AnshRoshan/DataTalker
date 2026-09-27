import React from 'react';
import { Activity, BookMarked, Database, MessageSquare, Settings, SquareTerminal, Waypoints } from 'lucide-react';
import type { ActiveDbRef, HealthStatus, ViewId } from '../types';
import { dbRefLabel } from '../lib/format';
import { StatusDot } from './ui';

const TITLES: Record<ViewId, { title: string; sub: string }> = {
  chat: { title: 'Ask', sub: 'natural language → read-only sql' },
  sql: { title: 'SQL lab', sub: 'write it yourself, same guard' },
  connections: { title: 'Sources', sub: 'databases, attachments, preflight' },
  schema: { title: 'Schema', sub: 'tables, columns, join paths' },
  library: { title: 'Library', sub: 'saved queries & activity log' },
  insights: { title: 'Pulse', sub: 'usage, safety and latency' },
};

const MOBILE_NAV: { id: ViewId; label: string; Icon: typeof MessageSquare }[] = [
  { id: 'chat', label: 'Ask', Icon: MessageSquare },
  { id: 'sql', label: 'SQL lab', Icon: SquareTerminal },
  { id: 'connections', label: 'Sources', Icon: Database },
  { id: 'schema', label: 'Schema', Icon: Waypoints },
  { id: 'library', label: 'Library', Icon: BookMarked },
  { id: 'insights', label: 'Pulse', Icon: Activity },
];

interface TopBarProps {
  view: ViewId;
  onViewChange: (view: ViewId) => void;
  activeRef: ActiveDbRef | null;
  refOk: boolean | null; // null = unknown (e.g. quick attach with no status yet)
  health: HealthStatus;
  onOpenSettings: () => void;
}

/** Header: where you are, which database is active, whether the backend answers. */
const TopBar: React.FC<TopBarProps> = ({
  view,
  onViewChange,
  activeRef,
  refOk,
  health,
  onOpenSettings,
}) => {
  const healthLabel =
    health === 'connected' ? 'Connected' : health === 'checking' ? 'Checking' : 'Disconnected';
  const healthTone: 'ok' | 'error' | 'unknown' =
    health === 'connected' ? 'ok' : health === 'disconnected' ? 'error' : 'unknown';
  const meta = TITLES[view];

  return (
    <header
      className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border px-4 backdrop-blur"
      style={{ background: 'color-mix(in srgb, var(--color-primary) 88%, transparent)' }}
    >
      <div className="min-w-0">
        <h1 className="truncate font-display text-[15px] font-semibold leading-tight tracking-tight">
          {meta.title}
        </h1>
        <p className="truncate font-code text-[10px] uppercase tracking-[0.1em] text-faint">{meta.sub}</p>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Narrow viewports have no sidebar, so the views live here instead. */}
        <div className="flex items-center gap-1 md:hidden">
          {MOBILE_NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => onViewChange(id)}
              aria-label={label}
              aria-current={view === id ? 'page' : undefined}
              className="btn btn-ghost size-9 p-0"
              style={view === id ? { color: 'var(--color-accent)', background: 'var(--color-accent-soft)' } : undefined}
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>

        {activeRef ? (
          <span className="tag h-9 gap-2 px-2.5 normal-case tracking-normal" style={{ maxWidth: 260 }}>
            <StatusDot tone={refOk === null ? 'unknown' : refOk ? 'ok' : 'error'} />
            <span className="truncate text-[11.5px] normal-case">{dbRefLabel(activeRef)}</span>
          </span>
        ) : (
          <span className="tag h-9 hidden px-2.5 sm:inline-flex">no source attached</span>
        )}

        <span className="tag h-9 gap-2 px-2.5" title="Backend /health status">
          <StatusDot tone={healthTone} />
          <span className="text-[10.5px]">{healthLabel}</span>
        </span>

        <button type="button" onClick={onOpenSettings} aria-label="Open settings" className="btn btn-secondary size-9 p-0">
          <Settings className="size-4" />
        </button>
      </div>
    </header>
  );
};

export default TopBar;
