import React, { useState } from 'react';
import { Check, ChevronRight, Copy } from 'lucide-react';
import type { ChatMessageData } from '../../types';
import { formatLatency } from '../../lib/format';
import { renderMarkdown } from '../../lib/markdown';
import ResultsTable from '../ResultsTable';

/** Collapsible SQL block: deeper-than-surface code panel with a header row. */
const SqlBlock: React.FC<{ sql: string }> = ({ sql }) => {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable; nothing sensible to do.
    }
  };

  return (
    <div className="mt-3.5 overflow-hidden rounded-lg border border-border bg-bg/70">
      <div className="flex items-center justify-between bg-surface/60 px-2.5 py-1.5">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
          className="flex items-center gap-1 font-code text-[11px] uppercase tracking-wide text-muted transition-tool hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
        >
          <ChevronRight
            size={13}
            className={`transition-tool ${open ? 'rotate-90' : ''}`}
            aria-hidden
          />
          SQL
        </button>
        <button
          type="button"
          onClick={() => void copy()}
          aria-label="Copy SQL to clipboard"
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-faint transition-tool hover:bg-surface-hi hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
        >
          {copied ? <Check size={13} className="text-accent" /> : <Copy size={13} />}
        </button>
      </div>
      {open && (
        <pre className="overflow-x-auto px-3.5 py-3 font-code text-[12px] leading-relaxed text-fg/90">
          <code>{sql}</code>
        </pre>
      )}
    </div>
  );
};

const TypingRow: React.FC = () => (
  <div className="flex items-center gap-1.5 px-1 py-2" aria-live="polite" aria-label="Waiting for answer">
    <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-accent" />
    <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-accent" />
    <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-accent" />
  </div>
);

const FollowUpChip: React.FC<{ question: string; onClick: (q: string) => void }> = ({
  question,
  onClick,
}) => (
  <button
    type="button"
    onClick={() => onClick(question)}
    className="rounded-full border border-border-strong bg-surface/50 px-3 py-1 text-left text-[12px] text-muted transition-tool hover:border-accent/50 hover:bg-surface-hi hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
  >
    {question}
  </button>
);

interface MessageCardProps {
  message: ChatMessageData;
  onFollowUpClick: (question: string) => void;
}

/** One conversation turn: user question right-aligned, answer as a clean card. */
const MessageCard: React.FC<MessageCardProps> = ({ message, onFollowUpClick }) => {
  const latency = formatLatency(message.latency_ms);
  const rowCount = Array.isArray(message.results) ? message.results.length : message.results ? 1 : 0;

  return (
    <article className="animate-msg-in">
      {/* User question: right-aligned accent-tinted bubble */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-xl rounded-br-sm bg-accent/12 px-3.5 py-2 text-[13.5px] text-fg">
          {message.question}
        </div>
      </div>

      {/* Answer card */}
      <div className="mt-2.5 rounded-card border border-border bg-primary px-4.5 py-3.5 shadow-tinted-sm">
        {message.isTyping ? (
          <TypingRow />
        ) : (
          <>
            <div className="text-[14px] leading-relaxed text-fg/90">
              {renderMarkdown(message.answer || 'No answer was returned.')}
            </div>

            {message.sql ? <SqlBlock sql={message.sql_executed || message.sql} /> : null}

            <ResultsTable results={message.results} />

            {message.results_truncated ? (
              <p className="mt-2 text-[11.5px] text-muted">
                Results were truncated at the server row cap
                {message.row_cap ? ` (${message.row_cap} rows)` : ''}. Download the CSV for the
                full returned set, or narrow the question.
              </p>
            ) : null}

            {message.follow_up_questions && message.follow_up_questions.length > 0 ? (
              <div className="mt-3.5">
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
                  Follow up
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {message.follow_up_questions.slice(0, 4).map(q => (
                    <FollowUpChip key={q} question={q} onClick={onFollowUpClick} />
                  ))}
                </div>
              </div>
            ) : null}

            {/* Meta line: small, muted, monospace */}
            <p className="mt-3 border-t border-border pt-2 font-code text-[10.5px] text-faint">
              {rowCount} {rowCount === 1 ? 'row' : 'rows'}
              {latency ? ` · ${latency}` : ''}
              {message.results_truncated ? ' · truncated' : ''}
            </p>
          </>
        )}
      </div>
    </article>
  );
};

export default MessageCard;
