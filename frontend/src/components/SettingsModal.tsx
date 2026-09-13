import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import type { HealthStatus } from '../types';
import { Field, Spinner, buttonGhost, buttonPrimary, inputClass } from './ui';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiUrl: string;
  apiKey: string;
  onSave: (settings: { apiUrl: string; apiKey: string }) => void;
}

/** API URL + API key modal. Escape closes; Enter in a field saves. */
const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  apiUrl,
  apiKey,
  onSave,
}) => {
  const [draft, setDraft] = useState({ apiUrl, apiKey });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<HealthStatus | null>(null);

  // Resync the draft whenever the modal is (re)opened.
  useEffect(() => {
    if (isOpen) {
      setDraft({ apiUrl, apiKey });
      setTestResult(null);
    }
  }, [isOpen, apiUrl, apiKey]);

  // Escape closes the modal.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${draft.apiUrl.replace(/\/$/, '')}/health`, {
        headers: draft.apiKey ? { Authorization: `Bearer ${draft.apiKey}` } : {},
      });
      setTestResult(res.ok ? 'connected' : 'disconnected');
    } catch {
      setTestResult('disconnected');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#02061799] px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      onMouseDown={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-card border border-border/50 bg-bg shadow-tinted">
        <div className="flex items-center justify-between border-b border-border/30 px-4 py-3">
          <h2 className="font-display text-[13px] font-semibold text-fg">Settings</h2>
          <button type="button" onClick={onClose} aria-label="Close settings" className="inline-flex h-7 w-7 items-center justify-center rounded-md text-fg/50 transition-tool hover:bg-surface-hi hover:text-fg focus-visible:outline-2 focus-visible:outline-accent">
            <X size={15} />
          </button>
        </div>

        <form
          className="space-y-4 px-4 py-4"
          onSubmit={e => {
            e.preventDefault();
            onSave(draft);
            onClose();
          }}
        >
          <Field label="API URL" htmlFor="settings-api-url">
            <div className="flex gap-2">
              <input
                id="settings-api-url"
                type="text"
                value={draft.apiUrl}
                onChange={e => setDraft({ ...draft, apiUrl: e.target.value })}
                className={inputClass}
                placeholder="http://127.0.0.1:8000"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => void testConnection()}
                disabled={testing}
                className={`${buttonGhost} shrink-0`}
              >
                {testing ? <Spinner /> : null}
                Test
              </button>
            </div>
            {testResult === 'connected' ? (
              <p className="mt-1 text-[12px] text-accent">Backend is healthy.</p>
            ) : testResult === 'disconnected' ? (
              <p className="mt-1 text-[12px] text-destructive">
                Could not reach the backend. Check the URL and that it is running.
              </p>
            ) : null}
          </Field>

          <Field
            label="API key"
            htmlFor="settings-api-key"
            hint="Sent as an Authorization: Bearer header on every data request."
          >
            <input
              id="settings-api-key"
              type="password"
              value={draft.apiKey}
              onChange={e => setDraft({ ...draft, apiKey: e.target.value })}
              className={`${inputClass} font-display`}
              placeholder="DATATALKER_API_KEY value"
              autoComplete="off"
            />
          </Field>

          <div className="flex justify-end gap-2 border-t border-border/30 pt-3">
            <button type="button" onClick={onClose} className={buttonGhost}>
              Cancel
            </button>
            <button type="submit" className={buttonPrimary}>
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SettingsModal;
