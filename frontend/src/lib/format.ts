/** Formatting helpers shared across views. */

/** Relative time ("just now", "4m ago", "2h ago", "Sep 12") from an ISO string. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'never';
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 15) return 'just now';
  if (seconds < 90) return '1m ago';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(then).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

/** Latency in a compact, monospace-friendly form. */
export function formatLatency(ms: number | undefined): string | null {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Human label for a quick-attach / active DB reference. */
export function dbRefLabel(ref: {
  kind: string;
  name?: string;
  path?: string;
  connectionString?: string;
}): string {
  if (ref.kind === 'connection') return ref.name ?? 'connection';
  if (ref.kind === 'file') return ref.name ?? 'uploaded file';
  if (ref.kind === 'path') {
    const p = ref.path ?? '';
    const base = p.split(/[\\/]/).pop();
    return base || p;
  }
  if (ref.kind === 'string') {
    const s = ref.connectionString ?? '';
    try {
      const u = new URL(s.replace(/^sqlite:\//, 'file:').replace(/^mysql/, 'http').replace(/^postgres/, 'http'));
      return u.pathname.replace(/^\//, '') || s;
    } catch {
      return s.length > 40 ? `${s.slice(0, 40)}...` : s;
    }
  }
  return 'database';
}
