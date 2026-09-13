import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { downloadCsv } from '../lib/csv';

interface ResultsTableProps {
  results: Record<string, unknown>[] | Record<string, unknown>;
}

const PAGE_SIZE = 50;

/** Render a cell value; objects/arrays are shown as JSON, nulls dimmed. */
const formatCellValue = (value: unknown): string => {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

interface PaginatedTableProps {
  title: React.ReactNode;
  headers: string[];
  rows: Record<string, unknown>[];
}

const PaginatedTable: React.FC<PaginatedTableProps> = ({ title, headers, rows }) => {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  // Clamp if the row count shrank (e.g. new results arrived) to avoid a dead page.
  const currentPage = Math.min(page, totalPages - 1);
  const startIndex = currentPage * PAGE_SIZE;
  const visibleRows = rows.slice(startIndex, startIndex + PAGE_SIZE);
  const hasMultiplePages = totalPages > 1;

  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[12px] text-fg/60">
          {title}
          <span className="font-display text-[11px] text-fg/40">
            {rows.length} {rows.length === 1 ? 'row' : 'rows'}
          </span>
        </p>
        <button
          type="button"
          onClick={() => downloadCsv('query-results.csv', headers, rows)}
          className="inline-flex items-center gap-1.5 rounded-button border border-border/50 px-2 py-1 text-[12px] text-fg/60 transition-tool hover:border-border hover:bg-surface/60 hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
          aria-label="Download results as CSV"
        >
          <Download size={13} strokeWidth={1.8} />
          CSV
        </button>
      </div>
      <div className="overflow-hidden rounded-card border border-border/40 shadow-tinted-sm">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border/40 bg-surface/50">
                {headers.map(key => (
                  <th
                    key={key}
                    scope="col"
                    className="whitespace-nowrap px-3 py-2 text-left font-display text-[11px] font-medium uppercase tracking-wide text-fg/60"
                  >
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, rowIndex) => (
                <tr
                  key={startIndex + rowIndex}
                  className={`transition-tool hover:bg-surface/60 ${
                    (startIndex + rowIndex) % 2 === 0 ? 'bg-transparent' : 'bg-surface/20'
                  }`}
                >
                  {headers.map(header => {
                    const value = row[header];
                    return (
                      <td
                        key={`${startIndex + rowIndex}-${header}`}
                        className={`max-w-[24rem] truncate whitespace-nowrap px-3 py-1.5 ${
                          value === null || value === undefined ? 'text-fg/30' : 'text-fg/85'
                        }`}
                        title={formatCellValue(value)}
                      >
                        {formatCellValue(value)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-border/40 bg-surface/30 px-3 py-1.5 text-[12px] text-fg/50">
          <span>
            Showing {startIndex + 1} to {startIndex + visibleRows.length} of {rows.length}
          </span>
          {hasMultiplePages && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage(currentPage - 1)}
                disabled={currentPage === 0}
                aria-label="Previous page"
                className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-border/50 text-fg/60 transition-tool hover:bg-surface/60 hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft size={13} />
              </button>
              <span className="font-display text-[11px]">
                {currentPage + 1} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage(currentPage + 1)}
                disabled={currentPage >= totalPages - 1}
                aria-label="Next page"
                className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-border/50 text-fg/60 transition-tool hover:bg-surface/60 hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronRight size={13} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const ResultsTable: React.FC<ResultsTableProps> = ({ results }) => {
  // Handle cases where results might not be an array
  if (!results) {
    return null;
  }

  // Convert results to array if it's not already
  const resultsArray = Array.isArray(results) ? results : [results];

  if (resultsArray.length === 0) {
    return null;
  }

  // Check if this is actual tabular data or just a message
  const firstItem = resultsArray[0];
  if (!firstItem || typeof firstItem !== 'object') {
    return null;
  }
  const headers = Object.keys(firstItem);

  // Skip rendering if it looks like a string was converted to an object with numeric indices
  const hasOnlyNumericKeys = headers.every(key => /^\d+$/.test(key));
  if (hasOnlyNumericKeys) {
    return null;
  }

  // Also skip if there's only one key and it contains the answer text
  const firstValue: unknown = firstItem[headers[0]];
  if (
    headers.length === 1 &&
    typeof firstValue === 'string' &&
    firstValue.toLowerCase().includes('database')
  ) {
    return null;
  }

  // Group rows with identical column structures (defensive: handles mixed result shapes)
  const objectRows = resultsArray.filter(
    (row): row is Record<string, unknown> =>
      row !== null && typeof row === 'object' && !Array.isArray(row),
  );
  const groupedResults: { headers: string[]; rows: Record<string, unknown>[] }[] = [];

  for (const row of objectRows) {
    const rowHeaders = Object.keys(row).sort();
    const existingGroup = groupedResults.find(
      group =>
        group.headers.length === rowHeaders.length &&
        group.headers.every(h => rowHeaders.includes(h)),
    );

    if (existingGroup) {
      existingGroup.rows.push(row);
    } else {
      groupedResults.push({ headers: rowHeaders, rows: [row] });
    }
  }

  if (groupedResults.length === 0) {
    return null;
  }

  // If we have multiple groups with different structures, render them separately
  if (groupedResults.length > 1) {
    return (
      <div className="space-y-4">
        {groupedResults.map((group, groupIndex) => (
          <PaginatedTable
            key={groupIndex}
            title={groupedResults.length > 1 ? `Results ${groupIndex + 1}` : 'Results'}
            headers={group.headers}
            rows={group.rows}
          />
        ))}
      </div>
    );
  }

  // Single table rendering
  return <PaginatedTable title="Results" headers={groupedResults[0].headers} rows={groupedResults[0].rows} />;
};

export default ResultsTable;
