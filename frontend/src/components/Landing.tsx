import React, { useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, Moon, ShieldCheck, Sun, X } from 'lucide-react';
import { Link } from './ui';
import { Mark } from './Mark';
import type { Theme } from '../lib/theme';

/* Every number, query and verdict below was run against the bundled hospital.db
   fixture and the live validator — the page makes no claim the code does not keep. */

const DEMOS = [
  {
    tag: 'count',
    question: 'How many patients are on file?',
    sql: 'SELECT COUNT(*) AS patients\nFROM patients;',
    answer: 'There are 5 patients registered in the hospital database.',
    bars: [5],
    labels: ['patients'],
  },
  {
    tag: 'join',
    question: 'Which department handles the most appointments?',
    sql:
      'SELECT d.name AS department,\n       COUNT(a.appointment_id) AS appointments\nFROM appointments a\nJOIN doctors doc ON doc.doctor_id = a.doctor_id\nJOIN departments d ON d.department_id = doc.department_id\nGROUP BY 1\nORDER BY 2 DESC;',
    answer: 'All five departments carry 2 appointments each — the load is evenly spread.',
    bars: [2, 2, 2, 2, 2],
    labels: ['peds', 'ortho', 'onco', 'neuro', 'cardio'],
  },
  {
    tag: 'preview',
    question: 'What medications do we stock?',
    sql: 'SELECT name, description\nFROM medications\nLIMIT 5;',
    answer: 'Aspirin, Metoprolol, Paracetamol and Ibuprofen are among the 10 stocked entries.',
    bars: [10],
    labels: ['medications'],
  },
];

const PIPELINE = [
  { input: 'DROP TABLE departments', verdict: 'blocked', reason: 'only read-only SELECT/WITH allowed' },
  { input: 'SELECT 1; DELETE FROM users', verdict: 'blocked', reason: 'only a single statement is allowed' },
  { input: "SELECT pg_read_file('/etc/passwd')", verdict: 'blocked', reason: 'query uses a disallowed function' },
  { input: 'SELECT name FROM patients', verdict: 'allowed', reason: 'a single read-only query' },
];

const CAPABILITIES = [
  {
    title: 'Schema reflection, not guesswork',
    body: 'Tables, columns, keys and foreign keys are read live with SQLAlchemy. A graph of joins is built from them, so a question about two tables finds the path between them.',
    meta: 'introspection',
  },
  {
    title: 'Big schemas stay workable',
    body: 'Past 25 tables the schema is scored against your question and pruned to the relevant subset plus its join neighbours. Hundreds of tables do not blow the prompt.',
    meta: 'retrieval',
  },
  {
    title: 'Any database you can name',
    body: 'SQLite, PostgreSQL and MySQL built in; SQL Server, Oracle and Snowflake through optional drivers. Attach by upload, server path, URL or a saved connection that is preflighted first.',
    meta: 'dialects',
  },
  {
    title: 'Bring your own model key',
    body: 'Gemini, OpenRouter or any OpenAI-compatible endpoint. Paste it in Settings and it travels as a request header — the server holds it for that request alone and never writes it down.',
    meta: 'byok',
  },
  {
    title: 'Governance and a glossary',
    body: 'Optional table allowlist with column masking (full, partial or hashed), plus a YAML semantic layer so the model sees what your analysts call revenue.',
    meta: 'controls',
  },
  {
    title: 'Everything is written down',
    body: 'Each question, the SQL it produced, the verdict, the row count and the latency are appended to an audit log. Per-IP rate limiting sits in front of the paid path.',
    meta: 'audit',
  },
];

const Landing: React.FC<{ theme: Theme; onToggleTheme: () => void }> = ({
  theme,
  onToggleTheme,
}) => {
  const [active, setActive] = useState(0);
  const demo = DEMOS[active];
  const max = Math.max(...demo.bars);

  return (
    <div className="min-h-dvh" style={{ background: 'var(--color-bg)', color: 'var(--color-fg)' }}>
      <header
        className="sticky top-0 z-40"
        style={{
          background: 'color-mix(in srgb, var(--color-bg) 84%, transparent)',
          borderBottom: '1px solid var(--color-border)',
          backdropFilter: 'blur(14px)',
        }}
      >
        <div className="mx-auto flex h-16 max-w-[1100px] items-center gap-4 px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <Mark size={32} />
            <span className="font-display text-[16px] font-semibold tracking-tight">DataTalker</span>
          </Link>

          <nav className="ml-6 hidden items-center gap-6 text-[12.5px] md:flex" style={{ color: 'var(--color-muted)' }}>
            <a href="#product" className="transition-colors hover:text-[var(--color-fg)]">
              Product
            </a>
            <a href="#capabilities" className="transition-colors hover:text-[var(--color-fg)]">
              Capabilities
            </a>
            <a href="#safety" className="transition-colors hover:text-[var(--color-fg)]">
              Safety
            </a>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <button onClick={onToggleTheme} className="btn btn-secondary size-9 p-0" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <Link to="/login" className="btn btn-ghost h-9 hidden sm:inline-flex">
              Sign in
            </Link>
            <Link to="/studio" className="btn btn-primary h-9">
              Open the studio <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <section id="product" className="mx-auto max-w-[1100px] px-5 pb-16 pt-16 lg:pt-24">
        <div className="grid items-start gap-12 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <span
              className="tag"
              style={{ borderColor: 'var(--color-accent-line)', color: 'var(--color-accent)' }}
            >
              <span className="size-1.5 rounded-full" style={{ background: 'var(--color-accent)' }} />
              read-only natural language sql
            </span>

            <h1 className="font-display mt-5 text-[44px] leading-[1.03] tracking-tight sm:text-[62px]">
              Your database,
              <br />
              in <span style={{ color: 'var(--color-accent)' }}>plain English</span>.
            </h1>

            <p className="mt-5 max-w-[460px] text-[15px] leading-7" style={{ color: 'var(--color-muted)' }}>
              Ask the question you would ask a colleague. DataTalker reflects your schema, writes one
              guarded SELECT, runs it read-only, and answers with prose, the SQL and the rows — so you
              can check the work.
            </p>

            <div className="mt-7 flex flex-wrap items-center gap-2.5">
              <Link to="/studio" className="btn btn-primary h-11 px-5 text-[13.5px]">
                Open the studio <ArrowRight className="size-4" />
              </Link>
              <Link to="/login" className="btn btn-secondary h-11 px-5 text-[13.5px]">
                Sign in
              </Link>
            </div>

            <dl
              className="mt-10 grid max-w-[460px] grid-cols-3 gap-4"
              style={{ borderTop: '1px solid var(--color-border)', paddingTop: 20 }}
            >
              {[
                ['3', 'dialects built in'],
                ['25', 'checks on the pipeline'],
                ['0', 'writes, ever'],
              ].map(([value, key]) => (
                <div key={key}>
                  <dt className="font-display text-[28px] leading-none tabular">{value}</dt>
                  <dd
                    className="mt-1.5 font-code text-[10px] uppercase tracking-[0.12em]"
                    style={{ color: 'var(--color-faint)' }}
                  >
                    {key}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="panel overflow-hidden">
            <div
              className="flex items-center gap-2 px-3 py-2.5"
              style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
            >
              <span className="size-2 rounded-full" style={{ background: 'var(--color-destructive)', opacity: 0.7 }} />
              <span className="size-2 rounded-full" style={{ background: 'var(--color-warn)', opacity: 0.7 }} />
              <span className="size-2 rounded-full" style={{ background: 'var(--color-success)', opacity: 0.7 }} />
              <span className="ml-1 font-code text-[10.5px]" style={{ color: 'var(--color-faint)' }}>
                hospital.db · sqlite
              </span>
              <span
                className="tag ml-auto"
                style={{ color: 'var(--color-success)', borderColor: 'color-mix(in srgb, var(--color-success) 30%, transparent)' }}
              >
                read only
              </span>
            </div>

            <div className="flex gap-1 px-3 pt-3">
              {DEMOS.map((d, i) => (
                <button
                  key={d.tag}
                  onClick={() => setActive(i)}
                  className="rounded-md px-2.5 py-1 font-code text-[10px] uppercase tracking-wider transition-colors"
                  style={{
                    background: i === active ? 'var(--color-accent)' : 'transparent',
                    color: i === active ? 'var(--color-accent-ink)' : 'var(--color-faint)',
                    border: `1px solid ${i === active ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  }}
                >
                  {d.tag}
                </button>
              ))}
            </div>

            <div className="space-y-3.5 p-4">
              <div className="flex justify-end">
                <p
                  className="max-w-[88%] rounded-xl rounded-br-[4px] px-3 py-2 text-[13px] leading-6"
                  style={{ background: 'var(--color-accent-soft)', border: '1px solid var(--color-accent-line)' }}
                >
                  {demo.question}
                </p>
              </div>

              <div className="rounded-xl p-3" style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}>
                <span className="label">generated sql</span>
                <pre
                  className="mt-2 overflow-x-auto font-code text-[11px] leading-[1.75]"
                  style={{ color: 'var(--color-muted)' }}
                >
                  {demo.sql}
                </pre>
              </div>

              <div
                className="rounded-xl p-3"
                style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
              >
                <p className="text-[13px] leading-6">{demo.answer}</p>
                <div className="mt-3 flex h-20 items-end gap-1.5">
                  {demo.bars.map((bar, i) => (
                    <div key={`${demo.tag}-${i}`} className="flex flex-1 flex-col items-center gap-1">
                      <div
                        className="w-full rounded-t-[3px] transition-all duration-500"
                        style={{
                          height: `${(bar / max) * 100}%`,
                          background: bar === max ? 'var(--color-accent)' : 'var(--color-border-strong)',
                        }}
                      />
                      <span className="font-code text-[8.5px]" style={{ color: 'var(--color-faint)' }}>
                        {demo.labels[i]}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        id="capabilities"
        className="mx-auto max-w-[1100px] border-t px-5 py-16"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="label">what it does</span>
            <h2 className="font-display mt-2 max-w-[540px] text-[34px] leading-tight tracking-tight sm:text-[42px]">
              Built for the moment someone asks you for a number.
            </h2>
          </div>
          <Link to="/studio" className="btn btn-secondary h-9">
            See it live <ArrowUpRight className="size-3.5" />
          </Link>
        </div>

        <div className="divide-hair mt-10" style={{ borderTop: '1px solid var(--color-border)' }}>
          {CAPABILITIES.map((c, i) => (
            <div key={c.title} className="grid gap-2 py-5 sm:grid-cols-[28px_1fr_200px] sm:gap-6">
              <span className="font-code text-[11px] tabular" style={{ color: 'var(--color-faint)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div>
                <h3 className="text-[15px] font-semibold tracking-tight">{c.title}</h3>
                <p className="mt-1.5 max-w-[540px] text-[13.5px] leading-6" style={{ color: 'var(--color-muted)' }}>
                  {c.body}
                </p>
              </div>
              <span className="label self-start sm:justify-self-end">{c.meta}</span>
            </div>
          ))}
        </div>
      </section>

      <section
        id="safety"
        className="mx-auto max-w-[1100px] border-t px-5 py-16"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <span className="label">the guarantee</span>
            <h2 className="font-display mt-2 text-[34px] leading-tight tracking-tight sm:text-[42px]">
              Nothing writes.
              <br />
              Nothing leaks.
            </h2>
            <p className="mt-4 max-w-[440px] text-[14px] leading-7" style={{ color: 'var(--color-muted)' }}>
              Safety is not a line in a prompt. It is a deterministic pipeline that runs after the model
              and before your database, so a hallucinated or injected statement still cannot mutate a row.
            </p>
            <ul className="mt-6 space-y-2.5">
              {[
                'Single statement only — no chained queries, no semicolons',
                'Only SELECT and WITH … SELECT reach the engine',
                'SQLite engines are pinned query_only; server dialects get a statement timeout',
                'Hard row cap applied to every result set',
                'Connection strings are never echoed back to a client',
              ].map(line => (
                <li key={line} className="flex items-start gap-2.5 text-[13.5px] leading-6" style={{ color: 'var(--color-muted)' }}>
                  <Check className="mt-1 size-3.5 shrink-0" style={{ color: 'var(--color-accent)' }} />
                  {line}
                </li>
              ))}
            </ul>
          </div>

          <div className="panel p-4">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck className="size-4" style={{ color: 'var(--color-success)' }} />
              <span className="label">pipeline replay</span>
              <span className="tag ml-auto" style={{ color: 'var(--color-success)' }}>
                3 blocked · 1 allowed
              </span>
            </div>
            <div className="space-y-1.5">
              {PIPELINE.map(row => {
                const ok = row.verdict === 'allowed';
                return (
                  <div
                    key={row.input}
                    className="rounded-lg p-3"
                    style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}
                  >
                    <div className="flex items-center gap-2">
                      {ok ? (
                        <Check className="size-3.5 shrink-0" style={{ color: 'var(--color-success)' }} />
                      ) : (
                        <X className="size-3.5 shrink-0" style={{ color: 'var(--color-destructive)' }} />
                      )}
                      <code className="min-w-0 flex-1 truncate font-code text-[11.5px]">{row.input}</code>
                    </div>
                    <p
                      className="mt-1.5 pl-5 font-code text-[10.5px]"
                      style={{ color: ok ? 'var(--color-success)' : 'var(--color-destructive)' }}
                    >
                      {row.verdict} · {row.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1100px] px-5 pb-20 pt-4">
        <div
          className="relative overflow-hidden rounded-2xl px-6 py-14 text-center sm:px-12"
          style={{ border: '1px solid var(--color-border)', background: 'var(--color-primary)' }}
        >
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px overflow-hidden">
            <span className="scanline block h-px w-1/3" style={{ background: 'var(--color-accent)' }} />
          </div>
          <h2 className="font-display mx-auto max-w-[560px] text-[34px] leading-tight tracking-tight sm:text-[44px]">
            Stop writing the same five queries.
          </h2>
          <p className="mx-auto mt-4 max-w-[460px] text-[14px] leading-7" style={{ color: 'var(--color-muted)' }}>
            A demo hospital database ships inside the image. Ask it something, then attach your own
            database and keep going.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-2.5">
            <Link to="/studio" className="btn btn-primary h-11 px-5 text-[13.5px]">
              Open the studio <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-[1100px] border-t px-5 pb-10" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-4 pt-6">
          <span className="font-code text-[10.5px] uppercase tracking-[0.14em]" style={{ color: 'var(--color-faint)' }}>
            DataTalker — read-only natural language sql
          </span>
          <div className="flex items-center gap-5 text-[12px]" style={{ color: 'var(--color-faint)' }}>
            <Link to="/studio" className="transition-colors hover:text-[var(--color-fg)]">
              Studio
            </Link>
            <a
              href="https://github.com/AnshRoshan/DataTalker"
              target="_blank"
              rel="noreferrer"
              className="transition-colors hover:text-[var(--color-fg)]"
            >
              Source
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
