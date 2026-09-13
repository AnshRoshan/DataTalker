import React, { useState } from 'react';
import { downloadCsv } from '../lib/csv';

interface ResultsTableProps {
    results: Record<string, unknown>[] | Record<string, unknown>;
}

const PAGE_SIZE = 50;

/** Render a cell value; objects/arrays are shown as JSON. */
const formatCellValue = (value: unknown): string => {
    if (value === null || value === undefined) return '—';
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
        <div className="mt-6 animate-fadeIn">
            <div className="flex items-center justify-between mb-3">
                <p className="font-semibold text-gray-700 flex items-center">
                    <i className="fas fa-table text-green-500 mr-2"></i>
                    {title}
                    <span className="ml-2 text-sm font-normal text-gray-500">
                        ({rows.length} {rows.length === 1 ? 'row' : 'rows'})
                    </span>
                </p>
                <button
                    onClick={() => downloadCsv('query-results.csv', headers, rows)}
                    className="px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-800 transition-all duration-200 flex items-center"
                    aria-label="Download results as CSV"
                >
                    <i className="fas fa-download mr-2 text-green-500"></i>
                    Download CSV
                </button>
            </div>
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-green-400 to-blue-400 rounded-xl blur opacity-20"></div>
                <div className="relative overflow-hidden rounded-xl border border-gray-200 shadow-lg bg-white">
                    <div className="overflow-x-auto custom-scrollbar">
                        <table className="min-w-full">
                            <thead>
                                <tr className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                    {headers.map(key => (
                                        <th
                                            key={key}
                                            scope="col"
                                            className="px-6 py-4 text-left text-sm font-semibold text-gray-800 uppercase tracking-wider bg-gradient-to-r from-gray-50 to-gray-100"
                                        >
                                            <div className="flex items-center space-x-1">
                                                <span>{key}</span>
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {visibleRows.map((row, rowIndex) => (
                                    <tr
                                        key={startIndex + rowIndex}
                                        className={`
                                            transition-colors duration-200
                                            ${(startIndex + rowIndex) % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                                            hover:bg-blue-50
                                        `}
                                    >
                                        {headers.map(header => (
                                            <td
                                                key={`${startIndex + rowIndex}-${header}`}
                                                className="px-6 py-4 text-sm text-gray-700 whitespace-nowrap"
                                            >
                                                <span className="font-medium">
                                                    {formatCellValue(row[header])}
                                                </span>
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50/50 text-sm text-gray-600">
                        <span>
                            Showing {startIndex + 1}–{startIndex + visibleRows.length} of {rows.length} rows
                        </span>
                        {hasMultiplePages && (
                            <div className="flex items-center space-x-2">
                                <button
                                    onClick={() => setPage(currentPage - 1)}
                                    disabled={currentPage === 0}
                                    className="px-3 py-1 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    <i className="fas fa-chevron-left"></i>
                                </button>
                                <span className="text-xs">
                                    Page {currentPage + 1} of {totalPages}
                                </span>
                                <button
                                    onClick={() => setPage(currentPage + 1)}
                                    disabled={currentPage >= totalPages - 1}
                                    className="px-3 py-1 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    <i className="fas fa-chevron-right"></i>
                                </button>
                            </div>
                        )}
                    </div>
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
    // If the result has only numeric keys (0, 1, 2...) it's likely just a string that was converted to an object
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
    if (headers.length === 1 && typeof firstValue === 'string' &&
        firstValue.toLowerCase().includes('database')) {
        return null;
    }

    // Check if we have mixed column structures (multiple result sets)
    // If we have significantly different column structures, group by similar structures
    const objectRows = resultsArray.filter(
        (row): row is Record<string, unknown> => row !== null && typeof row === 'object' && !Array.isArray(row),
    );
    const groupedResults: { headers: string[], rows: Record<string, unknown>[] }[] = [];

    for (const row of objectRows) {
        const rowHeaders = Object.keys(row).sort();
        const existingGroup = groupedResults.find(group =>
            group.headers.length === rowHeaders.length &&
            group.headers.every(h => rowHeaders.includes(h))
        );

        if (existingGroup) {
            existingGroup.rows.push(row);
        } else {
            groupedResults.push({
                headers: rowHeaders,
                rows: [row]
            });
        }
    }

    // If we have multiple groups with different structures, render them separately
    if (groupedResults.length > 1) {
        return (
            <div className="space-y-4">
                {groupedResults.map((group, groupIndex) => (
                    <PaginatedTable
                        key={groupIndex}
                        title={
                            <>
                                Query Results {groupIndex + 1}
                            </>
                        }
                        headers={group.headers}
                        rows={group.rows}
                    />
                ))}
            </div>
        );
    }

    // Single table rendering (original logic)
    return (
        <PaginatedTable
            title="Query Results"
            headers={headers}
            rows={objectRows}
        />
    );
};

export default ResultsTable;
