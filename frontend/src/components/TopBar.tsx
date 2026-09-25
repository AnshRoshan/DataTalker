import React from 'react';
import { Settings } from 'lucide-react';
import type { ActiveDbRef, HealthStatus } from '../types';
import { dbRefLabel } from '../lib/format';
import { StatusDot, iconButton } from './ui';

const APP_VERSION = 'v0.4.0';

interface TopBarProps {
  activeRef: ActiveDbRef | null;
  refOk: boolean | null; // null = unknown (e.g. quick attach with no status yet)
  health: HealthStatus;
  onOpenSettings: () => void;
}

/** Top bar: identity, active database chip, backend health, settings. */
const TopBar: React.FC<TopBarProps> = ({ activeRef, refOk, health, onOpenSettings }) => {
  const healthLabel =
    health === 'connected' ? 'Connected' : health === 'checking' ? 'Checking' : 'Disconnected';
  const healthTone: 'ok' | 'error' | 'unknown' =
    health === 'connected' ? 'ok' : health === 'disconnected' ? 'error' : 'unknown';

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-bg/70 px-4 backdrop-blur">
      {/* Brand lockup */}
      <div className="flex items-center gap-2.5">
        <img src="/favicon.svg" alt="" width={24} height={24} aria-hidden />
        <span className="font-display text-[15px] font-semibold tracking-tight text-fg">
          DataTalker
        </span>
      </div>

      {/* Active database chip */}
      {activeRef ? (
        <div
          className="flex min-w-0 items-center gap-2 rounded-full border border-border bg-primary py-1 pl-2.5 pr-3"
          title="Active database"
        >
          <StatusDot tone={refOk === null ? 'unknown' : refOk ? 'ok' : 'error'} />
          <span className="max-w-[160px] truncate text-[12px] font-medium text-fg/85 sm:max-w-[280px]">
            {dbRefLabel(activeRef)}
          </span>
        </div>
      ) : (
        <span className="hidden rounded-full border border-dashed border-border-strong px-3 py-1 text-[12px] text-muted sm:inline">
          No database attached
        </span>
      )}

      <div className="flex-1" />

      {/* Backend health badge, polled every 30s */}
      <div
        className="flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-primary px-2.5 py-1"
        title="Backend /health status"
      >
        <StatusDot tone={healthTone} />
        <span className="text-[11px] font-medium text-muted">{healthLabel}</span>
      </div>

      <span className="hidden font-code text-[10px] text-faint sm:inline">{APP_VERSION}</span>

      <button type="button" onClick={onOpenSettings} aria-label="Open settings" className={iconButton}>
        <Settings size={16} strokeWidth={1.8} />
      </button>
    </header>
  );
};

export default TopBar;
