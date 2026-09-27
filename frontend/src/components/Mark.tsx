import React from 'react';

/** The product mark: a stacked cylinder drawn as one stroke path so it stays crisp at
 * any size and inherits the accent color instead of shipping an image. */
export const Mark: React.FC<{ size?: number; className?: string }> = ({
  size = 30,
  className = '',
}) => (
  <span
    className={`grid shrink-0 place-items-center rounded-[9px] ${className}`}
    style={{
      width: size,
      height: size,
      background: 'var(--color-accent)',
      color: 'var(--color-accent-ink)',
    }}
  >
    <svg
      viewBox="0 0 24 24"
      width={size * 0.62}
      height={size * 0.62}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      aria-hidden
    >
      <path d="M5 7.5c0-1.4 3.1-2.5 7-2.5s7 1.1 7 2.5-3.1 2.5-7 2.5-7-1.1-7-2.5Z" />
      <path d="M5 7.5v9c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-9" />
      <path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" />
    </svg>
  </span>
);

export const Wordmark: React.FC<{ sub?: string; size?: number }> = ({
  sub = 'data analyst',
  size,
}) => (
  <span className="flex min-w-0 items-center gap-2.5">
    <Mark size={size} />
    <span className="min-w-0">
      <span className="block truncate font-display text-[15px] font-semibold leading-none tracking-tight">
        DataTalker
      </span>
      {sub ? (
        <span
          className="mt-1 block font-code text-[9px] uppercase tracking-[0.16em]"
          style={{ color: 'var(--color-faint)' }}
        >
          {sub}
        </span>
      ) : null}
    </span>
  </span>
);
