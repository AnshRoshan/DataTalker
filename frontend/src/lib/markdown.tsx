import type { ReactNode } from 'react';

/**
 * Minimal, safe markdown rendering for answer text: paragraphs, **bold**,
 * and `inline code`. Everything else renders as plain text. No HTML injection:
 * output is React elements built from split strings.
 */

type Segment = { text: string; bold?: boolean; code?: boolean };

function parseInline(line: string): Segment[] {
  const segments: Segment[] = [];
  // Split on `code` first, then **bold** within the plain parts.
  const codeParts = line.split(/`([^`]*)`/g);
  codeParts.forEach((part, i) => {
    const isCode = i % 2 === 1;
    if (isCode) {
      if (part) segments.push({ text: part, code: true });
      return;
    }
    const boldParts = part.split(/\*\*([^*]+)\*\*/g);
    boldParts.forEach((bp, j) => {
      if (!bp) return;
      segments.push({ text: bp, bold: j % 2 === 1 });
    });
  });
  return segments;
}

function renderInline(line: string, keyPrefix: string): ReactNode[] {
  return parseInline(line).map((seg, i) => {
    const key = `${keyPrefix}-${i}`;
    if (seg.code) {
      return (
        <code
          key={key}
          className="rounded-md bg-surface px-1 py-0.5 font-display text-[12px] text-accent"
        >
          {seg.text}
        </code>
      );
    }
    if (seg.bold) {
      return (
        <strong key={key} className="font-semibold text-fg">
          {seg.text}
        </strong>
      );
    }
    return <span key={key}>{seg.text}</span>;
  });
}

/** Render a markdown-ish answer string as React elements. */
export function renderMarkdown(text: string): ReactNode[] {
  const paragraphs = text
    .split(/\n{2,}|\r\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean);
  return paragraphs.map((para, pIndex) => {
    // Treat single-newline groups inside a paragraph as a list when most
    // lines start with -, * or a digit-dot marker.
    const lines = para.split(/\n|\r\n/).map(l => l.trim()).filter(Boolean);
    const isList =
      lines.length > 1 &&
      lines.filter(l => /^([-*]|\d+\.)\s+/.test(l)).length >= Math.ceil(lines.length / 2);
    if (isList) {
      return (
        <ul key={`p-${pIndex}`} className="my-1.5 space-y-1 pl-1">
          {lines.map((line, lIndex) => (
            <li key={lIndex} className="flex gap-2">
              <span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-fg/40" />
              <span>
                {renderInline(line.replace(/^([-*]|\d+\.)\s+/, ''), `p${pIndex}-l${lIndex}`)}
              </span>
            </li>
          ))}
        </ul>
      );
    }
    return (
      <p key={`p-${pIndex}`} className="my-1.5 first:mt-0 last:mb-0">
        {lines.map((line, lIndex) => (
          <span key={lIndex}>
            {renderInline(line, `p${pIndex}-l${lIndex}`)}
            {lIndex < lines.length - 1 ? ' ' : null}
          </span>
        ))}
      </p>
    );
  });
}
