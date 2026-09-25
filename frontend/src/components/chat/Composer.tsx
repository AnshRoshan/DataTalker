import React, { useEffect, useRef, useState } from 'react';
import { Send, Square } from 'lucide-react';
import { dbRefLabel } from '../../lib/format';
import type { ActiveDbRef } from '../../types';
import { StatusDot } from '../ui';

interface ComposerProps {
  /** Send on Enter, newline on Shift+Enter. */
  onSend: (question: string) => void;
  onCancel: () => void;
  isLoading: boolean;
  dbRef: ActiveDbRef | null;
  refOk: boolean | null;
  onGoToConnections: () => void;
}

/** The chat input: auto-growing textarea, Enter to send, Shift+Enter newline. */
const Composer: React.FC<ComposerProps> = ({ onSend, onCancel, isLoading, dbRef, refOk, onGoToConnections }) => {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep the textarea height in step with its content (up to ~6 rows).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue('');
  };

  return (
    <div className="shrink-0 px-4 pb-4 pt-2">
      <form
        onSubmit={e => {
          e.preventDefault();
          submit();
        }}
        className="mx-auto w-full max-w-3xl"
      >
        <div className="flex items-end gap-2 rounded-card border border-border-strong bg-surface p-2 shadow-tinted transition-tool focus-within:border-accent/60 focus-within:shadow-glow">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Ask a question about your data..."
            aria-label="Question"
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[14px] text-fg placeholder:text-faint"
          />
          {isLoading ? (
            <button
              type="button"
              onClick={onCancel}
              aria-label="Cancel request"
              title="Cancel request"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-input border border-border-strong text-fg/70 transition-tool hover:border-destructive/60 hover:text-destructive focus-visible:outline-2 focus-visible:outline-accent"
            >
              <Square size={13} strokeWidth={2.2} />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!value.trim()}
              aria-label="Send question"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-input bg-accent text-[#053B26] shadow-tinted-sm transition-tool hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-accent"
            >
              <Send size={15} strokeWidth={2} />
            </button>
          )}
        </div>
        <div className="mx-auto mt-2 flex w-full max-w-3xl flex-wrap items-center justify-between gap-x-3 px-1">
          <p className="text-[11px] text-faint">
            Enter to send, Shift+Enter for a new line
          </p>
          {dbRef ? (
            <p className="flex items-center gap-1.5 text-[11px] text-muted">
              <StatusDot tone={refOk === null ? 'unknown' : refOk ? 'ok' : 'error'} />
              {dbRefLabel(dbRef)}
            </p>
          ) : (
            <button
              type="button"
              onClick={onGoToConnections}
              className="text-[11px] text-muted underline decoration-dotted underline-offset-2 transition-tool hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
            >
              Attach a database first
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default Composer;
