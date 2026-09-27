import React from 'react';
import { navigate } from '../lib/router';

/* Small shared primitives so every view reads from the same visual language. */

/** Anchor that routes in-app and degrades to a normal link on middle-click/new tab. */
export const Link: React.FC<{
  to: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
  onClick?: () => void;
}> = ({ to, className = '', style, children, onClick }) => (
  <a
    href={to}
    className={className}
    style={style}
    onClick={event => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      event.preventDefault();
      onClick?.();
      navigate(to);
    }}
  >
    {children}
  </a>
);

export const StatusDot: React.FC<{
  tone: 'ok' | 'error' | 'unknown';
  className?: string;
}> = ({ tone, className = '' }) => {
  const color =
    tone === 'ok' ? 'bg-accent' : tone === 'error' ? 'bg-destructive' : 'bg-muted';
  return (
    <span
      role="img"
      aria-label={tone === 'ok' ? 'connected' : tone === 'error' ? 'error' : 'unknown status'}
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${color} ${className}`}
    />
  );
};

export const Spinner: React.FC<{ className?: string }> = ({ className = 'h-3.5 w-3.5' }) => (
  <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
    <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

export const Badge: React.FC<{ children: React.ReactNode; tone?: 'default' | 'accent' }> = ({
  children,
  tone = 'default',
}) => (
  <span
    className={`inline-flex items-center rounded-md px-1.5 py-0.5 font-code text-[10px] uppercase tracking-wide ${
      tone === 'accent'
        ? 'bg-accent/12 text-accent'
        : 'border border-border bg-surface-hi/60 text-muted'
    }`}
  >
    {children}
  </span>
);

/** Real label + control wrapper used by every form in the app. */
export const Field: React.FC<{
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}> = ({ label, htmlFor, hint, children }) => (
  <div>
    <label htmlFor={htmlFor} className="mb-1 block text-[12px] font-medium text-fg/80">
      {label}
    </label>
    {children}
    {hint ? <p className="mt-1 text-[11px] text-muted">{hint}</p> : null}
  </div>
);

export const inputClass =
  'field';

export const buttonPrimary =
  'btn btn-primary shadow-tinted-sm';

export const buttonGhost = 'btn btn-secondary';

export const buttonDanger = 'btn btn-danger';

export const iconButton =
  'inline-flex h-8 w-8 items-center justify-center rounded-button text-muted transition-tool hover:bg-surface hover:text-fg disabled:cursor-not-allowed disabled:opacity-40';

/** Elevated panel: the workhorse surface of the workspace. */
export const panel = 'panel';

/** Micro uppercase label used for section headers everywhere. */
export const MicroLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => <span className={`label ${className}`}>{children}</span>;
