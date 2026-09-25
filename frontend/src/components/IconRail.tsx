import React from 'react';
import { Database, MessageSquare, Waypoints } from 'lucide-react';
import type { ViewId } from '../types';

const ITEMS: { id: ViewId; label: string; Icon: typeof MessageSquare }[] = [
  { id: 'chat', label: 'Chat', Icon: MessageSquare },
  { id: 'connections', label: 'Connections', Icon: Database },
  { id: 'schema', label: 'Schema explorer', Icon: Waypoints },
];

interface IconRailProps {
  active: ViewId;
  onChange: (view: ViewId) => void;
}

/** Persistent left icon rail: the workspace's primary navigation. */
const IconRail: React.FC<IconRailProps> = ({ active, onChange }) => (
  <nav
    aria-label="Workspace views"
    className="flex w-14 shrink-0 flex-col items-center gap-1.5 border-r border-border bg-primary/50 py-3"
  >
    {/* Brand mark anchors the rail. */}
    <a
      href="/"
      aria-label="DataTalker home"
      className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-accent/12 transition-tool hover:bg-accent/20"
    >
      <img src="/favicon.svg" alt="" width={22} height={22} />
    </a>

    {ITEMS.map(({ id, label, Icon }) => {
      const isActive = active === id;
      return (
        <div key={id} className="group relative">
          <button
            type="button"
            onClick={() => onChange(id)}
            aria-label={label}
            aria-current={isActive ? 'page' : undefined}
            className={`relative flex h-9 w-9 items-center justify-center rounded-xl transition-tool hover:bg-surface-hi focus-visible:outline-2 focus-visible:outline-accent ${
              isActive
                ? 'bg-accent/12 text-accent'
                : 'text-muted hover:text-fg'
            }`}
          >
            {isActive ? (
              <span
                aria-hidden
                className="absolute -left-[13px] h-4 w-[2px] rounded-full bg-accent"
              />
            ) : null}
            <Icon size={17} strokeWidth={1.8} />
          </button>
          <span
            role="tooltip"
            className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-lg border border-border bg-surface-hi px-2 py-1 text-[11px] font-medium text-fg opacity-0 shadow-tinted transition-tool group-hover:opacity-100"
          >
            {label}
          </span>
        </div>
      );
    })}
  </nav>
);

export default IconRail;
