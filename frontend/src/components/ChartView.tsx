import React, { useMemo, useState } from 'react';
import { classify, toNumber, type Row } from '../lib/chart';

/** Result charts without a charting dependency.
 *
 * A chart library is ~100KB gzipped to draw what this SVG draws, and the shapes a query
 * result can take are few: a category axis plus one numeric column. So this reads the
 * rows (classification lives in lib/chart so callers can hide the control when nothing
 * is plottable), offers the numeric columns it found, and renders bars — or a line once
 * there are enough points that bars turn to noise.
 */
const ChartView: React.FC<{ rows: Row[]; height?: number }> = ({ rows, height = 190 }) => {
  const shape = useMemo(() => classify(rows), [rows]);
  const [valueKey, setValueKey] = useState<string | null>(null);

  if (!shape || rows.length === 0) return null;

  const key = valueKey && shape.numeric.includes(valueKey) ? valueKey : shape.numeric[0];
  const points = rows
    .map((r, i) => ({
      label: String(r[shape.labelKey] ?? `#${i + 1}`),
      value: toNumber(r[key]) || 0,
    }))
    .slice(0, 40);

  const max = Math.max(...points.map(p => Math.abs(p.value)), 1);
  const width = 640;
  const pad = { left: 8, right: 8, top: 12, bottom: 26 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const bandW = plotW / Math.max(points.length, 1);
  const barW = Math.max(4, Math.min(38, bandW * 0.62));
  const showLine = points.length > 12;
  const yOf = (v: number) => pad.top + plotH - (Math.abs(v) / max) * plotH;
  const xOf = (i: number) => pad.left + bandW * (i + 0.5);

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${xOf(i).toFixed(1)},${yOf(p.value).toFixed(1)}`).join(' ');

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="label">chart · {key}</span>
        {shape.numeric.length > 1 ? (
          <select
            aria-label="Chart column"
            value={key}
            onChange={e => setValueKey(e.target.value)}
            className="field h-7 w-auto py-0 text-[11.5px]"
          >
            {shape.numeric.map(k => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`Chart of ${key} across ${points.length} rows`}
      >
        <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} stroke="var(--color-border)" />
        {showLine ? (
          <>
            <path d={linePath} fill="none" stroke="var(--color-accent)" strokeWidth="1.8" />
            {points.map((p, i) => (
              <circle key={`${p.label}-${i}`} cx={xOf(i)} cy={yOf(p.value)} r="2.4" fill="var(--color-accent)" />
            ))}
          </>
        ) : (
          points.map((p, i) => {
            const h = (Math.abs(p.value) / max) * plotH;
            return (
              <rect
                key={`${p.label}-${i}`}
                x={pad.left + bandW * i + (bandW - barW) / 2}
                y={pad.top + plotH - h}
                width={barW}
                height={Math.max(h, 1)}
                rx="2"
                fill="var(--color-accent)"
                opacity={i === points.length - 1 ? 1 : 0.62}
              >
                <title>{`${p.label}: ${p.value}`}</title>
              </rect>
            );
          })
        )}
        {points.map((p, i) =>
          i % Math.ceil(points.length / 8 || 1) === 0 ? (
            <text
              key={`l-${p.label}-${i}`}
              x={xOf(i)}
              y={height - 8}
              textAnchor="middle"
              fontSize="9"
              fontFamily="var(--font-code)"
              fill="var(--color-faint)"
            >
              {p.label.length > 10 ? `${p.label.slice(0, 9)}…` : p.label}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
};

export default ChartView;
