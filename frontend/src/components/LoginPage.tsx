import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { exchangeCredential, fetchAuthConfig, loadGsi, type AuthConfig } from '../lib/auth';
import { navigate } from '../lib/router';
import { loadApiUrl } from '../lib/storage';
import { Link, Spinner } from './ui';
import { Mark } from './Mark';

/** Sign-in screen.
 *
 * Google hands the browser an ID token; we post it to /auth/google, which verifies it
 * server-side and sets a session cookie. Nothing here holds a secret — the client id is
 * public by design and comes from the server, so rotating configuration never means
 * rebuilding the frontend.
 */
const LoginPage: React.FC<{ onSignedIn: (user: { email: string; name: string; picture: string }) => void }> = ({
  onSignedIn,
}) => {
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const cfg = await fetchAuthConfig(loadApiUrl());
        if (cancelled) return;
        setConfig(cfg);
        if (!cfg.google_enabled) return;

        const gsi = await loadGsi();
        if (cancelled || !buttonRef.current) return;
        gsi.initialize({
          client_id: cfg.client_id as string,
          callback: async response => {
            setError(null);
            setStatus('Verifying with the server…');
            try {
              const user = await exchangeCredential(loadApiUrl(), response.credential);
              onSignedIn(user);
              navigate('/studio');
            } catch (err) {
              setStatus(null);
              setError(err instanceof Error ? err.message : 'Sign-in failed.');
            }
          },
        });
        gsi.renderButton(buttonRef.current, { theme: 'outline', size: 'large', text: 'continue_with', width: 300 });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not reach the server.');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onSignedIn]);

  return (
    <div
      className="grid-texture flex min-h-dvh flex-col items-center justify-center px-5 py-16"
      style={{ background: 'var(--color-bg)', color: 'var(--color-fg)' }}
    >
      <div className="w-full max-w-[400px]">
        <Link to="/" className="mb-8 inline-flex items-center gap-2 font-display text-[15px] font-semibold tracking-tight">
          <Mark size={28} /> DataTalker
        </Link>

        <div className="panel p-6">
          <h1 className="font-display text-[26px] leading-tight tracking-tight">Sign in</h1>
          <p className="mt-2 text-[13px] leading-6" style={{ color: 'var(--color-muted)' }}>
            Use your Google account to reach the studio. Identity is verified by this server against
            Google's keys; the session lives in an HttpOnly cookie for a week.
          </p>

          <div className="mt-6 flex min-h-[44px] items-center justify-center">
            {error ? (
              <p className="text-[12.5px]" style={{ color: 'var(--color-destructive)' }}>
                {error}
              </p>
            ) : status ? (
              <span className="inline-flex items-center gap-2 text-[12.5px]" style={{ color: 'var(--color-muted)' }}>
                <Spinner /> {status}
              </span>
            ) : config && !config.google_enabled ? (
              <p className="text-[12.5px]" style={{ color: 'var(--color-muted)' }}>
                Google sign-in is not configured on this instance. Set{' '}
                <code className="font-code text-[11.5px]" style={{ color: 'var(--color-accent)' }}>
                  DATATALKER_GOOGLE_CLIENT_ID
                </code>{' '}
                to enable it.
              </p>
            ) : (
              <div ref={buttonRef} />
            )}
          </div>

          <div
            className="mt-6 flex items-start gap-2.5 border-t pt-4 text-[12px] leading-5"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-faint)' }}
          >
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" style={{ color: 'var(--color-success)' }} />
            <p>
              Signing in gates who may use this instance. It does not yet partition data between users —
              saved connections are shared, so run it that way only for people who trust each other.
            </p>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between text-[12.5px]">
          <Link to="/" className="inline-flex items-center gap-1.5 transition-colors hover:text-[var(--color-fg)]" style={{ color: 'var(--color-muted)' }}>
            <ArrowLeft className="size-3.5" /> Back to site
          </Link>
          <Link to="/studio" className="transition-colors hover:text-[var(--color-fg)]" style={{ color: 'var(--color-muted)' }}>
            Continue without an account
          </Link>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
