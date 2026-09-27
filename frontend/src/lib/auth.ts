/** Google sign-in client.
 *
 * The browser never talks to Google with our secret — it gets an ID token from
 * Google Identity Services and posts it to /auth/google, which verifies it against
 * Google's keys and answers with a signed session cookie. Everything here is
 * decoration around that exchange; if the server reports Google is not configured,
 * the caller renders no button at all rather than a broken one.
 */

export interface AuthUser {
  email: string;
  name: string;
  picture: string;
}

export interface AuthConfig {
  google_enabled: boolean;
  client_id: string | null;
  require_login: boolean;
  api_key_required: boolean;
}

const GSI_SRC = 'https://accounts.google.com/gsi/client';

interface GsiId {
  initialize(config: {
    client_id: string;
    callback: (response: { credential: string }) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: { theme?: string; size?: string; text?: string; shape?: string; width?: number },
  ): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GsiId } };
  }
}

const base = (apiUrl: string) => apiUrl.replace(/\/$/, '');

/** Session cookies are same-origin only. Sending them cross-origin (the split Vite dev
 * server on :5173 against the API on :8000) fails CORS with credentials and would break
 * every request, so the browser simply doesn't attach them there. */
const credentials = (apiUrl: string): RequestCredentials => {
  try {
    return new URL(base(apiUrl), window.location.href).origin === window.location.origin
      ? 'include'
      : 'omit';
  } catch {
    return 'omit';
  }
};

const opts = (apiUrl: string, init: RequestInit = {}): RequestInit => ({
  ...init,
  credentials: credentials(apiUrl),
});

export async function fetchAuthConfig(apiUrl: string): Promise<AuthConfig> {
  const res = await fetch(`${base(apiUrl)}/auth/config`, opts(apiUrl));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as AuthConfig;
}

export async function fetchMe(apiUrl: string): Promise<AuthUser | null> {
  try {
    const res = await fetch(`${base(apiUrl)}/auth/me`, opts(apiUrl));
    if (!res.ok) return null;
    const body = (await res.json()) as { authenticated: boolean; user: AuthUser | null };
    return body.authenticated ? body.user : null;
  } catch {
    return null;
  }
}

export async function exchangeCredential(apiUrl: string, credential: string): Promise<AuthUser> {
  const res = await fetch(
    `${base(apiUrl)}/auth/google`,
    opts(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    }),
  );
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(data.detail || 'Sign-in was rejected.');
  }
  return (await res.json()) as AuthUser;
}

export async function signOut(apiUrl: string): Promise<void> {
  await fetch(`${base(apiUrl)}/auth/logout`, opts(apiUrl, { method: 'POST' })).catch(() => undefined);
}

let gsiPromise: Promise<GsiId> | null = null;

/** Load the GSI script once per page. Rejected if the network blocks it, which the
 * login screen surfaces instead of leaving a blank slot where the button belongs. */
export function loadGsi(): Promise<GsiId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (gsiPromise) return gsiPromise;
  gsiPromise = new Promise<GsiId>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = GSI_SRC;
    script.async = true;
    script.onload = () => {
      const id = window.google?.accounts?.id;
      if (id) resolve(id);
      else reject(new Error('Google Identity Services loaded without an ID client.'));
    };
    script.onerror = () => {
      gsiPromise = null;
      reject(new Error('Could not load Google sign-in. Check the network or an ad blocker.'));
    };
    document.head.appendChild(script);
  });
  return gsiPromise;
}
