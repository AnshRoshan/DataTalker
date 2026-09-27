import { useSyncExternalStore } from 'react';

/** A ~30 line router. The app has three surfaces (/ /login /studio); pulling in a
 * routing library for that would cost more than it saves. The server serves
 * index.html for any path it does not claim, so pushState links survive a refresh. */

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach(l => l());
}

export function navigate(to: string): void {
  if (to === window.location.pathname + window.location.search) return;
  window.history.pushState({}, '', to);
  emit();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onPop = () => listener();
  window.addEventListener('popstate', onPop);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('popstate', onPop);
  };
}

export function usePath(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname);
}
