/** Theme is a class on <html> so the CSS custom properties swap for everything,
 * including portals and React Flow, without threading state through components. */

export type Theme = 'dark' | 'light';

const THEME_KEY = 'datatalker.theme';

export function loadTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    /* private-mode browsers just get the default */
  }
  return 'dark';
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('light', theme === 'light');
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* best-effort */
  }
}
