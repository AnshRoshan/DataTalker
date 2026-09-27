import React from 'react';
import {
  Database,
  LogOut,
  MessageSquare,
  Moon,
  Plus,
  Settings,
  Sun,
  Waypoints,
} from 'lucide-react';
import type { ViewId } from '../types';
import type { AuthUser } from '../lib/auth';
import type { Theme } from '../lib/theme';
import { Link } from './ui';
import { Mark } from './Mark';

const NAV: { id: ViewId; label: string; Icon: typeof MessageSquare }[] = [
  { id: 'chat', label: 'Ask', Icon: MessageSquare },
  { id: 'connections', label: 'Sources', Icon: Database },
  { id: 'schema', label: 'Schema', Icon: Waypoints },
];

interface SidebarProps {
  view: ViewId;
  onChange: (view: ViewId) => void;
  onNewChat: () => void;
  hasMessages: boolean;
  connectionCount: number;
  user: AuthUser | null;
  onSignOut: () => void;
  googleEnabled: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
}

/** Workspace navigation. Identity, theme and settings live here so the header only
 * ever has to say where you are and which database you are talking to. */
const Sidebar: React.FC<SidebarProps> = ({
  view,
  onChange,
  onNewChat,
  hasMessages,
  connectionCount,
  user,
  onSignOut,
  googleEnabled,
  theme,
  onToggleTheme,
  onOpenSettings,
}) => (
  <aside
    className="sticky top-0 hidden h-dvh w-[236px] shrink-0 flex-col border-r border-border md:flex"
    style={{ background: 'var(--color-primary)' }}
  >
    <div className="flex h-14 shrink-0 items-center border-b border-border px-4">
      <Link to="/" aria-label="DataTalker home">
        <Mark size={26} />
      </Link>
      <span className="ml-2.5 min-w-0">
        <span className="block truncate font-display text-[15px] font-semibold leading-none tracking-tight">
          DataTalker
        </span>
        <span className="mt-1 block font-code text-[9px] uppercase tracking-[0.16em] text-faint">
          nl → read-only sql
        </span>
      </span>
    </div>

    <div className="shrink-0 p-3">
      <button
        type="button"
        onClick={onNewChat}
        disabled={!hasMessages}
        className="btn btn-primary h-9 w-full"
        title={hasMessages ? 'Start a new conversation' : 'No conversation in progress'}
      >
        <Plus className="size-4" /> New question
      </button>
    </div>

    <nav aria-label="Workspace views" className="space-y-px px-3">
      {NAV.map(({ id, label, Icon }) => {
        const on = view === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-current={on ? 'page' : undefined}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12.5px] font-medium transition-colors"
            style={{
              background: on ? 'var(--color-surface)' : 'transparent',
              color: on ? 'var(--color-fg)' : 'var(--color-muted)',
              boxShadow: on ? 'inset 2px 0 0 var(--color-accent)' : undefined,
            }}
          >
            <Icon
              className="size-4 shrink-0"
              strokeWidth={1.8}
              style={{ color: on ? 'var(--color-accent)' : 'var(--color-faint)' }}
            />
            <span className="flex-1 truncate text-left">{label}</span>
            {id === 'connections' && connectionCount > 0 ? (
              <span className="font-code text-[10px] text-faint">{connectionCount}</span>
            ) : null}
          </button>
        );
      })}
    </nav>

    <div className="mt-auto shrink-0 space-y-px p-3" style={{ borderTop: '1px solid var(--color-border)' }}>
      <button
        type="button"
        onClick={onOpenSettings}
        className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12.5px] font-medium text-muted transition-colors hover:bg-surface hover:text-fg"
      >
        <Settings className="size-4 shrink-0" strokeWidth={1.8} style={{ color: 'var(--color-faint)' }} />
        Settings & keys
      </button>

      <div className="flex items-center gap-2 px-1.5 pt-2" style={{ borderTop: '1px solid var(--color-border)' }}>
        {user ? (
          <>
            {user.picture ? (
              <img src={user.picture} alt="" className="size-7 shrink-0 rounded-full" referrerPolicy="no-referrer" />
            ) : (
              <span className="grid size-7 shrink-0 place-items-center rounded-full border border-border bg-surface font-code text-[11px] font-bold text-accent">
                {user.name?.[0]?.toUpperCase() ?? '?'}
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12px] font-semibold">{user.name}</span>
              <span className="block truncate text-[10.5px] text-faint">{user.email}</span>
            </span>
            <button type="button" onClick={onSignOut} className="btn btn-ghost size-7 p-0" title="Sign out">
              <LogOut className="size-3.5" />
            </button>
          </>
        ) : (
          <>
            <span className="min-w-0 flex-1">
              <span className="block text-[12px] font-semibold">Not signed in</span>
              <span className="block text-[10.5px] text-faint">
                {googleEnabled ? 'Google account optional' : 'Local session'}
              </span>
            </span>
            {googleEnabled ? (
              <Link to="/login" className="btn btn-secondary h-7 px-2 text-[11px]">
                Sign in
              </Link>
            ) : null}
          </>
        )}
        <button
          type="button"
          onClick={onToggleTheme}
          className="btn btn-ghost size-7 p-0"
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
        </button>
      </div>
    </div>
  </aside>
);

export default Sidebar;
