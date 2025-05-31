import React, { useState } from 'react';

interface ResultsTableProps {
    results: Record<string, any>[] | Record<string, any>;
}

const ResultsTable: React.FC<ResultsTableProps> = ({ results }) => {
    const [hoveredRow, setHoveredRow] = useState<string | number | null>(null);
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
    const headers = Object.keys(firstItem);

    // Skip rendering if it looks like a string was converted to an object with numeric indices
    const hasOnlyNumericKeys = headers.every(key => /^\d+$/.test(key));
    if (hasOnlyNumericKeys) {
        return null;
    }

    // Also skip if there's only one key and it contains the answer text
    if (headers.length === 1 && typeof firstItem[headers[0]] === 'string' &&
        firstItem[headers[0]].toLowerCase().includes('database')) {
        return null;
    }

    // Check if we have mixed column structures (multiple result sets)
    const allHeaders = new Set<string>();
    resultsArray.forEach(row => {
        Object.keys(row).forEach(key => allHeaders.add(key));
    });

    // If we have significantly different column structures, group by similar structures
    const groupedResults: { headers: string[], rows: any[] }[] = [];

    for (const row of resultsArray) {
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
            <div className="mt-6 animate-fadeIn space-y-4">
                {groupedResults.map((group, groupIndex) => (
                    <div key={groupIndex}>
                        <div className="flex items-center justify-between mb-3">
                            <p className="font-semibold text-gray-700 flex items-center">
                                <i className="fas fa-table text-green-500 mr-2"></i>
                                Query Results {groupIndex + 1}
                                <span className="ml-2 text-sm font-normal text-gray-500">
                                    ({group.rows.length} {group.rows.length === 1 ? 'row' : 'rows'})
                                </span>
                            </p>
                        </div>
                        <div className="relative">
                            <div className="absolute inset-0 bg-gradient-to-r from-green-400 to-blue-400 rounded-xl blur opacity-20"></div>
                            <div className="relative overflow-hidden rounded-xl border border-gray-200 shadow-lg bg-white">
                                <div className="overflow-x-auto custom-scrollbar">
                                    <table className="min-w-full">
                                        <thead>
                                            <tr className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                                {group.headers.map((key, index) => (
                                                    <th
                                                        key={key}
                                                        scope="col"
                                                        className="px-6 py-4 text-left text-sm font-semibold text-gray-800 uppercase tracking-wider bg-gradient-to-r from-gray-50 to-gray-100"
                                                        style={{
                                                            animationDelay: `${index * 50}ms`
                                                        }}
                                                    >
                                                        <div className="flex items-center space-x-1">
                                                            <span>{key}</span>
                                                        </div>
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {group.rows.map((row, rowIndex) => (
                                                <tr
                                                    key={rowIndex}
                                                    className={`
                                                        transition-all duration-200
                                                        ${rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                                                        ${hoveredRow === `${groupIndex}-${rowIndex}` ? 'bg-blue-50 shadow-sm' : ''}
                                                        hover:bg-blue-50 hover:shadow-sm
                                                        group
                                                    `}
                                                    onMouseEnter={() => setHoveredRow(`${groupIndex}-${rowIndex}`)}
                                                    onMouseLeave={() => setHoveredRow(null)}
                                                    style={{
                                                        animationDelay: `${(rowIndex + 1) * 50}ms`
                                                    }}
                                                >
                                                    {group.headers.map((header, colIndex) => (
                                                        <td
                                                            key={`${rowIndex}-${colIndex}`}
                                                            className="px-6 py-4 text-sm text-gray-700 whitespace-nowrap"
                                                        >
                                                            <div className="flex items-center space-x-2">
                                                                {colIndex === 0 && (
                                                                    <div className={`
                                                                        w-2 h-2 rounded-full mr-2 transition-all duration-200
                                                                        ${hoveredRow === `${groupIndex}-${rowIndex}` ? 'bg-blue-400' : 'bg-gray-300'}
                                                                    `} />
                                                                )}
                                                                <span className="font-medium group-hover:text-gray-900">
                                                                    {row[header] !== undefined ? String(row[header]) : '—'}
                                                                </span>
                                                            </div>
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    // Single table rendering (original logic)
    return (
        <div className="mt-6 animate-fadeIn">
            <div className="flex items-center justify-between mb-3">
                <p className="font-semibold text-gray-700 flex items-center">
                    <i className="fas fa-table text-green-500 mr-2"></i>
                    Query Results
                    <span className="ml-2 text-sm font-normal text-gray-500">
                        ({resultsArray.length} {resultsArray.length === 1 ? 'row' : 'rows'})
                    </span>
                </p>
            </div>
            <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-green-400 to-blue-400 rounded-xl blur opacity-20"></div>
                <div className="relative overflow-hidden rounded-xl border border-gray-200 shadow-lg bg-white">
                    <div className="overflow-x-auto custom-scrollbar">
                        <table className="min-w-full">
                            <thead>
                                <tr className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                    {headers.map((key, index) => (
                                        <th
                                            key={key}
                                            scope="col"
                                            className="px-6 py-4 text-left text-sm font-semibold text-gray-800 uppercase tracking-wider bg-gradient-to-r from-gray-50 to-gray-100"
                                            style={{
                                                animationDelay: `${index * 50}ms`
                                            }}
                                        >
                                            <div className="flex items-center space-x-1">
                                                <span>{key}</span>
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {resultsArray.map((row, rowIndex) => (
                                    <tr
                                        key={rowIndex}
                                        className={`
                                            transition-all duration-200
                                            ${rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                                            ${hoveredRow === rowIndex ? 'bg-blue-50 shadow-sm' : ''}
                                            hover:bg-blue-50 hover:shadow-sm
                                            group
                                        `}
                                        onMouseEnter={() => setHoveredRow(rowIndex)}
                                        onMouseLeave={() => setHoveredRow(null)}
                                        style={{
                                            animationDelay: `${(rowIndex + 1) * 50}ms`
                                        }}
                                    >
                                        {headers.map((header, colIndex) => (
                                            <td
                                                key={`${rowIndex}-${colIndex}`}
                                                className="px-6 py-4 text-sm text-gray-700 whitespace-nowrap"
                                            >
                                                <div className="flex items-center space-x-2">
                                                    {colIndex === 0 && (
                                                        <div className={`
                                                            w-2 h-2 rounded-full mr-2 transition-all duration-200
                                                            ${hoveredRow === rowIndex ? 'bg-blue-400' : 'bg-gray-300'}
                                                        `} />
                                                    )}
                                                    <span className="font-medium group-hover:text-gray-900">
                                                        {row[header] !== undefined ? String(row[header]) : '—'}
                                                    </span>
                                                </div>
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResultsTable;