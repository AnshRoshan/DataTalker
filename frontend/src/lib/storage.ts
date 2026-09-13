import type { ChatMessageData, InputMethod } from '../types';

export const CHAT_HISTORY_KEY = 'datatalker.chatHistory';
export const DB_REF_KEY = 'datatalker.dbRef';
export const API_URL_KEY = 'apiUrl';
export const API_KEY_KEY = 'apiKey';

/** Cap on how many messages are persisted to localStorage (most recent are kept). */
export const MAX_PERSISTED_MESSAGES = 50;

export interface PersistedDbRef {
    inputMethod: InputMethod;
    dbPath: string;
    dbUrl: string;
}

/** Persisted messages must be JSON-safe; results may contain anything the DB returned. */
type PersistedMessage = Omit<ChatMessageData, 'results'> & {
    results: unknown;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

function readJson(key: string): unknown {
    try {
        const raw = localStorage.getItem(key);
        return raw === null ? null : JSON.parse(raw);
    } catch {
        return null;
    }
}

export function loadChatHistory(): ChatMessageData[] {
    const parsed = readJson(CHAT_HISTORY_KEY);
    if (!Array.isArray(parsed)) return [];
    return parsed
        .filter((m): m is PersistedMessage => isRecord(m) && typeof m.id === 'string' && typeof m.question === 'string')
        .map(m => ({
            id: m.id,
            question: m.question,
            answer: typeof m.answer === 'string' ? m.answer : '',
            sql: typeof m.sql === 'string' ? m.sql : '',
            results: (isRecord(m.results) || Array.isArray(m.results) ? m.results : []) as ChatMessageData['results'],
            // A restored message can never still be "typing".
            isTyping: false,
            follow_up_questions: Array.isArray(m.follow_up_questions)
                ? (m.follow_up_questions as string[])
                : undefined,
            results_truncated: typeof m.results_truncated === 'boolean' ? m.results_truncated : undefined,
            sql_executed: typeof m.sql_executed === 'string' ? m.sql_executed : undefined,
            latency_ms: typeof m.latency_ms === 'number' ? m.latency_ms : undefined,
            row_cap: typeof m.row_cap === 'number' ? m.row_cap : undefined,
        }));
}

export function saveChatHistory(messages: ChatMessageData[]): void {
    const capped = messages.slice(-MAX_PERSISTED_MESSAGES).map(m => ({
        ...m,
        isTyping: false,
    }));
    // Shrink-and-retry so a large single message can't silently lose the whole history.
    let candidate = capped;
    while (candidate.length > 0) {
        try {
            localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(candidate));
            return;
        } catch {
            candidate = candidate.slice(Math.ceil(candidate.length / 2));
        }
    }
    try {
        localStorage.removeItem(CHAT_HISTORY_KEY);
    } catch {
        // Nothing more we can do; persistence is best-effort.
    }
}

export function loadDbRef(): PersistedDbRef | null {
    const parsed = readJson(DB_REF_KEY);
    if (!isRecord(parsed)) return null;
    const inputMethod = parsed.inputMethod === 'url' ? 'url' : 'upload';
    return {
        inputMethod,
        dbPath: typeof parsed.dbPath === 'string' ? parsed.dbPath : '',
        dbUrl: typeof parsed.dbUrl === 'string' ? parsed.dbUrl : '',
    };
}

export function saveDbRef(ref: PersistedDbRef): void {
    try {
        localStorage.setItem(DB_REF_KEY, JSON.stringify(ref));
    } catch {
        // Best-effort.
    }
}
