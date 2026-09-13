import React, { useEffect, useRef } from 'react';
import { AlertCircle, BarChart3, Database, Sparkles, Table2, X } from 'lucide-react';
import type { ActiveDbRef, ChatMessageData } from '../../types';
import { dbRefLabel } from '../../lib/format';
import MessageCard from './MessageCard';
import Composer from './Composer';

interface ChatViewProps {
  messages: ChatMessageData[];
  isLoading: boolean;
  error: string | null;
  dbRef: ActiveDbRef | null;
  refOk: boolean | null;
  onSend: (question: string) => void;
  onCancel: () => void;
  onDismissError: () => void;
  onClearChat: () => void;
  onGoToConnections: () => void;
}

const EXAMPLES: { q: string; tag: string; Icon: typeof BarChart3 }[] = [
  { q: 'How many rows are in each table?', tag: 'Overview', Icon: Table2 },
  { q: 'Show me a sample of the largest table', tag: 'Explore', Icon: Database },
  { q: 'What are the top 5 values in the most populated column?', tag: 'Top N', Icon: BarChart3 },
  { q: 'Summarize what this database contains', tag: 'Summary', Icon: Sparkles },
];

/** The hero view: centered conversation column over a persistent composer. */
const ChatView: React.FC<ChatViewProps> = ({
  messages,
  isLoading,
  error,
  dbRef,
  refOk,
  onSend,
  onCancel,
  onDismissError,
  onClearChat,
  onGoToConnections,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastCountRef = useRef(messages.length);

  // Auto-scroll only when a message is added (not on every re-render).
  useEffect(() => {
    if (messages.length !== lastCountRef.current) {
      lastCountRef.current = messages.length;
      bottomRef.current?.scrollIntoView({ block: 'end' });
    }
  }, [messages.length]);

  const empty = messages.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {error ? (
        <div
          role="alert"
          className="mx-auto mt-3 flex w-full max-w-3xl items-start gap-2 rounded-card border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive"
        >
          <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden />
          <p className="flex-1">{error}</p>
          <button
            type="button"
            onClick={onDismissError}
            aria-label="Dismiss error"
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-tool hover:bg-destructive/20 focus-visible:outline-2 focus-visible:outline-accent"
          >
            <X size={13} />
          </button>
        </div>
      ) : null}

      {empty ? (
        <div className="flex flex-1 items-center justify-center overflow-y-auto px-4 py-8">
          <div className="w-full max-w-2xl animate-hero-in text-center [&>*]:max-w-full">
            {/* Glyph */}
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-primary shadow-tinted">
              <img src="/favicon.svg" alt="" width={30} height={30} />
            </div>

            <h1 className="font-display text-[26px] font-bold leading-tight tracking-tight text-fg text-balance sm:text-[30px]">
              {dbRef ? (
                <>
                  Ask <span className="text-accent">{dbRefLabel(dbRef)}</span> anything
                </>
              ) : (
                'Ask your data a question'
              )}
            </h1>
            <p className="mx-auto mt-2.5 max-w-md px-2 text-[14px] leading-relaxed text-muted">
              Plain English in. The answer, the SQL, and the rows out.{' '}
              {dbRef ? 'Try one of these to start.' : 'Connect a database to begin.'}
            </p>

            {dbRef ? (
              <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {EXAMPLES.map(({ q, tag, Icon }) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => onSend(q)}
                    className="group rounded-card border border-border bg-primary p-3.5 text-left transition-tool hover:border-accent/45 hover:bg-surface-hi/40 shadow-tinted-sm focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-faint transition-tool group-hover:text-accent">
                      <Icon size={13} strokeWidth={2} aria-hidden />
                      {tag}
                    </span>
                    <span className="mt-1.5 block text-[13.5px] leading-snug text-fg/85 transition-tool group-hover:text-fg">
                      {q}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="mt-8 rounded-card border border-border bg-primary p-5 text-left shadow-tinted">
                <ol className="space-y-3">
                  <li className="flex items-start gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/12 font-code text-[11px] font-medium text-accent">
                      1
                    </span>
                    <p className="text-[13.5px] text-fg/85">
                      Connect a database. SQLite file, PostgreSQL, MySQL, or any SQLAlchemy URL.
                    </p>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/12 font-code text-[11px] font-medium text-accent">
                      2
                    </span>
                    <p className="text-[13.5px] text-fg/85">
                      Ask in plain language. DataTalker writes read-only SQL and explains the result.
                    </p>
                  </li>
                </ol>
                <button
                  type="button"
                  onClick={onGoToConnections}
                  className="mt-4 w-full rounded-button bg-accent px-4 py-2.5 text-[13.5px] font-medium text-[#053B26] transition-tool hover:bg-accent-strong focus-visible:outline-2 focus-visible:outline-accent"
                >
                  Connect a database
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onClearChat}
                className="rounded-button px-2 py-1 text-[11px] text-faint transition-tool hover:text-fg/70 focus-visible:outline-2 focus-visible:outline-accent"
              >
                Clear chat
              </button>
            </div>
            {messages.map(m => (
              <MessageCard key={m.id} message={m} onFollowUpClick={onSend} />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>
      )}

      <Composer
        onSend={onSend}
        onCancel={onCancel}
        isLoading={isLoading}
        dbRef={dbRef}
        refOk={refOk}
        onGoToConnections={onGoToConnections}
      />
    </div>
  );
};

export default ChatView;
