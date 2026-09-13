import React from 'react';

/* Small shared primitives so every view reads from the same visual language. */

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
  'w-full rounded-input border border-border-strong bg-bg/60 px-3 py-2 text-[13px] text-fg placeholder:text-faint transition-tool hover:border-border-strong focus:border-accent';

export const buttonPrimary =
  'inline-flex items-center justify-center gap-1.5 rounded-button bg-accent px-3.5 py-2 text-[13px] font-medium text-[#053B26] transition-tool hover:bg-accent-strong shadow-tinted-sm disabled:cursor-not-allowed disabled:opacity-40';

export const buttonGhost =
  'inline-flex items-center justify-center gap-1.5 rounded-button border border-border-strong bg-surface/60 px-3.5 py-2 text-[13px] text-fg/80 transition-tool hover:border-accent/50 hover:bg-surface-hi hover:text-fg disabled:cursor-not-allowed disabled:opacity-40';

export const iconButton =
  'inline-flex h-8 w-8 items-center justify-center rounded-button text-muted transition-tool hover:bg-surface-hi hover:text-fg disabled:cursor-not-allowed disabled:opacity-40';

/** Elevated panel: the workhorse surface of the workspace. */
export const panel =
  'rounded-card border border-border bg-primary shadow-tinted';
