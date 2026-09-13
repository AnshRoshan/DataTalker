/** Escape a single cell for RFC-4180-style CSV output. */
function escapeCsvValue(value: unknown): string {
    if (value === null || value === undefined) return '';
    let text: string;
    if (typeof value === 'object') {
        try {
            text = JSON.stringify(value);
        } catch {
            text = String(value);
        }
    } else {
        text = String(value);
    }
    if (/[",\n\r]/.test(text)) {
        text = `"${text.replace(/"/g, '""')}"`;
    }
    return text;
}

/**
 * Serialize rows to CSV (with a UTF-8 BOM for Excel) and trigger a browser download.
 */
export function downloadCsv(
    filename: string,
    headers: string[],
    rows: Record<string, unknown>[],
): void {
    const lines: string[] = [headers.map(escapeCsvValue).join(',')];
    for (const row of rows) {
        lines.push(headers.map(header => escapeCsvValue(row[header])).join(','));
    }
    const blob = new Blob([`\ufeff${lines.join('\r\n')}`], {
        type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
}
