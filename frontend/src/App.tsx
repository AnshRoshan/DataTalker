import React, { useCallback, useEffect, useState } from 'react';
import Landing from './components/Landing';
import LoginPage from './components/LoginPage';
import Workspace from './components/Workspace';
import { fetchAuthConfig, fetchMe, type AuthConfig, type AuthUser } from './lib/auth';
import { loadApiUrl } from './lib/storage';
import { applyTheme, loadTheme, type Theme } from './lib/theme';
import { navigate, usePath } from './lib/router';

/** Three surfaces, one document: the public page, the sign-in screen, the workspace. */
const App: React.FC = () => {
  const path = usePath();
  const [theme, setTheme] = useState<Theme>(() => loadTheme());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    const apiUrl = loadApiUrl();
    let cancelled = false;
    void Promise.all([
      fetchAuthConfig(apiUrl).catch(() => null),
      fetchMe(apiUrl),
    ]).then(([cfg, who]) => {
      if (cancelled) return;
      setConfig(cfg);
      setUser(who);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleTheme = useCallback(() => setTheme(t => (t === 'dark' ? 'light' : 'dark')), []);

  const handleSignedIn = useCallback((signedIn: AuthUser) => {
    setUser(signedIn);
    navigate('/studio');
  }, []);

  if (path === '/login') {
    return <LoginPage onSignedIn={handleSignedIn} />;
  }

  // When the server requires an identity, the workspace is not rendered at all — the
  // data routes would 401 anyway, and a half-loaded screen is a worse answer than the
  // sign-in page.
  if (path !== '/studio' || (config?.require_login && !user)) {
    return <Landing theme={theme} onToggleTheme={toggleTheme} />;
  }

  return (
    <Workspace
      user={user}
      googleEnabled={Boolean(config?.google_enabled)}
      onSignedOut={() => setUser(null)}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  );
};

export default App;
