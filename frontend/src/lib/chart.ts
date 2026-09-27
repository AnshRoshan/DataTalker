/** Result-set column classification for the charts, kept out of the component so a
 * caller can decide whether to offer a chart without rendering one. */

export type Row = Record<string, unknown>;

const isNumeric = (v: unknown): v is number => {
  if (typeof v === 'number') return Number.isFinite(v);
  if (typeof v === 'string' && v.trim() !== '' && !isNaN(Number(v))) return true;
  return false;
};

/** First all-numeric column set plus a label column, or null when nothing is plottable. */
export function classify(rows: Row[]): { numeric: string[]; labelKey: string } | null {
  if (rows.length === 0) return null;
  const keys = Object.keys(rows[0]);
  const numeric = keys.filter(
    k => rows.some(r => isNumeric(r[k])) && rows.every(r => r[k] == null || isNumeric(r[k])),
  );
  if (numeric.length === 0) return null;
  return { numeric, labelKey: keys.find(k => !numeric.includes(k)) ?? keys[0] };
}

export function hasPlottableColumn(rows: Row[]): boolean {
  return classify(rows) !== null;
}

export function toNumber(v: unknown): number {
  return typeof v === 'number' ? v : Number(v);
}
